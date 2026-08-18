"""Contrato comum que todo provedor de imagem precisa seguir.

E' isso que permite adicionar/trocar/reordenar IAs de geracao de imagem
(config/providers.yaml) sem tocar no resto do sistema.
"""
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx


class ProviderError(Exception):
    """Levantada em qualquer falha de um provedor (rede, auth, cota, conteudo
    recusado etc.) para que o registry caia pro proximo da cadeia."""


@dataclass
class GeneratedImage:
    image_bytes: bytes
    mime_type: str = "image/png"


class ImageProvider(ABC):
    id: str
    label: str
    supports_reference: bool
    max_reference_images: int

    @abstractmethod
    def generate(
        self,
        prompt: str,
        reference_images: list[bytes],
        aspect_ratio: str,
        exact_text: str = "",
        consistency_ref_included: bool = False,
    ) -> GeneratedImage:
        """Gera uma imagem a partir do prompt + ate max_reference_images imagens
        de referencia (ja truncadas pelo chamador). Deve levantar ProviderError
        em qualquer falha, nunca deixar uma excecao generica vazar.

        exact_text: o texto literal que precisa aparecer na imagem, sem o resto
        do prompt ao redor -- so os provedores que se beneficiam disso (Gemini,
        com a tecnica de confirmar o texto num turno antes de pedir a imagem)
        precisam usar; os demais ignoram.

        consistency_ref_included: quando True, o ULTIMO item de reference_images
        e' o slide anterior do mesmo carrossel (pra consistencia visual), nao uma
        referencia de estetica do usuario -- so importa pra provedores que rotulam
        o papel de cada imagem de referencia individualmente."""


# Instagram feed/carrossel favorece retrato 4:5; usado como padrao pelos adapters.
_ASPECT_SIZES = {
    "4:5": (1080, 1350),
    "1:1": (1080, 1080),
    "9:16": (1080, 1920),
}


def aspect_ratio_to_size(aspect_ratio: str) -> tuple[int, int]:
    return _ASPECT_SIZES.get(aspect_ratio, _ASPECT_SIZES["4:5"])


def sanitize_for_url_path(text: str) -> str:
    """Descoberta em ago/2026, confirmada empiricamente: uma barra '/' literal
    no texto do prompt (ex: 'ESTILO/DESIGN') quebra o roteamento do Pollinations
    mesmo url-encoded (%2F vira separador de path no proxy deles -> 404). So
    afeta APIs que embutem o prompt na URL (path), nao no corpo da requisicao."""
    return text.replace("/", " ")


def get_with_retry(
    url: str, params: dict, headers: dict, timeout: float, retries: int = 1, backoff: float = 6.0
) -> httpx.Response:
    """GET com uma nova tentativa em caso de falha. APIs gratuitas anonimas
    (ex: Pollinations) tem instabilidade conhecida e sem SLA -- uma segunda
    tentativa depois de uma pequena espera resolve boa parte dos casos."""
    last_error = "erro desconhecido"
    for attempt in range(retries + 1):
        try:
            resp = httpx.get(url, params=params, headers=headers, timeout=timeout)
        except httpx.HTTPError as e:
            last_error = f"erro de rede: {e}"
            resp = None

        if resp is not None and resp.status_code == 200:
            return resp
        if resp is not None:
            last_error = f"retornou {resp.status_code}: {resp.text[:300]}"

        if attempt < retries:
            time.sleep(backoff)

    raise ProviderError(f"Falhou apos {retries + 1} tentativa(s) — {last_error}")
