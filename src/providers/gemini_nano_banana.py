"""Gemini "Nano Banana" -- duas variantes selecionaveis (config/providers.yaml
registra as duas como entradas separadas, ambas usando este modulo):
- GeminiNanoBananaProvider (Flash, gemini-3.1-flash-image): mais barato
  (~US$0.067/imagem 1K), boa qualidade geral.
- GeminiNanoBananaProProvider (Pro, gemini-3-pro-image): ~US$0.134/imagem
  (2x o Flash), mas a propria Google posiciona esse como o modelo pra texto
  longo/preciso em infografico/marketing -- confirmado tambem por quem ja usa
  em producao pra carrossel (Nano Banana Pro "e' disparado o melhor modelo de
  imagem pra slides com texto real, sem distorcer"). Prioridade #1 do produto
  e' fidelidade de texto, entao o Pro fica primeiro na cadeia automatica.

Tecnicas aplicadas aqui, vindas da doc oficial do Google ("Ultimate prompting
guide for Nano Banana") e de relatos de quem ja usa isso em producao pra
carrossel:
1. Confirmar o texto exato num turno "fake" ANTES do turno que pede a imagem
   -- pedir texto+composicao visual no mesmo turno faz o texto competir por
   atencao com o resto da composicao, e o texto costuma perder. Pre-preencher
   um turno de "model" ja ecoando o texto ancora ele antes da imagem ser
   pedida, sem custo extra de chamada (continua sendo 1 unica requisicao HTTP).
2. Rotular o papel de cada imagem de referencia explicitamente (qual e'
   estetica do usuario, qual e' o slide anterior so pra consistencia) --
   evita o modelo tratar todas como igualmente importantes/copiaveis.
3. Mandar aspectRatio de verdade em generationConfig.imageConfig (campo
   confirmado via doc oficial) -- antes o parametro aspect_ratio chegava aqui
   e nunca era usado no request, o formato ficava so "sugerido" pelo texto do
   prompt, sem garantia nenhuma da API.

Aceita bytes de referencia diretamente (inline_data), sem precisar de URL publica.
"""
import base64
import os

import httpx

from src.providers.base import GeneratedImage, ImageProvider, ProviderError

API_URL = "https://generativelanguage.googleapis.com/v1/models/{model}:generateContent"


class GeminiNanoBananaProvider(ImageProvider):
    id = "gemini_nano_banana"
    label = "Gemini (Nano Banana 2 - Flash)"
    supports_reference = True
    max_reference_images = 14
    MODEL = "gemini-3.1-flash-image"
    IMAGE_SIZE = "1K"  # bate com o cost_per_image_usd de config/providers.yaml (preco varia por tamanho)

    def _reference_parts(self, reference_images: list[bytes], consistency_ref_included: bool) -> list[dict]:
        parts: list[dict] = []
        aesthetic_count = len(reference_images) - (1 if consistency_ref_included else 0)
        for i, img_bytes in enumerate(reference_images):
            is_consistency = consistency_ref_included and i == len(reference_images) - 1
            if is_consistency:
                label = (
                    "Imagem de referencia (slide anterior deste MESMO carrossel, so pra voce manter a "
                    "mesma identidade visual -- cores, tipografia, composicao geral). Prioridade menor que "
                    "o texto exato pedido abaixo: gere um conteudo NOVO, nao repita o texto desta referencia."
                )
            else:
                n = i + 1
                label = (
                    f"Imagem de referencia {n} de {aesthetic_count} (estetica enviada pelo usuario). Use "
                    "APENAS como guia de cor/tipografia/composicao -- nunca copie texto, numeros ou "
                    "conteudo que apareca nela."
                )
            parts.append({"text": label})
            parts.append(
                {"inlineData": {"mimeType": "image/png", "data": base64.b64encode(img_bytes).decode("ascii")}}
            )
        return parts

    def _build_contents(
        self, prompt: str, reference_images: list[bytes], exact_text: str, consistency_ref_included: bool
    ) -> list[dict]:
        contents = []
        if exact_text:
            contents.append(
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": (
                                "Repita exatamente, caractere por caractere, sem mudar absolutamente nada "
                                "(inclusive acentos e pontuacao), o texto a seguir. Ele vai aparecer numa "
                                f"imagem que voce vai gerar em seguida:\n\n\"{exact_text}\""
                            )
                        }
                    ],
                }
            )
            contents.append({"role": "model", "parts": [{"text": exact_text}]})

        parts = [{"text": prompt}] + self._reference_parts(reference_images, consistency_ref_included)
        contents.append({"role": "user", "parts": parts})
        return contents

    def generate(
        self,
        prompt: str,
        reference_images: list[bytes],
        aspect_ratio: str,
        exact_text: str = "",
        consistency_ref_included: bool = False,
    ) -> GeneratedImage:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ProviderError("GEMINI_API_KEY nao configurada")

        contents = self._build_contents(
            prompt, reference_images[: self.max_reference_images], exact_text, consistency_ref_included
        )

        try:
            resp = httpx.post(
                API_URL.format(model=self.MODEL),
                headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
                json={
                    "contents": contents,
                    "generationConfig": {
                        "imageConfig": {"aspectRatio": aspect_ratio, "imageSize": self.IMAGE_SIZE}
                    },
                },
                timeout=90,
            )
        except httpx.HTTPError as e:
            raise ProviderError(f"Erro de rede no Gemini: {e}") from e

        if resp.status_code == 429:
            raise ProviderError("Gemini: cota/limite de taxa excedido (429)")
        if resp.status_code != 200:
            raise ProviderError(f"Gemini retornou {resp.status_code}: {resp.text[:300]}")

        data = resp.json()
        try:
            candidate_parts = data["candidates"][0]["content"]["parts"]
        except (KeyError, IndexError) as e:
            raise ProviderError(f"Resposta inesperada do Gemini: {e}") from e

        for part in candidate_parts:
            # a resposta real da API usa camelCase (inlineData/mimeType), apesar
            # do request aceitar snake_case; checamos os dois por seguranca.
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                mime_type = inline.get("mimeType") or inline.get("mime_type", "image/png")
                return GeneratedImage(image_bytes=base64.b64decode(inline["data"]), mime_type=mime_type)

        raise ProviderError("Gemini nao retornou nenhuma imagem (pode ter recusado o prompt)")


class GeminiNanoBananaProProvider(GeminiNanoBananaProvider):
    id = "gemini_nano_banana_pro"
    label = "Gemini (Nano Banana Pro)"
    MODEL = "gemini-3-pro-image"
    IMAGE_SIZE = "2K"  # no Pro, 2K custa o mesmo que 1K (ver providers.yaml) -- melhor nitidez de texto de graca
