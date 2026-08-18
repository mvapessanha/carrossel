"""Editar um slide ja gerado: a imagem atual vira a nova referencia e roda de
novo, so pelos provedores com suporte a referencia (Gemini/Kontext) -- so
esses conseguem partir de uma imagem existente. Uma nova imagem e' salva
(URL antiga no Supabase Storage fica orfa, mas isso e' aceitavel pro escopo atual).
"""
from src import db
from src.providers.registry import generate_edit_with_fallback
from src.storage.images import fetch_bytes, save_slide_image


class EditError(Exception):
    pass


def edit_slide(slide_id: str, instruction: str, aspect_ratio: str = "4:5") -> dict:
    slide = db.get_slide(slide_id)
    if slide is None:
        raise EditError("Slide nao encontrado")
    if not slide["image_path"]:
        raise EditError("Slide ainda nao tem imagem gerada")

    current_bytes = fetch_bytes(slide["image_path"])
    prompt = (
        "Edite esta imagem conforme a instrucao a seguir, mantendo o restante "
        f"do design como esta.\n[INSTRUCAO DE EDICAO]\n{instruction}"
    )

    image, provider_id = generate_edit_with_fallback(
        prompt, current_bytes, aspect_ratio, exact_text=slide["brief_text"] or ""
    )

    new_path = save_slide_image(slide["job_id"], slide["idx"], image.image_bytes, image.mime_type)
    db.set_slide_result(slide_id, new_path, provider_id)
    db.set_slide_final_prompt(slide_id, prompt)

    return {"slide_id": slide_id, "image_path": new_path, "provider_used": provider_id}
