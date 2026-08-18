"""API FastAPI: cria jobs de carrossel/imagem unica (pipeline de 2 chamadas:
planner de texto -> gerador de imagem com fallback), consulta a biblioteca de
jobs anteriores, edita slides, baixa resultados e mostra a cota por provedor.
"""
import time
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

load_dotenv()  # precisa rodar antes de qualquer modulo que leia GEMINI_API_KEY/GROQ_API_KEY/etc via os.environ

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src import db
from src.edit import EditError, edit_slide
from src.planner import attachments
from src.planner.content_planner import PlannerError, plan_slides
from src.prompt_builder import build_prompt
from src.providers.registry import PACING_SECONDS, AllProvidersFailed, generate_with_fallback, get_quota_status
from src.storage.export import build_job_zip
from src.storage.images import save_job_reference, save_slide_image

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
GENERATIONS_DIR = DATA_DIR / "generations"
TMP_REFS_DIR = DATA_DIR / "tmp_refs"
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
MAX_NUM_IMAGES = 10

GENERATIONS_DIR.mkdir(parents=True, exist_ok=True)
TMP_REFS_DIR.mkdir(parents=True, exist_ok=True)
db.init_db()
db.sweep_orphaned_jobs()  # jobs 'pending'/'running' de um processo anterior (servidor reiniciado) nao tem como continuar

app = FastAPI(title="Carrossel IA")
app.mount("/generations", StaticFiles(directory=str(GENERATIONS_DIR)), name="generations")
app.mount("/tmp-refs", StaticFiles(directory=str(TMP_REFS_DIR)), name="tmp_refs")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "web" / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "web" / "templates"))


def _is_image(filename: str) -> bool:
    return Path(filename).suffix.lower() in IMAGE_EXTENSIONS


def _to_url(file_path: str) -> str:
    rel = Path(file_path).resolve().relative_to(GENERATIONS_DIR.resolve())
    return f"/generations/{rel.as_posix()}"


def _job_detail(job_id: str) -> dict:
    job = db.get_job(job_id)
    if job is None:
        raise HTTPException(404, "job nao encontrado")
    slides = db.list_slides(job_id)
    refs = db.list_job_references(job_id)
    return {
        "id": job["id"],
        "mode": job["mode"],
        "num_images": job["num_images"],
        "content_text": job["content_text"],
        "design_text": job["design_text"],
        "preferred_provider": job["preferred_provider"],
        "status": job["status"],
        "error_message": job["error_message"],
        "created_at": job["created_at"],
        "slides": [
            {
                "id": s["id"],
                "idx": s["idx"],
                "role": s["role"],
                "brief_text": s["brief_text"],
                "final_prompt": s["final_prompt"],
                "image_url": _to_url(s["image_path"]) if s["image_path"] else None,
                "provider_used": s["provider_used"],
                "status": s["status"],
                "error_message": s["error_message"],
            }
            for s in slides
        ],
        "references": [
            {
                "id": r["id"],
                "kind": r["kind"],
                "url": _to_url(r["file_path"]),
                "original_filename": r["original_filename"],
            }
            for r in refs
        ],
    }


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "active_page": "create"})


@app.get("/biblioteca", response_class=HTMLResponse)
def biblioteca(request: Request):
    return templates.TemplateResponse("library.html", {"request": request, "active_page": "library"})


@app.get("/jobs")
def list_jobs():
    jobs = db.list_jobs()
    result = []
    for job in jobs:
        slides = db.list_slides(job["id"])
        thumbnail = next((s["image_path"] for s in slides if s["image_path"]), None)
        result.append(
            {
                "id": job["id"],
                "mode": job["mode"],
                "num_images": job["num_images"],
                "status": job["status"],
                "created_at": job["created_at"],
                "content_excerpt": job["content_text"][:140],
                "thumbnail_url": _to_url(thumbnail) if thumbnail else None,
            }
        )
    return result


@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    return _job_detail(job_id)


def _run_generation(
    job_id: str,
    full_content_text: str,
    design_text: str,
    num_images: int,
    preferred_provider: str | None,
    design_ref_bytes: list[bytes],
    content_image_bytes: list[bytes],
) -> None:
    """Roda no background (FastAPI BackgroundTasks): continua rodando no
    servidor mesmo se a pessoa sair da tela, fechar a aba ou navegar pra
    outro lugar -- nao depende da conexao HTTP que criou o job."""
    db.reset_cancel_flag(job_id)
    db.set_job_status(job_id, "running")

    try:
        briefs = plan_slides(full_content_text, design_text, num_images)
    except PlannerError as e:
        db.set_job_status(job_id, "error", f"Falha no planejamento de conteudo: {e}")
        return

    all_reference_bytes = design_ref_bytes + content_image_bytes
    first_slide_bytes: Optional[bytes] = None
    any_success = False
    # uma vez que uma IA gera o primeiro slide com sucesso, os proximos "travam"
    # nela (registry ainda insiste antes de trocar) -- evita misturar estilo/
    # qualidade de provedores diferentes no mesmo carrossel.
    established_provider = preferred_provider

    for brief in briefs:
        if db.is_cancel_requested(job_id):
            db.set_job_status(job_id, "cancelled", "Cancelado pelo usuario")
            return

        if brief.index > 1:
            time.sleep(PACING_SECONDS)  # espaco entre slides pra nao estourar rate limit de APIs gratuitas

        if db.is_cancel_requested(job_id):  # checa de novo apos a pausa, reduz atraso pra parar de verdade
            db.set_job_status(job_id, "cancelled", "Cancelado pelo usuario")
            return

        slide_id = db.create_slide(job_id, brief.index, brief.role, brief.text)
        prompt = build_prompt(brief, design_text, num_images)
        db.set_slide_final_prompt(slide_id, prompt)

        refs_for_call = list(all_reference_bytes)
        if first_slide_bytes is not None:
            refs_for_call.append(first_slide_bytes)  # ajuda a manter consistencia visual entre slides

        try:
            image, provider_id = generate_with_fallback(
                prompt, refs_for_call, "4:5", preferred_provider_id=established_provider
            )
        except AllProvidersFailed as e:
            db.set_slide_error(slide_id, str(e))
            continue

        image_path = save_slide_image(job_id, brief.index, image.image_bytes, image.mime_type)
        db.set_slide_result(slide_id, image_path, provider_id)
        any_success = True
        if first_slide_bytes is None:
            first_slide_bytes = image.image_bytes
            established_provider = provider_id

    db.set_job_status(job_id, "done" if any_success else "error", None if any_success else "todos os slides falharam")


def _run_edit_all(job_id: str, instruction: str) -> None:
    """Aplica a mesma instrucao de edicao em todas as imagens ja geradas do
    job, uma a uma (reaproveita edit_slide, pacing e orcamento ja existentes).
    Reusa o status 'running' do job pra bloquear criar/editar outro job
    enquanto isso roda, e o mesmo cancel_requested pra poder parar no meio."""
    db.reset_cancel_flag(job_id)
    db.set_job_status(job_id, "running")
    slides = [s for s in db.list_slides(job_id) if s["status"] == "done" and s["image_path"]]

    any_error = False
    for i, slide in enumerate(slides):
        if db.is_cancel_requested(job_id):
            db.set_job_status(job_id, "cancelled", "Edicao em lote cancelada pelo usuario")
            return
        if i > 0:
            time.sleep(PACING_SECONDS)
        try:
            edit_slide(slide["id"], instruction)
        except (EditError, AllProvidersFailed):
            any_error = True  # a imagem anterior (ja' boa) continua valendo, nao apagamos o slide

    db.set_job_status(job_id, "error" if any_error else "done", "algumas edicoes falharam" if any_error else None)


@app.post("/jobs")
def create_job(
    background_tasks: BackgroundTasks,
    content_text: str = Form(""),
    design_text: str = Form(""),
    mode: str = Form(...),
    num_images: int = Form(1),
    preferred_provider: str = Form(""),
    content_files: List[UploadFile] = File(default_factory=list),
    design_refs: List[UploadFile] = File(default_factory=list),
    reuse_reference_ids: List[str] = Form(default_factory=list),
):
    if db.count_active_jobs() > 0:
        raise HTTPException(409, "Ja existe uma geracao em andamento. Aguarde ela terminar antes de criar outra.")

    if mode not in ("single", "carousel"):
        raise HTTPException(400, "mode invalido (use 'single' ou 'carousel')")
    if mode == "single":
        num_images = 1
    if num_images < 1 or num_images > MAX_NUM_IMAGES:
        raise HTTPException(400, f"num_images deve estar entre 1 e {MAX_NUM_IMAGES}")

    extra_text_parts: list[str] = []
    content_image_bytes: list[bytes] = []
    content_image_names: list[str] = []
    for f in content_files:
        if not f.filename:
            continue  # input de arquivo vazio (nenhum arquivo selecionado) ainda chega aqui pelo form
        raw = f.file.read()
        if not raw:
            continue
        if _is_image(f.filename):
            content_image_bytes.append(raw)
            content_image_names.append(f.filename)
        else:
            try:
                extra_text_parts.append(attachments.extract_text(f.filename, raw))
            except attachments.AttachmentError as e:
                raise HTTPException(400, str(e))

    full_content_text = content_text
    if extra_text_parts:
        full_content_text = (full_content_text + "\n\n" + "\n\n".join(extra_text_parts)).strip()

    design_ref_bytes: list[bytes] = []
    design_ref_names: list[str] = []
    for f in design_refs:
        if not f.filename:
            continue  # input de arquivo vazio (nenhum arquivo selecionado) ainda chega aqui pelo form
        raw = f.file.read()
        if not raw:
            continue
        design_ref_bytes.append(raw)
        design_ref_names.append(f.filename)

    for ref_id in reuse_reference_ids:
        ref = db.get_job_reference(ref_id)
        if ref is None:
            continue
        raw = Path(ref["file_path"]).read_bytes()
        name = ref["original_filename"] or "referencia.png"
        if ref["kind"] == "design_reference":
            design_ref_bytes.append(raw)
            design_ref_names.append(name)
        else:
            content_image_bytes.append(raw)
            content_image_names.append(name)

    if not full_content_text.strip():
        raise HTTPException(400, "conteudo vazio")

    job_id = db.create_job(mode, num_images, full_content_text, design_text, preferred_provider or None)

    for i, raw in enumerate(design_ref_bytes):
        path = save_job_reference(job_id, "design_reference", i, raw, design_ref_names[i])
        db.create_job_reference(job_id, "design_reference", path, design_ref_names[i])
    for i, raw in enumerate(content_image_bytes):
        path = save_job_reference(job_id, "content_attachment", i, raw, content_image_names[i])
        db.create_job_reference(job_id, "content_attachment", path, content_image_names[i])

    background_tasks.add_task(
        _run_generation,
        job_id,
        full_content_text,
        design_text,
        num_images,
        preferred_provider or None,
        design_ref_bytes,
        content_image_bytes,
    )

    return _job_detail(job_id)


@app.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    job = db.get_job(job_id)
    if job is None:
        raise HTTPException(404, "job nao encontrado")
    if job["status"] not in ("pending", "running"):
        raise HTTPException(400, "esse job ja terminou, nao ha nada pra cancelar")
    db.request_cancel(job_id)
    return {"ok": True}


@app.post("/jobs/{job_id}/edit-all")
def edit_all(job_id: str, background_tasks: BackgroundTasks, instruction: str = Form(...)):
    job = db.get_job(job_id)
    if job is None:
        raise HTTPException(404, "job nao encontrado")
    if db.count_active_jobs() > 0:
        raise HTTPException(409, "Ja existe uma geracao/edicao em andamento. Aguarde ela terminar.")
    if not any(s["status"] == "done" and s["image_path"] for s in db.list_slides(job_id)):
        raise HTTPException(400, "esse job nao tem nenhuma imagem gerada pra editar")

    background_tasks.add_task(_run_edit_all, job_id, instruction)
    return _job_detail(job_id)


@app.post("/slides/{slide_id}/edit")
def edit_slide_endpoint(slide_id: str, instruction: str = Form(...)):
    try:
        result = edit_slide(slide_id, instruction)
    except EditError as e:
        raise HTTPException(400, str(e))
    except AllProvidersFailed as e:
        raise HTTPException(502, str(e))
    result["image_url"] = _to_url(result["image_path"])
    return result


@app.get("/jobs/{job_id}/download.zip")
def download_job_zip(job_id: str):
    job = db.get_job(job_id)
    if job is None:
        raise HTTPException(404, "job nao encontrado")
    zip_bytes = build_job_zip(job_id)
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="carrossel_{job_id}.zip"'},
    )


@app.get("/quota")
def quota():
    return get_quota_status()
