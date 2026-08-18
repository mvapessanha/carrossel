"""Contador de uso por provedor (imagem ou planner), com janela diaria/semanal.

'hard' = a API publica um teto real (ex: Gemini). 'soft' = a API nao publica
teto (ex: Pollinations), o limite aqui e' so um ritmo responsavel que a gente
mesmo impoe. As duas usam o mesmo mecanismo de contagem -- a diferenca e' so
como o numero e' rotulado pra pessoa na UI.
"""
from datetime import datetime, timezone

from src.db import get_db


class QuotaExceeded(Exception):
    def __init__(self, provider_id: str):
        self.provider_id = provider_id
        super().__init__(f"Cota esgotada para '{provider_id}' na janela atual")


def _window_start(window: str) -> str:
    now = datetime.now(timezone.utc)
    if window == "daily":
        return now.strftime("%Y-%m-%d")
    if window == "weekly":
        year, week, _ = now.isocalendar()
        return f"{year}-W{week:02d}"
    raise ValueError(f"janela de cota desconhecida: {window}")


def get_usage(provider_id: str, window: str) -> int:
    ws = _window_start(window)
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT count FROM quota_counters WHERE provider_id = ? AND window_start = ?",
            (provider_id, ws),
        ).fetchone()
        return row["count"] if row else 0
    finally:
        conn.close()


def increment(provider_id: str, window: str) -> int:
    ws = _window_start(window)
    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO quota_counters (provider_id, window_start, count) VALUES (?, ?, 1)
               ON CONFLICT(provider_id, window_start) DO UPDATE SET count = count + 1""",
            (provider_id, ws),
        )
        conn.commit()
        row = conn.execute(
            "SELECT count FROM quota_counters WHERE provider_id = ? AND window_start = ?",
            (provider_id, ws),
        ).fetchone()
        return row["count"]
    finally:
        conn.close()


def ensure_available(provider_id: str, quota_config: dict) -> None:
    """Levanta QuotaExceeded se o provedor ja bateu o limite da janela atual."""
    used = get_usage(provider_id, quota_config["window"])
    if used >= quota_config["limit"]:
        raise QuotaExceeded(provider_id)


def status(provider_id: str, quota_config: dict) -> dict:
    used = get_usage(provider_id, quota_config["window"])
    limit = quota_config["limit"]
    return {
        "provider_id": provider_id,
        "window": quota_config["window"],
        "kind": quota_config["kind"],
        "limit": limit,
        "used": used,
        "remaining": max(limit - used, 0),
    }
