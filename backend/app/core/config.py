"""Configuration : secrets/environnement via .env (pydantic-settings),
paramètres non-secrets via config/*.yaml (versionnés)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

# Racine du dépôt (…/backend/app/core/config.py -> remonte de 3 niveaux).
ROOT_DIR = Path(__file__).resolve().parents[3]
CONFIG_DIR = ROOT_DIR / "config"


class Settings(BaseSettings):
    """Variables d'environnement et secrets. Jamais commité (voir .env.example)."""

    database_url: str = "postgresql+psycopg://reif:reif@localhost:5432/reif"
    log_level: str = "INFO"
    app_env: str = "local"
    # Collecte responsable : user-agent honnête et identifiable (§32).
    user_agent: str = "reif-observatory/0.1 (+https://example.org/contact)"
    collection_interval: int = 86400

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def load_yaml_config(name: str = "default") -> dict[str, Any]:
    """Charge un fichier de paramètres non-secrets depuis config/<name>.yaml."""
    path = CONFIG_DIR / f"{name}.yaml"
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


settings = get_settings()
