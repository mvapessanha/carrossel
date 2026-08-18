"""Extrai texto de anexos de conteudo (PDF, DOCX, TXT) pra juntar ao texto
bruto antes do planner dividir entre os slides. Imagens anexadas na caixa de
conteudo NAO passam por aqui -- entram como referencia visual extra na
chamada de geracao de imagem, nao viram texto.
"""
import io

from docx import Document
from pypdf import PdfReader


class AttachmentError(Exception):
    pass


def extract_text(filename: str, file_bytes: bytes) -> str:
    lower = filename.lower()
    if lower.endswith(".pdf"):
        return _extract_pdf(file_bytes)
    if lower.endswith(".docx"):
        return _extract_docx(file_bytes)
    if lower.endswith(".txt") or lower.endswith(".md"):
        return file_bytes.decode("utf-8", errors="ignore")
    raise AttachmentError(f"Tipo de arquivo nao suportado pra extracao de texto: {filename}")


def _extract_pdf(file_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(file_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _extract_docx(file_bytes: bytes) -> str:
    doc = Document(io.BytesIO(file_bytes))
    return "\n".join(p.text for p in doc.paragraphs)
