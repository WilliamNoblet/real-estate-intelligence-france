"""Orchestrateur de collecte : relie un connecteur (ListingSourceAdapter) au moteur
d'ingestion (Phase 6). Générique et testable avec un adaptateur factice (sans réseau).

Pour chaque annonce découverte : fetch → parse → normalize → validate → ingest_observation.
Les annonces connues mais NON redécouvertes sont marquées absentes (record_missing → machine à
états). Discovery et refresh (§33) partagent ici une passe unique ; la séparation des fréquences
viendra avec le scheduler (Phase 7)."""
from __future__ import annotations

import datetime as dt
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.models import DataSource, Listing
from backend.app.models.enums import SourceType
from collectors.base import ListingSourceAdapter
from pipelines.listings.ingest import ingest_observation, record_missing

logging.basicConfig(
    level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s"
)
log = logging.getLogger("reif.collect")


def get_or_create_listing_source(session: Session, name: str) -> DataSource:
    src = session.scalar(select(DataSource).where(DataSource.name == name))
    if src is not None:
        return src
    src = DataSource(
        name=name, source_type=SourceType.LISTING_PORTAL, free=True, enabled=True
    )
    session.add(src)
    session.commit()
    return src


def run_collection(
    session: Session,
    adapter: ListingSourceAdapter,
    source_id: int,
    now: dt.datetime | None = None,
    refresh_missing: bool = True,
) -> dict:
    """Une passe de collecte : ingère les annonces découvertes, marque absentes les disparues."""
    now = now or dt.datetime.now(dt.UTC)
    discovered = list(dict.fromkeys(adapter.discover()))  # dédoublonne, garde l'ordre
    stats = {
        "discovered": len(discovered),
        "ingested": 0,
        "invalid": 0,
        "errors": 0,
        "missing": 0,
    }
    seen: set[str] = set()
    for external_id in discovered:
        try:
            normalized = adapter.normalize(adapter.parse(adapter.fetch(external_id)))
            if not adapter.validate(normalized):
                stats["invalid"] += 1
                continue
            ingest_observation(session, normalized, source_id, checked_at=now)
            # « Vue » par l'identifiant CANONIQUE (external_id du NormalizedListing), qui peut
            # différer de l'entrée de discover() (ex. URL -> id) : sinon on marquerait à tort
            # toutes les annonces comme disparues.
            seen.add(normalized.external_id)
            stats["ingested"] += 1
        except Exception:  # noqa: BLE001 — une annonce en échec ne doit pas arrêter la passe (§147)
            session.rollback()  # une erreur DB met la session en échec : la réinitialiser
            log.exception("collecte : échec sur l'annonce %s", external_id)
            stats["errors"] += 1

    if refresh_missing:
        known = session.execute(
            select(Listing.external_listing_id).where(Listing.source_id == source_id)
        ).scalars().all()
        for external_id in known:
            if external_id in seen:
                continue
            try:
                record_missing(session, source_id, external_id, now)
                stats["missing"] += 1
            except Exception:  # noqa: BLE001 — isolation : un échec ne stoppe pas le marquage
                session.rollback()
                log.exception("collecte : échec du marquage absent de %s", external_id)
                stats["errors"] += 1

    log.info("collecte terminée : %s", stats)
    return stats


def main() -> int:
    # Aucun connecteur réel n'est encore activé : le premier (Immonot) sera branché après
    # feu vert et vérification de docs/sources/immonot.md (collecte responsable, LIMITED).
    log.info(
        "Aucun connecteur d'annonces activé. Immonot (sitemap officiel, débit faible, "
        "sans donnée personnelle) sera branché après validation — voir docs/sources/immonot.md."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
