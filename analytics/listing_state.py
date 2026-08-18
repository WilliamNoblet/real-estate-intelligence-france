"""État courant d'une annonce, dérivé de ses snapshots (§111).

C'est un DÉRIVÉ reconstructible : la source de vérité reste `listing_snapshot` (§184).
Réutilise `listing_indicators` du moteur d'historisation."""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from backend.app.models import Listing, ListingSnapshot
from pipelines.listings.history import listing_indicators


def _iso(value) -> str | None:
    return value.isoformat() if value is not None else None


def _snapshots_by_listing(session: Session, listing_ids: list[int]) -> dict[int, list[dict]]:
    if not listing_ids:
        return {}
    rows = session.execute(
        select(
            ListingSnapshot.listing_id,
            ListingSnapshot.observed_at,
            ListingSnapshot.price_eur,
        )
        .where(ListingSnapshot.listing_id.in_(listing_ids))
        .order_by(ListingSnapshot.observed_at)
    ).all()
    grouped: dict[int, list[dict]] = defaultdict(list)
    for lid, observed_at, price in rows:
        grouped[lid].append(
            {"observed_at": observed_at, "price_eur": float(price) if price is not None else None}
        )
    return grouped


def _state(listing: Listing, indicators: dict) -> dict:
    return {
        "id": listing.id,
        "source_id": listing.source_id,
        "external_listing_id": listing.external_listing_id,
        "status": listing.status.value,
        "canonical_url": listing.canonical_url,
        "first_seen_at": _iso(listing.first_seen_at),
        "last_seen_at": _iso(listing.last_seen_at),
        "current_price": indicators.get("current_price"),
        "initial_price": indicators.get("initial_price"),
        "lowest_price": indicators.get("lowest_price"),
        "total_price_drop_eur": indicators.get("total_price_drop_eur"),
        "total_price_drop_pct": indicators.get("total_price_drop_pct"),
        "price_decrease_count": indicators.get("price_decrease_count"),
        "observed_days_online": indicators.get("observed_days_online"),
        "days_before_first_drop": indicators.get("days_before_first_drop"),
    }


def list_listing_states(session: Session, listings: list[Listing]) -> list[dict]:
    grouped = _snapshots_by_listing(session, [x.id for x in listings])
    return [_state(x, listing_indicators(grouped.get(x.id, []))) for x in listings]


def listing_state(session: Session, listing: Listing) -> dict:
    grouped = _snapshots_by_listing(session, [listing.id])
    return _state(listing, listing_indicators(grouped.get(listing.id, [])))


_PRICE_DROPS_SQL = text(
    """
WITH state AS (
    SELECT listing_id,
        (array_agg(price_eur ORDER BY observed_at ASC, id ASC))[1] AS initial_price,
        (array_agg(price_eur ORDER BY observed_at DESC, id DESC))[1] AS current_price,
        min(price_eur) AS lowest_price
    FROM listing_snapshot
    WHERE price_eur IS NOT NULL
    GROUP BY listing_id
)
SELECT s.listing_id, s.initial_price, s.current_price, s.lowest_price,
       l.external_listing_id, l.source_id, l.status, l.first_seen_at, l.last_seen_at,
       round((s.current_price - s.initial_price) / s.initial_price * 100, 2) AS drop_pct
FROM state s
JOIN listing l ON l.id = s.listing_id
WHERE s.initial_price > 0
  AND (s.current_price - s.initial_price) / s.initial_price * 100 <= :max_gap
ORDER BY drop_pct ASC, s.listing_id
LIMIT :limit OFFSET :offset
"""
)


def price_drops(
    session: Session, min_drop_pct: float = 5.0, limit: int = 50, offset: int = 0
) -> list[dict]:
    """Annonces triées par plus forte baisse cumulée (§107 : GET /price-drops)."""
    params = {"max_gap": -abs(min_drop_pct), "limit": limit, "offset": offset}
    out = []
    for r in session.execute(_PRICE_DROPS_SQL, params).mappings():
        out.append(
            {
                "listing_id": r["listing_id"],
                "external_listing_id": r["external_listing_id"],
                "source_id": r["source_id"],
                "status": r["status"],
                "initial_price": float(r["initial_price"]),
                "current_price": float(r["current_price"]),
                "lowest_price": float(r["lowest_price"]),
                "drop_pct": float(r["drop_pct"]),
                "first_seen_at": _iso(r["first_seen_at"]),
                "last_seen_at": _iso(r["last_seen_at"]),
            }
        )
    return out
