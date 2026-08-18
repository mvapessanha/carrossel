"""Monta o prompt unico e estruturado que vai pro gerador de imagem, juntando
o bloco de texto do slide (ja organizado pelo planner) com a descricao de
design. As caixas "Conteudo" e "Design" da UI existem so pra pessoa organizar
o que quer dizer -- na chamada de verdade viram um prompt so.

Instrucao fixa de "imagem limpa e profissional" vive aqui (nao em cada
provider) porque e' um requisito de produto, nao de uma IA especifica:
descoberto na pratica que sem isso, quando a referencia estetica e' um print
de post real, a IA as vezes recria a interface do Instagram inteira (like,
comentario, nome de usuario, texto inventado) em vez de so aproveitar a
estetica (cores/tipografia/composicao). O core do prompt deixa isso
impossivel de confundir.
"""
from src.planner.content_planner import SlideBrief

_ROLE_LABELS = {
    "hook": "gancho de abertura do carrossel",
    "value": "conteudo principal",
    "cta": "chamada para acao de fechamento",
    "single": "post unico (imagem avulsa)",
}

_CORE_INSTRUCTIONS = """Voce e' um designer grafico profissional criando uma peca criativa PRONTA
PARA PUBLICAR no Instagram (nao uma demonstracao, nao um mockup do app).

REGRAS OBRIGATORIAS, sempre, sem excecao:
- A imagem final e' o proprio criativo (o post), preenchendo o quadro inteiro.
  NUNCA inclua celular, navegador, barra de status, cabecalho do app, botao
  "Seguir", icones de curtir/comentar/compartilhar/salvar, contador de likes
  ou comentarios, nome de usuario, foto de perfil, indicador de "slide X de Y"
  ou qualquer outro elemento de interface do Instagram. Isso NUNCA deve
  aparecer, mesmo que uma imagem de referencia mostre isso.
- Se houver imagem(ns) de referencia anexada(s), use-as APENAS como guia de
  ESTETICA: paleta de cores, estilo tipografico, composicao/layout, tom
  visual geral. Nunca copie textos, numeros, nomes ou qualquer conteudo que
  apareca na referencia -- a referencia e' sobre COMO fica visualmente, nao
  SOBRE O QUE dizer.

FIDELIDADE DE TEXTO -- a regra mais importante de todas, prioridade maxima:
  O texto que aparece na imagem tem que ser 100% IDENTICO, palavra por
  palavra e letra por letra, ao texto indicado em [CONTEUDO A TRANSMITIR
  NESTA IMAGEM] abaixo. Isso significa, sem excecao:
  - Zero erro de ortografia em portugues. Nenhuma letra trocada, faltando ou
    sobrando (ex: nunca escreva "mudang", "descovra" ou "segnica" quando o
    texto diz "mudando", "descubra", "significa").
  - Todos os acentos exatamente como no texto original (á, â, ã, é, ê, í, ó,
    ô, õ, ú, ç). Nunca troque "vocû" por "você" nem remova um acento.
  - Toda a pontuacao do texto original preservada -- virgula, ponto, dois
    pontos, interrogacao -- exatamente onde esta, sem adicionar nem remover.
  - Nenhuma palavra solta, cortada, fundida com outra ou fora de ordem (ex:
    nunca escreva "Expectvaida" quando e' "Expectativa", nem "Decisôs ie"
    quando e' "Decisões e").
  - Nao parafraseie, resuma, abrevie nem reescreva o texto de forma
    nenhuma -- reproduza exatamente como foi escrito, mesmo que pareca
    longo. Se precisar quebrar em mais de uma linha por espaco, quebre a
    frase, nunca corte ou altere uma palavra.
  - Antes de finalizar, confira mentalmente cada palavra da imagem contra o
    texto original, letra por letra.
- Descreva a fonte de forma generica (ex: "sans-serif limpa e em negrito",
  "serifada elegante"), nunca pelo nome de uma fonte especifica.
- Estruture a hierarquia visual explicitamente: qual texto e' o titulo
  (maior, topo ou centro), qual e' o corpo (menor, abaixo), e onde fica
  qualquer elemento grafico de apoio (icone, grafico, forma). Nao deixe o
  layout implicito.
- Seja especifico, nunca vago: descreva fundo, cores exatas (por nome ou
  tom), e composicao explicitamente em vez de deixar a IA decidir sozinha."""


def build_prompt(brief: SlideBrief, design_text: str, total_slides: int) -> str:
    role_label = _ROLE_LABELS.get(brief.role, "conteudo")

    parts = [
        _CORE_INSTRUCTIONS,
        f"[TIPO DESTA IMAGEM]\n{role_label}, slide {brief.index} de {total_slides}.",
        f"[CONTEUDO A TRANSMITIR NESTA IMAGEM]\n{brief.text}",
    ]
    if design_text:
        parts.append(f"[ESTILO/DESIGN DESEJADO]\n{design_text}")
    if total_slides > 1:
        parts.append(
            "Mantenha a mesma identidade visual (cores, tipografia, composicao) "
            "das outras imagens deste mesmo carrossel."
        )

    return "\n\n".join(parts)
