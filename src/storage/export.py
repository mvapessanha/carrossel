"""Empacota os slides de um job num .zip pro download de carrossel."""
import io
import zipfile

from src import db


def build_job_zip(job_id: str) -> bytes:
    slides = db.list_slides(job_id)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for slide in slides:
            if not slide["image_path"]:
                continue
            arcname = slide["image_path"].split("\\")[-1].split("/")[-1]
            zf.write(slide["image_path"], arcname=f"slide_{slide['idx']:02d}_{arcname}")
    buffer.seek(0)
    return buffer.read()
