"""Armazenamento local das imagens geradas e das referencias temporarias.

Abstraido atras de funcoes simples para que trocar por armazenamento em nuvem
(quando o sistema virar produto hospedado) seja mudar so este arquivo.
"""
import os
import uuid
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
GENERATIONS_DIR = DATA_DIR / "generations"
TMP_REFS_DIR = DATA_DIR / "tmp_refs"


class PublicUrlUnavailable(Exception):
    """Levantada quando um provedor precisa de uma URL publica para a imagem
    de referencia, mas PUBLIC_BASE_URL nao esta configurada (uso local)."""


def save_slide_image(job_id: str, slide_idx: int, image_bytes: bytes, mime_type: str = "image/png") -> str:
    ext = "jpg" if "jpeg" in mime_type else "png"
    job_dir = GENERATIONS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    path = job_dir / f"slide_{slide_idx}.{ext}"
    path.write_bytes(image_bytes)
    return str(path)


def save_job_reference(job_id: str, kind: str, index: int, file_bytes: bytes, original_filename: str) -> str:
    """Persiste uma imagem de referencia (design ou anexo de conteudo) junto do
    job, pra biblioteca poder mostrar depois e pro 'realizar chamada novamente'
    conseguir reaproveitar sem a pessoa reanexar o arquivo."""
    ext = Path(original_filename).suffix or ".png"
    ref_dir = GENERATIONS_DIR / job_id / "refs"
    ref_dir.mkdir(parents=True, exist_ok=True)
    path = ref_dir / f"{kind}_{index}{ext}"
    path.write_bytes(file_bytes)
    return str(path)


def publish_temp_reference(image_bytes: bytes, mime_type: str = "image/png") -> str:
    """Salva uma imagem de referencia e devolve uma URL publica pra ela.

    So funciona se PUBLIC_BASE_URL estiver configurada no .env (ex: dominio do
    deploy, ou um tunel tipo ngrok apontando pro servidor local). Sem isso,
    provedores que exigem URL (ex: Pollinations Kontext) nao tem como buscar
    a imagem — levanta PublicUrlUnavailable, e o registry cai pro proximo
    provedor da cadeia.
    """
    base_url = os.environ.get("PUBLIC_BASE_URL")
    if not base_url:
        raise PublicUrlUnavailable("PUBLIC_BASE_URL nao configurada")

    ext = "jpg" if "jpeg" in mime_type else "png"
    TMP_REFS_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.{ext}"
    (TMP_REFS_DIR / filename).write_bytes(image_bytes)
    return f"{base_url.rstrip('/')}/tmp-refs/{filename}"
