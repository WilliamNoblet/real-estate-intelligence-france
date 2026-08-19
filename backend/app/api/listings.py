"""Endpoints ANNONCES — prix DEMANDÉS et leur historique (§107).

Distinct des endpoints DVF (prix payés). La source de vérité est `listing_snapshot` ;
l'état courant et les baisses sont des dérivés reconstructibles (§111, §184)."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from analytics.listing_state import list_listing_states, listing_state, price_drops
from backend.app.core.db import get_session
from backend.app.models import Listing, ListingEvent, ListingSnapshot
from backend.app.models.enums import ListingStatus
from matching.dvf_reconciliation import find_dvf_candidates

router = APIRouter(tags=["listings"])

SessionDep = Annotated[Session, Depends(get_session)]


@router.get("/listings")
def list_listings(
    session: SessionDep,
    status: ListingStatus | None = Query(default=None),
    source_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    """Annonces avec leur état courant (prix actuel/initial, baisse cumulée)."""
    stmt = select(Listing)
    if status is not None:
        stmt = stmt.where(Listing.status == status)
    if source_id is not None:
        stmt = stmt.where(Listing.source_id == source_id)
    stmt = (
        stmt.order_by(Listing.first_seen_at.desc().nullslast(), Listing.id.desc())
        .limit(limit)
        .offset(offset)
    )
    listings = list(session.execute(stmt).scalars().all())
    items = list_listing_states(session, listings)
    return {"items": items, "limit": limit, "offset": offset, "count": len(items)}


def _get_or_404(session: Session, listing_id: int) -> Listing:
    listing = session.get(Listing, listing_id)
    if listing is None:
        raise HTTPException(status_code=404, detail="Annonce introuvable")
    return listing


@router.get("/listings/{listing_id}")
def get_listing(session: SessionDep, listing_id: Annotated[int, Path()]) -> dict[str, Any]:
    return listing_state(session, _get_or_404(session, listing_id))


@router.get("/listings/{listing_id}/price-history")
def listing_price_history(
    session: SessionDep, listing_id: Annotated[int, Path()]
) -> dict[str, Any]:
    """Série temporelle des prix demandés (pour le graphique, §101)."""
    _get_or_404(session, listing_id)
    rows = session.execute(
        select(
            ListingSnapshot.observed_at,
            ListingSnapshot.price_eur,
            ListingSnapshot.price_per_m2,
        )
        .where(ListingSnapshot.listing_id == listing_id)
        .order_by(ListingSnapshot.observed_at)
    ).all()
    points = [
        {
            "observed_at": o.isoformat(),
            "price_eur": float(p) if p is not None else None,
            "price_per_m2": float(pm) if pm is not None else None,
        }
        for o, p, pm in rows
    ]
    return {"listing_id": listing_id, "points": points}


@router.get("/listings/{listing_id}/snapshots")
def listing_snapshots(
    session: SessionDep,
    listing_id: Annotated[int, Path()],
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    _get_or_404(session, listing_id)
    stmt = (
        select(ListingSnapshot)
        .where(ListingSnapshot.listing_id == listing_id)
        .order_by(ListingSnapshot.observed_at.desc(), ListingSnapshot.id.desc())
        .limit(limit)
        .offset(offset)
    )
    items = [
        {
            "observed_at": s.observed_at.isoformat(),
            "price_eur": float(s.price_eur) if s.price_eur is not None else None,
            "price_per_m2": float(s.price_per_m2) if s.price_per_m2 is not None else None,
            "surface_m2": float(s.surface_m2) if s.surface_m2 is not None else None,
            "rooms": s.rooms,
            "energy_rating": s.energy_rating,
            "agency_name": s.agency_name,
        }
        for s in session.execute(stmt).scalars().all()
    ]
    return {"listing_id": listing_id, "items": items, "limit": limit, "offset": offset}


@router.get("/listings/{listing_id}/events")
def listing_events(session: SessionDep, listing_id: Annotated[int, Path()]) -> dict[str, Any]:
    _get_or_404(session, listing_id)
    stmt = (
        select(ListingEvent)
        .where(ListingEvent.listing_id == listing_id)
        .order_by(ListingEvent.event_date, ListingEvent.id)
    )
    items = [
        {
            "event_type": e.event_type.value,
            "event_date": e.event_date.isoformat(),
            "old_value": e.old_value,
            "new_value": e.new_value,
            "metadata": e.event_metadata,
        }
        for e in session.execute(stmt).scalars().all()
    ]
    return {"listing_id": listing_id, "items": items}


@router.get("/listings/{listing_id}/dvf-candidates")
def listing_dvf_candidates(
    session: SessionDep,
    listing_id: Annotated[int, Path()],
    min_confidence: float = Query(default=0.5, ge=0, le=1),
) -> dict[str, Any]:
    """Transactions DVF potentiellement correspondantes (probabiliste, §61)."""
    _get_or_404(session, listing_id)
    candidates = find_dvf_candidates(session, listing_id, min_confidence=min_confidence)
    return {
        "listing_id": listing_id,
        "note": "Correspondances PROBABILISTES (confiance), jamais une certitude (§61, §66).",
        "candidates": candidates,
    }


@router.get("/price-drops")
def list_price_drops(
    session: SessionDep,
    min_drop_pct: float = Query(default=5.0, ge=0, description="Baisse cumulée minimale (%)"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    """Annonces triées par plus forte baisse de prix (§99, §107)."""
    items = price_drops(session, min_drop_pct=min_drop_pct, limit=limit, offset=offset)
    return {"items": items, "limit": limit, "offset": offset, "count": len(items)}
