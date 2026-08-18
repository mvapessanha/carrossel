"""Carrega config/providers.yaml (fonte unica de verdade pra ordem/limites dos
provedores de imagem e do planejador de texto). Cache simples em memoria."""
from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "providers.yaml"

_cache: dict | None = None


def load_config() -> dict:
    global _cache
    if _cache is None:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            _cache = yaml.safe_load(f)
    return _cache
