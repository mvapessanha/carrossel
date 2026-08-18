"""Pollinations.ai, model=flux — gratis, sem chave, so texto->imagem (sem
referencia). Ultimo recurso da cadeia de fallback: sempre funciona local (sem
cadastro, ~1 req/15s), nao depende de PUBLIC_BASE_URL. Se POLLINATIONS_TOKEN
estiver configurado (cadastro no tier "Seed"), usa o ritmo mais rapido dele.
"""
import os
from urllib.parse import quote

from src.providers.base import (
    GeneratedImage,
    ImageProvider,
    ProviderError,
    aspect_ratio_to_size,
    get_with_retry,
    sanitize_for_url_path,
)

BASE_URL = "https://image.pollinations.ai/prompt"


class PollinationsFluxProvider(ImageProvider):
    id = "pollinations_flux"
    label = "Pollinations (Flux)"
    supports_reference = False
    max_reference_images = 0

    def generate(self, prompt: str, reference_images: list[bytes], aspect_ratio: str) -> GeneratedImage:
        width, height = aspect_ratio_to_size(aspect_ratio)
        headers = {}
        token = os.environ.get("POLLINATIONS_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"

        url = f"{BASE_URL}/{quote(sanitize_for_url_path(prompt))}"
        resp = get_with_retry(
            url,
            params={"model": "flux", "width": width, "height": height, "nologo": "true"},
            headers=headers,
            timeout=90,
        )

        content_type = resp.headers.get("content-type", "")
        if "image" not in content_type:
            raise ProviderError(f"Pollinations nao retornou uma imagem (content-type: {content_type})")

        return GeneratedImage(image_bytes=resp.content, mime_type=content_type.split(";")[0] or "image/png")
