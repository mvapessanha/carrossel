"""Pollinations.ai, model=kontext — aceita ate 4 imagens de referencia.
Descoberta em ago/2026: kontext exige cadastro gratuito no tier "Seed"
(https://enter.pollinations.ai) e um token; sem POLLINATIONS_TOKEN no .env
esse provedor falha (500) e cai automaticamente pro proximo da cadeia.
Limitacao adicional: o parametro 'image' exige URL publica, entao so funciona
com referencia se PUBLIC_BASE_URL estiver configurada (ver src/storage/images.py).
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
from src.storage.images import PublicUrlUnavailable, publish_temp_reference

BASE_URL = "https://image.pollinations.ai/prompt"


class PollinationsKontextProvider(ImageProvider):
    id = "pollinations_kontext"
    label = "Pollinations (Kontext)"
    supports_reference = True
    max_reference_images = 4

    def generate(self, prompt: str, reference_images: list[bytes], aspect_ratio: str) -> GeneratedImage:
        width, height = aspect_ratio_to_size(aspect_ratio)
        params = {"model": "kontext", "width": width, "height": height, "nologo": "true"}

        if reference_images:
            try:
                urls = [publish_temp_reference(img) for img in reference_images[: self.max_reference_images]]
            except PublicUrlUnavailable as e:
                raise ProviderError(
                    "Pollinations Kontext precisa de imagens de referencia em URL publica; "
                    "configure PUBLIC_BASE_URL no .env para habilitar este provedor com referencia."
                ) from e
            params["image"] = "|".join(urls)

        headers = {}
        token = os.environ.get("POLLINATIONS_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"

        url = f"{BASE_URL}/{quote(sanitize_for_url_path(prompt))}"
        resp = get_with_retry(url, params=params, headers=headers, timeout=90)

        content_type = resp.headers.get("content-type", "")
        if "image" not in content_type:
            raise ProviderError(f"Pollinations nao retornou uma imagem (content-type: {content_type})")

        return GeneratedImage(image_bytes=resp.content, mime_type=content_type.split(";")[0] or "image/png")
