"""Tests du moteur d'historisation (Phase 6) — pur, sans réseau ni base.
Reproduit l'exemple du cahier des charges (§47)."""
from __future__ import annotations

import datetime as dt

from backend.app.models.enums import EventType, ListingStatus
from pipelines.listings.history import (
    compute_payload_hash,
    diff_events,
    has_meaningful_change,
    listing_indicators,
    normalized_text_hash,
    transition,
)


def _d(year: int, month: int, day: int) -> dt.datetime:
    return dt.datetime(year, month, day, tzinfo=dt.UTC)


SNAPSHOTS = [
    {"observed_at": _d(2027, 1, 15), "price_eur": 420000},
    {"observed_at": _d(2027, 2, 3), "price_eur": 399000},
    {"observed_at": _d(2027, 2, 20), "price_eur": 385000},
]


def test_indicators_master_example():
    ind = listing_indicators(SNAPSHOTS)
    assert ind["initial_price"] == 420000
    assert ind["current_price"] == 385000
    assert ind["lowest_price"] == 385000
    assert ind["highest_price"] == 420000
    assert ind["total_price_drop_eur"] == -35000
    assert ind["total_price_drop_pct"] == -8.33
    assert ind["price_change_count"] == 2
    assert ind["price_decrease_count"] == 2
    assert ind["price_increase_count"] == 0
    assert ind["days_before_first_drop"] == 19
    assert ind["observed_days_online"] == 36


def test_price_decrease_event():
    ev = diff_events({"price_eur": 420000}, {"price_eur": 399000}, _d(2027, 2, 3))
    assert len(ev) == 1
    assert ev[0]["event_type"] == EventType.PRICE_DECREASE
    assert ev[0]["metadata"]["variation_eur"] == -21000
    assert ev[0]["metadata"]["variation_pct"] == -5.0


def test_price_increase_event():
    ev = diff_events({"price_eur": 385000}, {"price_eur": 400000}, _d(2027, 3, 1))
    assert ev[0]["event_type"] == EventType.PRICE_INCREASE
    assert ev[0]["metadata"]["variation_eur"] == 15000


def test_no_change_is_stable():
    # Description équivalente après normalisation → aucun changement significatif (§56).
    a = {"price_eur": 385000, "surface_m2": 105, "description": "Belle maison"}
    b = {"price_eur": 385000, "surface_m2": 105, "description": "belle   maison !"}
    assert compute_payload_hash(a) == compute_payload_hash(b)
    assert has_meaningful_change(a, b) is False
    assert diff_events(a, b, _d(2027, 3, 1)) == []


def test_meaningful_change_on_price():
    assert has_meaningful_change({"price_eur": 420000}, {"price_eur": 399000}) is True


def test_description_changed_event():
    ev = diff_events(
        {"description": "maison avec jardin"},
        {"description": "maison renovee avec grand jardin"},
        _d(2027, 3, 1),
    )
    assert any(e["event_type"] == EventType.DESCRIPTION_CHANGED for e in ev)


def test_property_details_changed_event():
    ev = diff_events(
        {"surface_m2": 105, "rooms": 4}, {"surface_m2": 110, "rooms": 5}, _d(2027, 3, 1)
    )
    assert any(e["event_type"] == EventType.PROPERTY_DETAILS_CHANGED for e in ev)


def test_normalized_text_hash():
    assert normalized_text_hash("Belle Maison !!") == normalized_text_hash("belle   maison")
    assert normalized_text_hash("") is None
    assert normalized_text_hash(None) is None


def test_state_machine_missing_to_removed_to_reappeared():
    # ACTIVE -> MISSING au 1er échec, REMOVED au 3e (seuil=3) ; une absence != vente (§49).
    assert transition(ListingStatus.ACTIVE, False, 1, 3) == (
        ListingStatus.MISSING, EventType.LISTING_MISSING
    )
    assert transition(ListingStatus.MISSING, False, 2, 3) == (ListingStatus.MISSING, None)
    assert transition(ListingStatus.MISSING, False, 3, 3) == (
        ListingStatus.REMOVED, EventType.LISTING_REMOVED
    )
    # REMOVED -> REAPPEARED si on la retrouve.
    assert transition(ListingStatus.REMOVED, True, 0, 3) == (
        ListingStatus.REAPPEARED, EventType.LISTING_REAPPEARED
    )
    # Trouvée et déjà active : reste ACTIVE, sans événement.
    assert transition(ListingStatus.ACTIVE, True, 0, 3) == (ListingStatus.ACTIVE, None)
