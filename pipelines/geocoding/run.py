"""Enrichissement géographique des annonces : ville+CP du dernier snapshot -> insee + coordonnées.

Décoré du géocodeur (injectable pour les tests). CLI : `python -m pipelines.geocoding.run`
(= `make geocode`). Aussi appelé par le scheduler (job geocode_listings)."""
from __future__ import annotations

import logging
from collections.abc import Callable

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.db import SessionLocal
from pipelines.geocoding.client import geocode_place

logging.basicConfig(
    level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s"
)
log = logging.getLogger("reif.geocode")

# Annonces sans localisation + ville/CP de leur dernier snapshot.
_PENDING_SQL = text(
    """
SELECT l.id AS listing_id, s.city, s.postal_code
FROM listing l
JOIN LATERAL (
    SELECT city, postal_code
    FROM listing_snapshot
    WHERE listing_id = l.id
    ORDER BY observed_at DESC, id DESC
    LIMIT 1
) s ON TRUE
WHERE l.location IS NULL AND s.postal_code IS NOT NULL
LIMIT :lim
"""
)

_UPDATE_SQL = text(
    """
UPDATE listing
SET latitude = :lat,
    longitude = :lon,
    location = ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
    insee_code = :insee,
    geocoding_score = :score,
    geocoded_at = now(),
    updated_at = now()
WHERE id = :id
"""
)


def geocode_pending(
    session: Session | None = None,
    geocoder: Callable[[str | None, str | None], dict | None] | None = None,
    limit: int = 1000,
) -> int:
    """Géocode les annonces en attente. Renvoie le nombre d'annonces géolocalisées."""
    geocoder = geocoder or geocode_place
    owns = session is None
    session = session or SessionLocal()
    try:
        pending = session.execute(_PENDING_SQL, {"lim": limit}).all()
        geocoded = 0
        for listing_id, city, postcode in pending:
            result = geocoder(city, postcode)
            if not result or result.get("latitude") is None:
                continue
            session.execute(
                _UPDATE_SQL,
                {
                    "lat": result["latitude"],
                    "lon": result["longitude"],
                    "insee": result.get("insee_code"),
                    "score": result.get("score"),
                    "id": listing_id,
                },
            )
            geocoded += 1
        session.commit()
        log.info("Géocodage : %d/%d annonces géolocalisées.", geocoded, len(pending))
        return geocoded
    finally:
        if owns:
            session.close()


if __name__ == "__main__":
    geocode_pending()
