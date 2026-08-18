"""Gemini 'Nano Banana 2' (gemini-3.1-flash-image) — melhor modelo de imagem
disponivel pra essa conta (nao existe um tier "Pro" separado; confirmado via
lista real de modelos em ago/2026: so gemini-2.5-flash-image,
gemini-3.1-flash-image e gemini-3.1-flash-lite-image). ~$0.067/imagem (1K),
mais caro que o 2.5 ($0.039) mas com melhor renderizacao de texto.
Exige billing (Blaze) ativado no projeto Google -- tier gratuito tem cota 0
pra geracao de imagem (confirmado testando com chave real em ago/2026).
Aceita bytes de referencia diretamente (inline_data), sem precisar de URL publica.
"""
import base64
import os

import httpx

from src.providers.base import GeneratedImage, ImageProvider, ProviderError

MODEL = "gemini-3.1-flash-image"
URL = f"https://generativelanguage.googleapis.com/v1/models/{MODEL}:generateContent"


class GeminiNanoBananaProvider(ImageProvider):
    id = "gemini_nano_banana"
    label = "Gemini (Nano Banana)"
    supports_reference = True
    max_reference_images = 14

    def generate(self, prompt: str, reference_images: list[bytes], aspect_ratio: str) -> GeneratedImage:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ProviderError("GEMINI_API_KEY nao configurada")

        parts = [{"text": prompt}]
        for img_bytes in reference_images[: self.max_reference_images]:
            parts.append(
                {"inlineData": {"mimeType": "image/png", "data": base64.b64encode(img_bytes).decode("ascii")}}
            )

        try:
            resp = httpx.post(
                URL,
                headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
                json={"contents": [{"parts": parts}]},
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
