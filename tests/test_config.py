"""Tests de chargement de la configuration non-secrète."""
from __future__ import annotations

from backend.app.core.config import load_yaml_config


def test_default_config_loads() -> None:
    cfg = load_yaml_config("default")
    assert cfg["pilot"]["department"] == "33"
    # Les poids de matching somment à 1.0 (§58).
    weights = cfg["matching"]["weights"]
    assert abs(sum(weights.values()) - 1.0) < 1e-9
