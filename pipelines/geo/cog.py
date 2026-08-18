"""Référentiel géographique officiel (Code Officiel Géographique).

Source : geo.api.gouv.fr (API Découpage administratif, Licence Ouverte). Fournit la
hiérarchie région → département → commune avec les codes INSEE (clés de jointure pivots, §27).
Les fonctions `transform_*` sont pures (testables sur fixtures) ;
`fetch_*` et `load_cog` font le réseau."""
from __future__ import annotations

import httpx
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from backend.app.core.bulk import chunked, safe_chunk_size
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


def _chunked_upsert(session: Session, table, rows: list[dict], update_cols: list[str]) -> int:
    """Upsert par lots (sous la limite de 65535 paramètres) sur la clé insee_code.
    ~35 000 communes en un seul INSERT dépasseraient la limite → découpage obligatoire."""
    if not rows:
        return 0
    for chunk in chunked(rows, safe_chunk_size(len(rows[0]))):
        stmt = pg_insert(table).values(chunk)
        stmt = stmt.on_conflict_do_update(
            index_elements=["insee_code"],
            set_={col: getattr(stmt.excluded, col) for col in update_cols},
        )
        session.execute(stmt)
    return len(rows)


def upsert_regions(session: Session, rows: list[dict]) -> int:
    return _chunked_upsert(session, Region.__table__, rows, ["name"])


def upsert_departments(session: Session, rows: list[dict]) -> int:
    return _chunked_upsert(session, Department.__table__, rows, ["name", "region_code"])


def upsert_communes(session: Session, rows: list[dict]) -> int:
    return _chunked_upsert(session, Commune.__table__, rows, ["name", "department_code"])


def load_cog(session: Session) -> dict:
    """Charge tout le COG (régions, départements, communes) dans l'ordre des FK."""
    n_reg = upsert_regions(session, transform_regions(fetch_regions()))
    n_dep = upsert_departments(session, transform_departments(fetch_departments()))
    n_com = upsert_communes(session, transform_communes(fetch_communes()))
    session.commit()
    return {"regions": n_reg, "departments": n_dep, "communes": n_com}
