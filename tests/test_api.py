"""Tests de l'API sans dépendance à la base (routes meta)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app import __version__
from backend.app.main import app

client = TestClient(app)


def test_root() -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["version"] == __version__
    assert body["docs"] == "/docs"


def test_health_never_raises() -> None:
    # /health ne doit jamais lever, même base indisponible (renvoie 'degraded').
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] in {"ok", "degraded"}


def test_openapi_exposed() -> None:
    assert client.get("/openapi.json").status_code == 200
