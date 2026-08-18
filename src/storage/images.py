"""Armazenamento das imagens geradas e das referencias, no Supabase Storage
(bucket publico) -- precisa ser persistente de verdade porque a hospedagem
gratuita (Render) apaga o disco local a cada ~15min de inatividade.

Bonus: como tudo aqui fica com URL publica de verdade (nao um caminho local),
o Pollinations Kontext (que exige URL publica pra imagem de referencia)
passa a funcionar sempre, sem precisar de PUBLIC_BASE_URL/tunel.
"""
import os
import uuid

import httpx


def _bucket() -> str:
    return os.environ.get("SUPABASE_BUCKET", "carrossel-images")


def _supabase_url() -> str:
    return os.environ["SUPABASE_URL"].rstrip("/")


def _headers(content_type: str) -> dict:
    key = os.environ["SUPABASE_SERVICE_KEY"]
    return {
        "Authorization": f"Bearer {key}",
        "apikey": key,
        "Content-Type": content_type,
        "x-upsert": "true",
    }


def ensure_bucket() -> None:
    """Cria o bucket publico se ainda nao existir. Chamado uma vez no startup."""
    key = os.environ["SUPABASE_SERVICE_KEY"]
    resp = httpx.post(
        f"{_supabase_url()}/storage/v1/bucket",
        headers={"Authorization": f"Bearer {key}", "apikey": key},
        json={"id": _bucket(), "name": _bucket(), "public": True},
        timeout=30,
    )
    if resp.status_code not in (200, 201) and "already exists" not in resp.text.lower() and "duplicate" not in resp.text.lower():
        raise RuntimeError(f"Nao foi possivel criar o bucket do Supabase Storage: {resp.status_code} {resp.text[:200]}")


def _upload(path: str, data: bytes, mime_type: str) -> str:
    url = f"{_supabase_url()}/storage/v1/object/{_bucket()}/{path}"
    resp = httpx.post(url, headers=_headers(mime_type), content=data, timeout=60)
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Falha ao subir imagem pro Supabase Storage: {resp.status_code} {resp.text[:200]}")
    return f"{_supabase_url()}/storage/v1/object/public/{_bucket()}/{path}"


def save_slide_image(job_id: str, slide_idx: int, image_bytes: bytes, mime_type: str = "image/png") -> str:
    ext = "jpg" if "jpeg" in mime_type else "png"
    return _upload(f"{job_id}/slide_{slide_idx}.{ext}", image_bytes, mime_type)


def save_job_reference(job_id: str, kind: str, index: int, file_bytes: bytes, original_filename: str) -> str:
    """Persiste uma imagem de referencia (design ou anexo de conteudo) junto do
    job, pra biblioteca poder mostrar depois e pro 'realizar chamada novamente'
    conseguir reaproveitar sem a pessoa reanexar o arquivo."""
    ext = original_filename.rsplit(".", 1)[-1].lower() if "." in original_filename else "png"
    mime_type = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(
        ext, "application/octet-stream"
    )
    return _upload(f"{job_id}/refs/{kind}_{index}.{ext}", file_bytes, mime_type)


def publish_temp_reference(image_bytes: bytes, mime_type: str = "image/png") -> str:
    ext = "jpg" if "jpeg" in mime_type else "png"
    return _upload(f"tmp_refs/{uuid.uuid4().hex}.{ext}", image_bytes, mime_type)


def fetch_bytes(url: str) -> bytes:
    """Baixa os bytes de uma imagem ja salva (usado por editar e pelo zip do
    carrossel, que agora leem de uma URL publica em vez de disco local)."""
    resp = httpx.get(url, timeout=60)
    resp.raise_for_status()
    return resp.content
