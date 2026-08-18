"""API FastAPI. Documentation auto : /docs et /openapi.json (§109).

Phase 1 : endpoints d'amorçage (santé + catalogue des sources). Les endpoints métier
(§107 : /listings, /transactions, /markets, /price-drops…) arrivent dans les phases suivantes."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends, FastAPI
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from backend.app import __version__
from backend.app.api.dvf import router as dvf_router
from backend.app.api.listings import router as listings_router
from backend.app.core.db import engine, get_session
from backend.app.models import DataSource

app = FastAPI(
    title="Observatoire immobilier FR — API",
    version=__version__,
    description=(
        "Distingue explicitement prix DEMANDÉ (annonces) et prix de TRANSACTION (DVF). "
        "Source de vérité = les snapshots ; les tables agrégées sont des dérivés."
    ),
)

app.include_router(dvf_router)
app.include_router(listings_router)


@app.get("/", tags=["meta"])
def root() -> dict[str, Any]:
    return {
        "name": "reif — observatoire immobilier français",
        "version": __version__,
        "docs": "/docs",
    }


@app.get("/health", tags=["meta"])
def health() -> dict[str, Any]:
    """Vérifie la connectivité base + la présence de PostGIS."""
    db_ok = False
    postgis: str | None = None
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            db_ok = True
            row = conn.execute(text("SELECT extversion FROM pg_extension WHERE extname='postgis'"))
            found = row.scalar_one_or_none()
            postgis = str(found) if found is not None else None
    except Exception:  # noqa: BLE001 — la santé ne doit jamais lever
        db_ok = False
    return {"status": "ok" if db_ok else "degraded", "database": db_ok, "postgis": postgis}


@app.get("/sources", tags=["sources"])
def list_sources(session: Annotated[Session, Depends(get_session)]) -> list[dict[str, Any]]:
    """Catalogue des sources de données (§107 : GET /sources)."""
    rows = session.execute(select(DataSource).order_by(DataSource.name)).scalars().all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "type": s.source_type.value,
            "provider": s.provider,
            "license": s.license,
            "free": s.free,
            "enabled": s.enabled,
        }
        for s in rows
    ]
