"""Camada de dados Postgres (Supabase): users, jobs, slides, quota_counters.

Antes era SQLite local -- migrado pra Postgres porque hospedagem gratuita
(Render free tier) apaga o disco local a cada ~15min de inatividade. Postgres
gerenciado (Supabase) e' persistente de verdade.

user_id existe em todo registro desde o dia 1 (fixo em "local" por enquanto)
para que virar multiusuario no futuro seja trocar autenticacao, nao redesenhar o schema.
"""
import os
import uuid
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras

LOCAL_USER_ID = "local"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    mode TEXT NOT NULL,              -- 'single' | 'carousel'
    num_images INTEGER NOT NULL,
    content_text TEXT NOT NULL,
    design_text TEXT NOT NULL,
    preferred_provider TEXT,         -- IA escolhida manualmente, ou null = automatico (melhor disponivel)
    status TEXT NOT NULL,            -- 'pending' | 'running' | 'done' | 'error' | 'cancelled'
    cancel_requested INTEGER NOT NULL DEFAULT 0,  -- checado entre slides pelo background task
    error_message TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS slides (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES jobs(id),
    idx INTEGER NOT NULL,
    role TEXT,                       -- 'hook' | 'value' | 'cta' | null
    brief_text TEXT,
    final_prompt TEXT,               -- prompt exato mandado ao provedor de imagem (pra biblioteca mostrar depois)
    image_path TEXT,                 -- URL publica no Supabase Storage (nao caminho local)
    provider_used TEXT,
    status TEXT NOT NULL,            -- 'pending' | 'done' | 'error'
    error_message TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS job_references (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES jobs(id),
    kind TEXT NOT NULL,              -- 'design_reference' | 'content_attachment'
    file_path TEXT NOT NULL,         -- URL publica no Supabase Storage
    original_filename TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS quota_counters (
    provider_id TEXT NOT NULL,
    window_start TEXT NOT NULL,
    count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (provider_id, window_start)
);

-- Gasto real em dolares por provedor pago. NUNCA reseta sozinho (diferente de
-- quota_counters, que zera por janela) -- e' o total acumulado de verdade,
-- controlado pelo registry antes de cada chamada paga.
CREATE TABLE IF NOT EXISTS provider_spend (
    provider_id TEXT PRIMARY KEY,
    spent_usd REAL NOT NULL DEFAULT 0,
    call_count INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT
);
"""


class _Conn:
    """Wrapper fino pra psycopg2 se comportar como o sqlite3.Connection que o
    resto do codigo espera (.execute direto na conexao, params com '?',
    linhas acessiveis por nome de coluna) -- evita reescrever toda chamada."""

    def __init__(self):
        self._conn = psycopg2.connect(os.environ["DATABASE_URL"])
        self._cursor = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    def execute(self, query: str, params=()):
        self._cursor.execute(query.replace("?", "%s"), params)
        return self._cursor

    def executescript(self, script: str):
        self._cursor.execute(script)

    def commit(self):
        self._conn.commit()

    def close(self):
        self._cursor.close()
        self._conn.close()


def get_db() -> _Conn:
    return _Conn()


def init_db() -> None:
    conn = get_db()
    try:
        conn.executescript(_SCHEMA)
        conn.execute(
            "INSERT INTO users (id, created_at) VALUES (?, ?) ON CONFLICT (id) DO NOTHING",
            (LOCAL_USER_ID, _now()),
        )
        _migrate(conn)
        conn.commit()
    finally:
        conn.close()


def _migrate(conn: _Conn) -> None:
    """Ajustes idempotentes de schema pra bancos criados antes de uma coluna
    nova existir (evita ter que recriar o banco a cada mudanca)."""
    rows = conn.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'jobs'"
    ).fetchall()
    columns = {row["column_name"] for row in rows}
    if "preferred_provider" not in columns:
        conn.execute("ALTER TABLE jobs ADD COLUMN preferred_provider TEXT")
    if "cancel_requested" not in columns:
        conn.execute("ALTER TABLE jobs ADD COLUMN cancel_requested INTEGER NOT NULL DEFAULT 0")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return uuid.uuid4().hex


def create_job(
    mode: str,
    num_images: int,
    content_text: str,
    design_text: str,
    preferred_provider: str | None = None,
) -> str:
    job_id = new_id()
    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO jobs (id, user_id, mode, num_images, content_text, design_text, preferred_provider, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)""",
            (job_id, LOCAL_USER_ID, mode, num_images, content_text, design_text, preferred_provider, _now()),
        )
        conn.commit()
    finally:
        conn.close()
    return job_id


def set_job_status(job_id: str, status: str, error_message: str | None = None) -> None:
    conn = get_db()
    try:
        conn.execute(
            "UPDATE jobs SET status = ?, error_message = ? WHERE id = ?",
            (status, error_message, job_id),
        )
        conn.commit()
    finally:
        conn.close()


def count_active_jobs() -> int:
    """Jobs em 'pending' ou 'running' agora -- usado pra bloquear criar um job
    novo enquanto outro ainda esta em andamento."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM jobs WHERE status IN ('pending', 'running')"
        ).fetchone()
        return row["n"]
    finally:
        conn.close()


def request_cancel(job_id: str) -> None:
    conn = get_db()
    try:
        conn.execute("UPDATE jobs SET cancel_requested = 1 WHERE id = ?", (job_id,))
        conn.commit()
    finally:
        conn.close()


def is_cancel_requested(job_id: str) -> bool:
    conn = get_db()
    try:
        row = conn.execute("SELECT cancel_requested FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return bool(row and row["cancel_requested"])
    finally:
        conn.close()


def reset_cancel_flag(job_id: str) -> None:
    """Chamado no inicio de cada operacao de background nova (geracao ou
    edicao em lote) pra nao herdar um cancelamento de uma operacao anterior
    no mesmo job."""
    conn = get_db()
    try:
        conn.execute("UPDATE jobs SET cancel_requested = 0 WHERE id = ?", (job_id,))
        conn.commit()
    finally:
        conn.close()


def sweep_orphaned_jobs() -> int:
    """Chamado uma vez no startup do servidor: qualquer job 'pending'/'running'
    de um processo anterior e' necessariamente orfao (nenhuma thread deste
    processo novo pode estar rodando ele) -- marca como erro pra nao ficar
    preso pra sempre e nao bloquear jobs novos."""
    conn = get_db()
    try:
        cur = conn.execute(
            "UPDATE jobs SET status = 'error', error_message = 'Interrompido (servidor reiniciado)' "
            "WHERE status IN ('pending', 'running')"
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def get_job(job_id: str):
    conn = get_db()
    try:
        return conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    finally:
        conn.close()


def list_jobs(limit: int = 100):
    conn = get_db()
    try:
        return conn.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    finally:
        conn.close()


def create_slide(job_id: str, idx: int, role: str | None, brief_text: str) -> str:
    slide_id = new_id()
    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO slides (id, job_id, idx, role, brief_text, status, created_at)
               VALUES (?, ?, ?, ?, ?, 'pending', ?)""",
            (slide_id, job_id, idx, role, brief_text, _now()),
        )
        conn.commit()
    finally:
        conn.close()
    return slide_id


def set_slide_final_prompt(slide_id: str, final_prompt: str) -> None:
    conn = get_db()
    try:
        conn.execute("UPDATE slides SET final_prompt = ? WHERE id = ?", (final_prompt, slide_id))
        conn.commit()
    finally:
        conn.close()


def set_slide_result(slide_id: str, image_path: str, provider_used: str) -> None:
    conn = get_db()
    try:
        conn.execute(
            "UPDATE slides SET image_path = ?, provider_used = ?, status = 'done' WHERE id = ?",
            (image_path, provider_used, slide_id),
        )
        conn.commit()
    finally:
        conn.close()


def set_slide_error(slide_id: str, error_message: str) -> None:
    conn = get_db()
    try:
        conn.execute(
            "UPDATE slides SET status = 'error', error_message = ? WHERE id = ?",
            (error_message, slide_id),
        )
        conn.commit()
    finally:
        conn.close()


def list_slides(job_id: str):
    conn = get_db()
    try:
        return conn.execute(
            "SELECT * FROM slides WHERE job_id = ? ORDER BY idx ASC", (job_id,)
        ).fetchall()
    finally:
        conn.close()


def get_slide(slide_id: str):
    conn = get_db()
    try:
        return conn.execute("SELECT * FROM slides WHERE id = ?", (slide_id,)).fetchone()
    finally:
        conn.close()


def create_job_reference(job_id: str, kind: str, file_path: str, original_filename: str | None) -> str:
    ref_id = new_id()
    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO job_references (id, job_id, kind, file_path, original_filename, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (ref_id, job_id, kind, file_path, original_filename, _now()),
        )
        conn.commit()
    finally:
        conn.close()
    return ref_id


def list_job_references(job_id: str, kind: str | None = None):
    conn = get_db()
    try:
        if kind:
            return conn.execute(
                "SELECT * FROM job_references WHERE job_id = ? AND kind = ? ORDER BY created_at ASC",
                (job_id, kind),
            ).fetchall()
        return conn.execute(
            "SELECT * FROM job_references WHERE job_id = ? ORDER BY created_at ASC", (job_id,)
        ).fetchall()
    finally:
        conn.close()


def get_job_reference(ref_id: str):
    conn = get_db()
    try:
        return conn.execute("SELECT * FROM job_references WHERE id = ?", (ref_id,)).fetchone()
    finally:
        conn.close()


def get_spend(provider_id: str) -> float:
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT spent_usd FROM provider_spend WHERE provider_id = ?", (provider_id,)
        ).fetchone()
        return row["spent_usd"] if row else 0.0
    finally:
        conn.close()


def add_spend(provider_id: str, amount_usd: float) -> float:
    """Soma amount_usd ao total gasto desse provedor (nunca reseta) e devolve
    o novo total acumulado."""
    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO provider_spend (provider_id, spent_usd, call_count, updated_at)
               VALUES (?, ?, 1, ?)
               ON CONFLICT(provider_id) DO UPDATE SET
                 spent_usd = provider_spend.spent_usd + excluded.spent_usd,
                 call_count = provider_spend.call_count + 1,
                 updated_at = excluded.updated_at""",
            (provider_id, amount_usd, _now()),
        )
        conn.commit()
        row = conn.execute(
            "SELECT spent_usd FROM provider_spend WHERE provider_id = ?", (provider_id,)
        ).fetchone()
        return row["spent_usd"]
    finally:
        conn.close()
