"""Charge le référentiel géographique et matérialise la géolocalisation des transactions.

Usage :
    python -m pipelines.geo.run            # COG (régions/dép/communes) + backfill locations
    python -m pipelines.geo.run --cog-only
    python -m pipelines.geo.run --locations-only
"""
from __future__ import annotations

import argparse
import logging

from backend.app.core.config import settings
from backend.app.core.db import SessionLocal
from pipelines.geo.cog import load_cog
from pipelines.geo.location import backfill_transaction_locations

logging.basicConfig(
    level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s"
)
log = logging.getLogger("reif.geo")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Référentiel géographique + géolocalisation DVF.")
    parser.add_argument("--cog-only", action="store_true", help="Charge seulement le COG.")
    parser.add_argument(
        "--locations-only", action="store_true", help="Backfill seulement les locations."
    )
    args = parser.parse_args(argv)

    with SessionLocal() as session:
        if not args.locations_only:
            log.info("Chargement du COG (geo.api.gouv.fr)…")
            counts = load_cog(session)
            log.info("COG chargé : %s", counts)
        if not args.cog_only:
            n = backfill_transaction_locations(session)
            session.commit()
            log.info("Géolocalisation : %d transactions mises à jour.", n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
