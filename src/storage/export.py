"""Empacota os slides de um job num .zip pro download de carrossel."""
import io
import zipfile

from src import db
from src.storage.images import fetch_bytes


def build_job_zip(job_id: str) -> bytes:
    slides = db.list_slides(job_id)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for slide in slides:
            if not slide["image_path"]:
                continue
            ext = slide["image_path"].rsplit(".", 1)[-1].split("?")[0]
            image_bytes = fetch_bytes(slide["image_path"])
            zf.writestr(f"slide_{slide['idx']:02d}.{ext}", image_bytes)
    buffer.seek(0)
    return buffer.read()
