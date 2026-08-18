"""Peuplement de la géolocalisation PostGIS des transactions (Phase 3).

DVF géolocalisées fournit déjà lat/lon → on matérialise la colonne `location`
(geography Point 4326) pour les requêtes spatiales (ST_DWithin/ST_Distance, §28).
Une localisation approximative ne doit jamais être présentée comme certaine (§29)."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

_BASE = """
UPDATE transaction_dvf
SET location = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography
WHERE longitude IS NOT NULL
  AND latitude IS NOT NULL
"""


def backfill_transaction_locations(
    session: Session, batch_id: int | None = None, only_missing: bool = True
) -> int:
    """Renseigne `location` (geography) depuis lat/lon.

    - `only_missing=True` (défaut) : ne touche que les lignes sans location (backfill global).
    - `only_missing=False` : RECALCULE location pour toutes les lignes visées — nécessaire au
      chargement, car un ré-import peut corriger lat/lon (sinon la géométrie resterait figée).
    Restreint à un lot d'ingestion si `batch_id` est fourni.
    Renvoie le nombre de lignes mises à jour."""
    sql = _BASE
    params: dict = {}
    if only_missing:
        sql += " AND location IS NULL"
    if batch_id is not None:
        sql += " AND ingestion_batch_id = :bid"
        params["bid"] = batch_id
    result = session.execute(text(sql), params)
    return result.rowcount or 0
