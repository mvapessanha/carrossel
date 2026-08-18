"""Together AI — FLUX.1 [schnell] Free. Gratis e sem limite fixo publicado,
mas so texto->imagem (sem suporte a referencia). Fallback antes do Pollinations
Flux, quando a chave TOGETHER_API_KEY estiver configurada.
"""
import base64
import os

import httpx

from src.providers.base import GeneratedImage, ImageProvider, ProviderError, aspect_ratio_to_size

URL = "https://api.together.xyz/v1/images/generations"
MODEL = "black-forest-labs/FLUX.1-schnell-Free"


class TogetherFluxSchnellProvider(ImageProvider):
    id = "together_flux_schnell"
    label = "Together (FLUX schnell)"
    supports_reference = False
    max_reference_images = 0

    def generate(self, prompt: str, reference_images: list[bytes], aspect_ratio: str) -> GeneratedImage:
        api_key = os.environ.get("TOGETHER_API_KEY")
        if not api_key:
            raise ProviderError("TOGETHER_API_KEY nao configurada")

        width, height = aspect_ratio_to_size(aspect_ratio)
        try:
            resp = httpx.post(
                URL,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": MODEL,
                    "prompt": prompt,
                    "width": width,
                    "height": height,
                    "steps": 4,
                    "n": 1,
                    "response_format": "base64",
                },
                timeout=90,
            )
        except httpx.HTTPError as e:
            raise ProviderError(f"Erro de rede no Together: {e}") from e

        if resp.status_code != 200:
            raise ProviderError(f"Together retornou {resp.status_code}: {resp.text[:300]}")

        try:
            item = resp.json()["data"][0]
        except (KeyError, IndexError, ValueError) as e:
            raise ProviderError(f"Resposta inesperada do Together: {e}") from e

        if item.get("b64_json"):
            return GeneratedImage(image_bytes=base64.b64decode(item["b64_json"]))

        if item.get("url"):
            try:
                img_resp = httpx.get(item["url"], timeout=30)
            except httpx.HTTPError as e:
                raise ProviderError(f"Erro baixando imagem do Together: {e}") from e
            if img_resp.status_code != 200:
                raise ProviderError("Nao foi possivel baixar a imagem gerada pelo Together")
            return GeneratedImage(image_bytes=img_resp.content)

        raise ProviderError("Together nao retornou imagem em formato reconhecido")
