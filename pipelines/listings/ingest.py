"""Persistance d'une observation d'annonce (Phase 6).

Transforme un `NormalizedListing` en base : listing → listing_check → (listing_snapshot si
changement significatif) → listing_event, et applique la machine à états.

Invariants (§39, §41, §86) :
- un snapshot n'est créé QUE si le payload_hash change (sinon on maj last_seen/last_checked) ;
- les snapshots sont append-only : jamais d'écrasement de prix ;
- une annonce absente n'est jamais « vendue » (MISSING → REMOVED après N vérifications, §49-50)."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import load_yaml_config
from backend.app.models import Listing, ListingCheck, ListingEvent, ListingSnapshot
from backend.app.models.enums import EventType, HistoryOrigin, ListingStatus
from collectors.base import NormalizedListing
from pipelines.listings.history import (
    compute_payload_hash,
    diff_events,
    normalized_text_hash,
    transition,
)

PIPELINE_VERSION = "listings-0.1"


def _missing_threshold() -> int:
    cfg = load_yaml_config("default").get("historisation", {})
    return int(cfg.get("missing_before_removed", 3))


def _get_listing(session: Session, source_id: int, external_id: str) -> Listing | None:
    return session.scalar(
        select(Listing).where(
            Listing.source_id == source_id, Listing.external_listing_id == external_id
        )
    )


def _latest_snapshot(session: Session, listing_id: int) -> ListingSnapshot | None:
    return session.scalar(
        select(ListingSnapshot)
        .where(ListingSnapshot.listing_id == listing_id)
        .order_by(ListingSnapshot.observed_at.desc(), ListingSnapshot.id.desc())
        .limit(1)
    )


def _consecutive_missing(session: Session, listing_id: int) -> int:
    """Nombre de vérifications négatives consécutives les plus récentes (§50)."""
    founds = session.execute(
        select(ListingCheck.found)
        .where(ListingCheck.listing_id == listing_id)
        .order_by(ListingCheck.checked_at.desc(), ListingCheck.id.desc())
    ).scalars().all()
    count = 0
    for found in founds:
        if found:
            break
        count += 1
    return count


def _make_snapshot(listing_id: int, n: NormalizedListing, payload_hash: str) -> ListingSnapshot:
    price_per_m2 = None
    if n.price_eur and n.surface_m2 and n.surface_m2 > 0:
        price_per_m2 = round(n.price_eur / n.surface_m2, 2)
    return ListingSnapshot(
        listing_id=listing_id,
        observed_at=n.observed_at,
        price_eur=n.price_eur,
        price_per_m2=price_per_m2,
        title=n.title,
        surface_m2=n.surface_m2,
        land_surface_m2=n.land_surface_m2,
        rooms=n.rooms,
        bedrooms=n.bedrooms,
        energy_rating=n.energy_rating,
        ghg_rating=n.ghg_rating,
        seller_type=n.seller_type,
        agency_name=n.agency_name,
        city=n.city,
        postal_code=n.postal_code,
        latitude=n.latitude,
        longitude=n.longitude,
        photo_count=n.photo_count,
        description_hash=normalized_text_hash(n.description),
        photo_fingerprint=n.photo_fingerprint,
        payload_hash=payload_hash,
        pipeline_version=PIPELINE_VERSION,
    )


def _snapshot_to_significant(snap: ListingSnapshot) -> dict:
    """Champs signifiants d'un snapshot (pour le diff). description_hash est déjà stocké."""
    return {
        "price_eur": float(snap.price_eur) if snap.price_eur is not None else None,
        "surface_m2": float(snap.surface_m2) if snap.surface_m2 is not None else None,
        "land_surface_m2": (
            float(snap.land_surface_m2) if snap.land_surface_m2 is not None else None
        ),
        "rooms": snap.rooms,
        "bedrooms": snap.bedrooms,
        "energy_rating": snap.energy_rating,
        "ghg_rating": snap.ghg_rating,
        "title": snap.title,
        "description_hash": snap.description_hash,
        "agency_name": snap.agency_name,
    }


def _event_from_diff(listing_id: int, snapshot_id: int | None, ev: dict) -> ListingEvent:
    return ListingEvent(
        listing_id=listing_id,
        snapshot_id=snapshot_id,
        event_type=ev["event_type"],
        event_date=ev["event_date"],
        old_value=ev["old_value"],
        new_value=ev["new_value"],
        event_metadata=ev["metadata"],
    )


def ingest_observation(
    session: Session,
    normalized: NormalizedListing,
    source_id: int,
    checked_at: dt.datetime | None = None,
) -> dict:
    """Enregistre une annonce TROUVÉE. Crée le listing au besoin, un check, et un snapshot +
    des événements uniquement si les champs signifiants ont changé."""
    checked_at = checked_at or normalized.observed_at
    payload_hash = compute_payload_hash(normalized)
    result: dict = {"created": False, "snapshot_created": False, "events": []}

    listing = _get_listing(session, source_id, normalized.external_id)

    if listing is None:
        listing = Listing(
            source_id=source_id,
            external_listing_id=normalized.external_id,
            canonical_url=normalized.url,
            status=ListingStatus.ACTIVE,
            property_type=normalized.property_type,
            first_seen_at=normalized.observed_at,
            last_seen_at=normalized.observed_at,
            last_checked_at=checked_at,
            source_publication_date=normalized.source_publication_date,
            history_origin=HistoryOrigin.OBSERVED,
        )
        session.add(listing)
        session.flush()
        result["created"] = True
        session.add(
            ListingCheck(
                listing_id=listing.id, checked_at=checked_at, found=True, parser_success=True
            )
        )
        snap = _make_snapshot(listing.id, normalized, payload_hash)
        session.add(snap)
        session.flush()
        result["snapshot_created"] = True
        session.add(
            ListingEvent(
                listing_id=listing.id,
                event_type=EventType.LISTING_DISCOVERED,
                event_date=normalized.observed_at,
                new_value=str(normalized.price_eur) if normalized.price_eur is not None else None,
                snapshot_id=snap.id,
            )
        )
        result["events"].append(EventType.LISTING_DISCOVERED.value)
        session.commit()
        return result

    # Annonce déjà connue.
    session.add(
        ListingCheck(listing_id=listing.id, checked_at=checked_at, found=True, parser_success=True)
    )
    prev = _latest_snapshot(session, listing.id)
    new_snap: ListingSnapshot | None = None
    if prev is None or prev.payload_hash != payload_hash:
        new_snap = _make_snapshot(listing.id, normalized, payload_hash)
        session.add(new_snap)
        session.flush()
        result["snapshot_created"] = True
        if prev is not None:
            for ev in diff_events(
                _snapshot_to_significant(prev), normalized, normalized.observed_at
            ):
                session.add(_event_from_diff(listing.id, new_snap.id, ev))
                result["events"].append(ev["event_type"].value)

    # Machine à états : observation trouvée.
    new_status, status_event = transition(listing.status, True, 0, _missing_threshold())
    if status_event is not None:
        session.add(
            ListingEvent(
                listing_id=listing.id,
                event_type=status_event,
                event_date=checked_at,
                old_value=listing.status.value,
                new_value=new_status.value,
                snapshot_id=new_snap.id if new_snap else None,
            )
        )
        result["events"].append(status_event.value)
    listing.status = new_status
    listing.last_seen_at = normalized.observed_at
    listing.last_checked_at = checked_at
    session.commit()
    return result


def record_missing(
    session: Session, source_id: int, external_id: str, checked_at: dt.datetime
) -> dict:
    """Vérification NÉGATIVE (annonce introuvable). Fait avancer la machine à états."""
    listing = _get_listing(session, source_id, external_id)
    if listing is None:
        return {"unknown": True}

    session.add(ListingCheck(listing_id=listing.id, checked_at=checked_at, found=False))
    session.flush()
    n_missing = _consecutive_missing(session, listing.id)
    new_status, status_event = transition(listing.status, False, n_missing, _missing_threshold())

    events: list[str] = []
    if status_event is not None:
        session.add(
            ListingEvent(
                listing_id=listing.id,
                event_type=status_event,
                event_date=checked_at,
                old_value=listing.status.value,
                new_value=new_status.value,
            )
        )
        events.append(status_event.value)
    listing.status = new_status
    listing.last_checked_at = checked_at
    session.commit()
    return {"status": new_status.value, "consecutive_missing": n_missing, "events": events}
