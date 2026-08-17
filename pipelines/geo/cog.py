"""Référentiel géographique officiel (Code Officiel Géographique).

Source : geo.api.gouv.fr (API Découpage administratif, Licence Ouverte). Fournit la
hiérarchie région → département → commune avec les codes INSEE (clés de jointure pivots, §27).
Les fonctions `transform_*` sont pures (testables sur fixtures) ;
`fetch_*` et `load_cog` font le réseau."""
from __future__ import annotations

import httpx
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.models import Commune, Department, Region

GEO_API = "https://geo.api.gouv.fr"


def _get(path: str) -> list[dict]:
    resp = httpx.get(
        f"{GEO_API}{path}",
        timeout=60.0,
        follow_redirects=True,
        headers={"User-Agent": settings.user_agent},
    )
    resp.raise_for_status()
    return resp.json()


def fetch_regions() -> list[dict]:
    return _get("/regions")


def fetch_departments() -> list[dict]:
    return _get("/departements")


def fetch_communes() -> list[dict]:
    return _get("/communes?fields=nom,code,codeDepartement,codeRegion")


# --- Transformations pures (JSON API -> lignes de table) ---


def transform_regions(items: list[dict]) -> list[dict]:
    return [{"insee_code": r["code"], "name": r["nom"]} for r in items if r.get("code")]


def transform_departments(items: list[dict]) -> list[dict]:
    return [
        {"insee_code": d["code"], "name": d["nom"], "region_code": d.get("codeRegion")}
        for d in items
        if d.get("code")
    ]


def transform_communes(items: list[dict]) -> list[dict]:
    return [
        {"insee_code": c["code"], "name": c["nom"], "department_code": c.get("codeDepartement")}
        for c in items
        if c.get("code")
    ]


# --- Chargement (upsert) ---


def upsert_regions(session: Session, rows: list[dict]) -> int:
    if not rows:
        return 0
    stmt = pg_insert(Region.__table__).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["insee_code"], set_={"name": stmt.excluded.name}
    )
    session.execute(stmt)
    return len(rows)


def upsert_departments(session: Session, rows: list[dict]) -> int:
    if not rows:
        return 0
    stmt = pg_insert(Department.__table__).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["insee_code"],
        set_={"name": stmt.excluded.name, "region_code": stmt.excluded.region_code},
    )
    session.execute(stmt)
    return len(rows)


def upsert_communes(session: Session, rows: list[dict]) -> int:
    if not rows:
        return 0
    stmt = pg_insert(Commune.__table__).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["insee_code"],
        set_={"name": stmt.excluded.name, "department_code": stmt.excluded.department_code},
    )
    session.execute(stmt)
    return len(rows)


def load_cog(session: Session) -> dict:
    """Charge tout le COG (régions, départements, communes) dans l'ordre des FK."""
    n_reg = upsert_regions(session, transform_regions(fetch_regions()))
    n_dep = upsert_departments(session, transform_departments(fetch_departments()))
    n_com = upsert_communes(session, transform_communes(fetch_communes()))
    session.commit()
    return {"regions": n_reg, "departments": n_dep, "communes": n_com}
