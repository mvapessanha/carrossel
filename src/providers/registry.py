"""Cadeia de fallback entre provedores de imagem: tenta em ordem (melhor -> pior,
conforme config/providers.yaml), pulando os sem chave configurada ou com cota
esgotada, ate um dar certo. Coracao do sistema.
"""
import time

from src import db
from src.config import load_config
from src.providers.base import GeneratedImage, ProviderError
from src.providers.gemini_nano_banana import GeminiNanoBananaProvider
from src.providers.hf_flux_kontext import HFFluxKontextProvider
from src.providers.pollinations_flux import PollinationsFluxProvider
from src.providers.pollinations_kontext import PollinationsKontextProvider
from src.providers.together_flux_schnell import TogetherFluxSchnellProvider
from src.quota import tracker

_PROVIDER_CLASSES = {
    "gemini_nano_banana": GeminiNanoBananaProvider,
    "hf_flux_kontext": HFFluxKontextProvider,
    "pollinations_kontext": PollinationsKontextProvider,
    "together_flux_schnell": TogetherFluxSchnellProvider,
    "pollinations_flux": PollinationsFluxProvider,
}


class AllProvidersFailed(Exception):
    def __init__(self, attempts: list[dict]):
        self.attempts = attempts
        reasons = "; ".join(f"{a['provider_id']}: {a['error']}" for a in attempts) or "nenhum provedor disponivel"
        super().__init__(f"Todos os provedores de imagem falharam ou estao sem cota — {reasons}")


PACING_SECONDS = 16.0  # espaco minimo entre chamadas reais, pra respeitar o rate
# limit do Pollinations sem cadastro (~1 req/15s) -- some ~1s de folga. Cai pra
# bem menos na pratica quando o POLLINATIONS_TOKEN (tier Seed, 1 req/5s) estiver
# configurado, mas mantemos conservador aqui ja que o registry nao sabe qual
# provedor exato sera chamado a seguir antes de tentar.


def _is_configured(entry: dict) -> bool:
    import os

    return all(os.environ.get(var) for var in entry.get("requires_env", []))


def _attempt(
    entry: dict,
    prompt: str,
    reference_images: list[bytes],
    aspect_ratio: str,
    attempts: list[dict],
    real_call_count: list[int],
):
    provider_id = entry["id"]

    if not _is_configured(entry):
        attempts.append({"provider_id": provider_id, "error": "chave de API nao configurada"})
        return None

    try:
        tracker.ensure_available(provider_id, entry["quota"])
    except tracker.QuotaExceeded:
        attempts.append({"provider_id": provider_id, "error": "cota esgotada na janela atual"})
        return None

    cost_per_image = entry.get("cost_per_image_usd")
    budget = entry.get("budget_usd")
    if cost_per_image is not None and budget is not None:
        spent_so_far = db.get_spend(provider_id)
        if spent_so_far + cost_per_image > budget:
            attempts.append(
                {
                    "provider_id": provider_id,
                    "error": f"orcamento esgotado (US${spent_so_far:.2f} de US${budget:.2f} ja gastos)",
                }
            )
            return None

    if real_call_count[0] > 0:
        time.sleep(PACING_SECONDS)
    real_call_count[0] += 1

    provider = _PROVIDER_CLASSES[entry["module"]]()
    refs = reference_images[: entry["max_reference_images"]] if entry["supports_reference"] else []

    try:
        image = provider.generate(prompt, refs, aspect_ratio)
    except ProviderError as e:
        attempts.append({"provider_id": provider_id, "error": str(e)})
        return None

    tracker.increment(provider_id, entry["quota"]["window"])
    if cost_per_image is not None:
        db.add_spend(provider_id, cost_per_image)
    return image, provider_id


SAME_PROVIDER_RETRIES = 2  # antes de trocar de IA no meio de um carrossel, insiste
# nessa mesma algumas vezes -- misturar provedor no meio quebra a consistencia
# visual/qualidade do carrossel, o que e' pior do que esperar um pouco mais.


def generate_with_fallback(
    prompt: str,
    reference_images: list[bytes],
    aspect_ratio: str = "4:5",
    preferred_provider_id: str | None = None,
) -> tuple[GeneratedImage, str]:
    """Por padrao tenta na ordem de config/providers.yaml (melhor -> pior).
    Se preferred_provider_id for passado, essa IA vira a primeira tentativa
    (respeitando a escolha da pessoa, ou a IA que ja gerou os slides
    anteriores do mesmo carrossel) -- e insiste nela por algumas tentativas
    antes de cair pra proxima, pra nao misturar qualidade/estilo no meio do
    carrossel. A cadeia continua pras demais como rede de seguranca final."""
    config = load_config()
    entries = config["image_providers"]
    if preferred_provider_id:
        entries = sorted(entries, key=lambda e: e["id"] != preferred_provider_id)

    attempts: list[dict] = []
    real_call_count = [0]
    for i, entry in enumerate(entries):
        is_preferred = preferred_provider_id and i == 0 and entry["id"] == preferred_provider_id
        tries = SAME_PROVIDER_RETRIES + 1 if is_preferred else 1
        for _ in range(tries):
            result = _attempt(entry, prompt, reference_images, aspect_ratio, attempts, real_call_count)
            if result:
                return result
    raise AllProvidersFailed(attempts)


def generate_edit_with_fallback(
    prompt: str, current_image: bytes, aspect_ratio: str = "4:5"
) -> tuple[GeneratedImage, str]:
    """Igual a generate_with_fallback, mas so tenta provedores com suporte a
    referencia — editar sempre usa a imagem atual como a nova referencia."""
    config = load_config()
    attempts: list[dict] = []
    real_call_count = [0]
    for entry in config["image_providers"]:
        if not entry["supports_reference"]:
            continue
        result = _attempt(entry, prompt, [current_image], aspect_ratio, attempts, real_call_count)
        if result:
            return result
    raise AllProvidersFailed(attempts)


def get_quota_status() -> list[dict]:
    config = load_config()
    result = []

    for entry in config["image_providers"]:
        s = tracker.status(entry["id"], entry["quota"])
        s["label"] = entry["label"]
        s["configured"] = _is_configured(entry)
        s["supports_reference"] = entry["supports_reference"]

        cost_per_image = entry.get("cost_per_image_usd")
        budget = entry.get("budget_usd")
        if cost_per_image is not None and budget is not None:
            spent = db.get_spend(entry["id"])
            s["cost_per_image_usd"] = cost_per_image
            s["budget_usd"] = budget
            s["spent_usd"] = spent
            s["remaining_usd"] = max(budget - spent, 0)
            s["is_paid"] = True
        else:
            s["is_paid"] = False

        result.append(s)

    planner_entry = config["planner"]
    planner_id = f"planner_{planner_entry['provider']}"
    planner_status = tracker.status(planner_id, planner_entry["quota"])
    planner_status["label"] = f"Planejador de conteudo ({planner_entry['provider']})"
    planner_status["configured"] = _is_configured(planner_entry)
    planner_status["supports_reference"] = False
    result.append(planner_status)

    return result
