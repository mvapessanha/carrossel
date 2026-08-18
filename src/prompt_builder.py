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

Duas tecnicas vindas da doc oficial do Google ("Ultimate prompting guide for
Nano Banana") aplicadas aqui:
1. Texto exato entre aspas -- sinaliza reproducao literal, char a char, em vez
   de "inspiracao" pro texto.
2. Ancora positiva ANTES da lista de negativas -- "isto e' um design plano
   tipo poster impresso" antes de listar o que nunca pode aparecer, reduz o
   risco do modelo "pensar" no elemento negado so por ele ter sido mencionado.

O formato (aspect_ratio) tambem e' reforcado aqui em texto, alem de ser
mandado de verdade pra API via generationConfig.imageConfig (gemini_nano_banana.py)
-- as duas coisas juntas, nao uma ou outra, e' o que da garantia real de
formato certo pro post.
"""
from dataclasses import dataclass

from src.planner.content_planner import SlideBrief

_ROLE_LABELS = {
    "hook": "gancho de abertura do carrossel",
    "value": "conteudo principal",
    "cta": "chamada para acao de fechamento",
    "single": "post unico (imagem avulsa)",
}


@dataclass
class PromptResult:
    full_prompt: str  # prompt completo mandado ao provedor (e' o que fica salvo/mostrado na biblioteca)
    exact_text: str  # so o texto que precisa aparecer, sem o resto do prompt ao redor


_CORE_INSTRUCTIONS = """Voce e' um designer grafico profissional criando uma peca criativa PRONTA
PARA PUBLICAR no Instagram (nao uma demonstracao, nao um mockup do app).

O QUE ESTA IMAGEM E': um design grafico plano, uma unica peca visual completa
-- pense nela como um cartaz/poster impresso ou um card digital, ocupando o
quadro inteiro de ponta a ponta.

REGRAS OBRIGATORIAS, sempre, sem excecao:
- A imagem final e' o proprio criativo (o post), preenchendo o quadro inteiro.
  NUNCA inclua celular, navegador, barra de status, cabecalho do app, botao
  "Seguir", icones de curtir/comentar/compartilhar/salvar, contador de likes
  ou comentarios, nome de usuario, foto de perfil, indicador de "slide X de Y"
  ou qualquer outro elemento de interface do Instagram. Isso NUNCA deve
  aparecer, mesmo que uma imagem de referencia mostre isso.
- Isto TAMBEM NAO e' um slide de apresentacao (PowerPoint, Google Slides,
  Keynote): nunca inclua numeracao de pagina/slide (ex: "6 de 7", "6/7"),
  rodape de apresentacao, bordas de slide, cursor do mouse ou qualquer outro
  elemento tipico de um software de apresentacao. E' uma peca grafica unica,
  autonoma, feita pra ser publicada como imagem.
- Cada imagem de referencia anexada vem com uma legenda dizendo o papel dela
  (estetica do usuario, ou slide anterior so pra consistencia). Siga
  exatamente o que a legenda de cada uma pede -- nunca copie texto, numeros
  ou conteudo que apareca em nenhuma delas, elas sao guia visual, nao
  conteudo a reproduzir.

FIDELIDADE DE TEXTO -- a regra mais importante de todas, prioridade maxima:
  O texto entre aspas em [CONTEUDO A TRANSMITIR NESTA IMAGEM] abaixo tem que
  aparecer 100% IDENTICO, palavra por palavra e letra por letra. Isso
  significa, sem excecao:
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
    nenhuma -- reproduza exatamente o que esta entre aspas, mesmo que pareca
    longo. Se precisar quebrar em mais de uma linha por espaco, quebre a
    frase, nunca corte ou altere uma palavra.
  - Antes de finalizar, confira mentalmente cada palavra da imagem contra o
    texto entre aspas, letra por letra.
- Descreva a fonte de forma generica (ex: "sans-serif limpa e em negrito",
  "serifada elegante"), nunca pelo nome de uma fonte especifica.
- Estruture a hierarquia visual explicitamente: qual texto e' o titulo
  (maior, topo ou centro), qual e' o corpo (menor, abaixo), e onde fica
  qualquer elemento grafico de apoio (icone, grafico, forma). Nao deixe o
  layout implicito.
- Seja especifico, nunca vago: descreva fundo, cores exatas (por nome ou
  tom), e composicao explicitamente em vez de deixar a IA decidir sozinha.

TAMANHO DE TEXTO -- equilibrio profissional, sempre:
  O tamanho das letras e' o de uma peca grafica profissional (editorial,
  revista, post de marca séria), nunca amador. Isso quer dizer nos dois
  sentidos:
  - NUNCA pequeno/fino demais a ponto de ficar dificil de ler numa miniatura
    de feed do celular.
  - NUNCA gigante/exagerado a ponto de parecer clickbait, meme ou anuncio
    barato -- o texto nao pode dominar o quadro sozinho nem espremer os
    elementos graficos.
  O titulo/gancho pode ser maior que o corpo (hierarquia visual), mas dentro
  de uma proporcao equilibrada com o espaco em branco e os elementos visuais
  ao redor -- como um designer profissional calibraria, nao no extremo.

ALINHAMENTO -- tudo alinhado com precisao, sempre:
  Todo texto e elemento grafico segue um grid/eixo consistente (margens
  iguais nos dois lados, linhas de base retas, blocos de texto alinhados
  entre si -- a esquerda, centralizado ou a direita, mas sempre o MESMO
  alinhamento dentro do mesmo bloco). Nada torto, desalinhado, com margens
  desiguais ou elementos flutuando fora do eixo do layout.

NUNCA REPITA PALAVRAS OU FRASES:
  Cada palavra, frase ou linha do texto entre aspas aparece exatamente UMA
  VEZ na imagem. Nunca duplique o titulo, nunca escreva a mesma frase em
  dois lugares diferentes, nunca ecoe um trecho do texto uma segunda vez em
  outra posicao do design."""


_FORMAT_LABELS = {
    "4:5": "retrato 4:5 (formato padrao de post/carrossel do Instagram)",
    "1:1": "quadrado 1:1",
    "9:16": "retrato 9:16 (Stories/Reels)",
}


def _orientation_note(aspect_ratio: str) -> str:
    try:
        w, h = (int(p) for p in aspect_ratio.split(":"))
    except ValueError:
        return ""
    if h > w:
        return " -- RETRATO (mais alto que largo), nunca paisagem/deitado"
    if w > h:
        return " -- PAISAGEM (mais largo que alto), nunca em pe"
    return " -- QUADRADO (largura igual altura)"


def build_prompt(brief: SlideBrief, design_text: str, total_slides: int, aspect_ratio: str = "4:5") -> PromptResult:
    role_label = _ROLE_LABELS.get(brief.role, "conteudo")
    exact_text = brief.text
    format_label = _FORMAT_LABELS.get(aspect_ratio, f"proporcao {aspect_ratio}")

    parts = [
        _CORE_INSTRUCTIONS,
        f"[TIPO DESTA IMAGEM]\n{role_label}, slide {brief.index} de {total_slides}.",
        f"[FORMATO]\nProporcao {format_label}{_orientation_note(aspect_ratio)}. "
        "Preencha o quadro inteiro de ponta a ponta, sem bordas, faixas em branco/pretas nem cortar "
        "elementos importantes nas margens.",
        f'[CONTEUDO A TRANSMITIR NESTA IMAGEM]\nO texto a seguir tem que aparecer exatamente como esta, '
        f'entre aspas, char a char:\n"{exact_text}"',
    ]
    if design_text:
        parts.append(f"[ESTILO/DESIGN DESEJADO]\n{design_text}")
    if total_slides > 1:
        parts.append(
            "Mantenha a mesma identidade visual (cores, tipografia, composicao) "
            "das outras imagens deste mesmo carrossel, seguindo o [ESTILO/DESIGN DESEJADO] acima -- "
            "essa e' a fonte principal de consistencia, mais importante que qualquer imagem de "
            "referencia de slide anterior anexada."
        )

    return PromptResult(full_prompt="\n\n".join(parts), exact_text=exact_text)
