"""Divide o conteudo bruto em N blocos de texto (um por slide), seguindo a
logica de carrossel do Instagram (gancho -> valor -> CTA), usando Groq
(gratis, rapido) como planejador de texto -- separado da cota de imagem.

Usa o modelo "groq/compound", que decide sozinho quando fazer busca na web
(sem custo/setup extra, mesma chave) -- importante quando o conteudo passado
pela pessoa e' vago/geral e envolve dados reais (numeros, taxas, datas etc),
pra nao inventar informacao. Por usar tool-use, response_format=json_object
nao e' garantido; por isso o parsing do JSON e' defensivo (aceita cercas de
markdown, extrai o objeto se vier com texto ao redor).

E' a primeira das duas chamadas do pipeline: o resultado daqui (texto ja
limpo e dividido) que alimenta a segunda chamada, ao gerador de imagem.
"""
import json
import os
import re
import time
from dataclasses import dataclass

import httpx

from src.config import load_config
from src.quota import tracker

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
RETRIES = 1
RETRY_BACKOFF_SECONDS = 4.0


class PlannerError(Exception):
    pass


@dataclass
class SlideBrief:
    index: int
    role: str | None
    text: str


_SYSTEM_PROMPT = """Voce e' um redator especialista em carrosseis do Instagram.
Recebe um conteudo bruto e uma descricao de estilo/tom, e divide o conteudo em
exatamente N blocos de texto, um por imagem, seguindo a logica de post de
carrossel do Instagram:
- Se N == 1: uma unica mensagem forte e completa (post de imagem unica), role="single".
- Se N > 1: o slide 1 e' um gancho (role="hook") que prende atencao logo de cara;
  os slides do meio entregam o conteudo em pedacos claros e escaneaveis, um
  assunto por slide (role="value"); o ultimo slide e' uma chamada para acao
  coerente com o conteudo (role="cta").
- Se o conteudo ja disser explicitamente o que colocar em cada slide/imagem,
  respeite isso ao inves de redividir por conta propria.
- TEXTO CURTO POR SLIDE, sempre que o conteudo permitir: carrossel que converte
  tem pouco texto por imagem, escaneavel num relance -- nao um paragrafo denso.
  Dentro dos N slides pedidos, prefira uma frase de impacto curta (ate ~12-15
  palavras) por slide; se o assunto de um slide especifico precisar de mais,
  quebre em titulo curto + 1-2 frases curtas de apoio, nunca um bloco continuo
  longo. Isso nao e' cortar informacao -- e' distribuir o MESMO conteudo de
  forma mais legivel entre os slides que ja existem.
- Se a pessoa ja forneceu dados/numeros especificos (taxas, datas,
  estatisticas etc.), use exatamente esses.
- Se o conteudo for vago/generico e voce NAO tiver certeza de um numero,
  taxa, data ou estatistica especifica, NUNCA invente um valor especifico
  como se fosse real. Nesse caso, fale do assunto de forma mais geral/
  conceitual (sem o numero preciso) em vez de arriscar um dado falso.
- Nunca invente informacao que nao esteja no conteudo original.
- Nao use travessao (—) nem meia-risca/en dash (–) em nenhum texto, nem pra
  ligar duas frases nem como pontuacao. Troque por ponto, virgula, dois
  pontos ou frases curtas separadas.
- Nenhum slide pode ficar com texto vazio.
- Responda SOMENTE em JSON, sem nenhum texto antes ou depois, no formato exato:
  {"slides": [{"index": 1, "role": "hook", "text": "..."}]}
  Devolva exatamente N itens em "slides", nessa ordem.
"""

_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)
_DASH_RE = re.compile(r"\s*[—–]\s*")


def _strip_dashes(text: str) -> str:
    """Rede de seguranca determinística: garante que nenhum travessao/meia-risca
    passe, independente do modelo seguir a instrucao ou nao."""
    return _DASH_RE.sub(", ", text).strip()


def _extract_json(content: str) -> dict:
    content = content.strip()
    if content.startswith("```"):
        content = content.strip("`")
        content = content[content.find("\n") + 1 :] if "\n" in content else content
    try:
        return json.loads(content)
    except ValueError:
        pass
    match = _JSON_BLOCK_RE.search(content)
    if match:
        return json.loads(match.group(0))
    raise ValueError("nenhum JSON encontrado na resposta")


def _call_groq_once(api_key: str, model: str, user_message: str) -> list[dict]:
    try:
        resp = httpx.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                "temperature": 0.7,
            },
            timeout=90,
        )
    except httpx.HTTPError as e:
        raise PlannerError(f"erro de rede: {e}") from e

    if resp.status_code != 200:
        raise PlannerError(f"retornou {resp.status_code}: {resp.text[:300]}")

    try:
        content = resp.json()["choices"][0]["message"]["content"]
        raw_slides = _extract_json(content)["slides"]
    except (KeyError, IndexError, ValueError) as e:
        raise PlannerError(f"resposta em formato inesperado: {e}") from e

    if not raw_slides or any(not str(s.get("text", "")).strip() for s in raw_slides):
        raise PlannerError("resposta veio com slide(s) sem texto")

    return raw_slides


def plan_slides(content_text: str, design_text: str, num_images: int) -> list[SlideBrief]:
    planner_config = load_config()["planner"]
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise PlannerError("GROQ_API_KEY nao configurada")

    planner_id = f"planner_{planner_config['provider']}"
    tracker.ensure_available(planner_id, planner_config["quota"])

    user_message = (
        f"Numero de imagens (N): {num_images}\n\n"
        f"CONTEUDO A TRANSMITIR:\n{content_text}\n\n"
        f"ESTILO/TOM DESEJADO (contexto pra calibrar o tom do texto):\n{design_text or '(nao informado)'}"
    )

    last_error: PlannerError | None = None
    raw_slides: list[dict] | None = None
    for attempt in range(RETRIES + 1):
        try:
            raw_slides = _call_groq_once(api_key, planner_config["model"], user_message)
            break
        except PlannerError as e:
            last_error = e
            if attempt < RETRIES:
                time.sleep(RETRY_BACKOFF_SECONDS)

    if raw_slides is None:
        raise PlannerError(f"Groq falhou apos {RETRIES + 1} tentativa(s) — {last_error}")

    tracker.increment(planner_id, planner_config["quota"]["window"])

    briefs = [
        SlideBrief(index=s.get("index", i + 1), role=s.get("role"), text=s.get("text", ""))
        for i, s in enumerate(raw_slides)
    ]

    if len(briefs) > num_images:
        briefs = briefs[:num_images]
    while len(briefs) < num_images:
        briefs.append(SlideBrief(index=len(briefs) + 1, role="value", text=content_text))

    for b in briefs:
        b.text = _strip_dashes(b.text)

    return briefs
