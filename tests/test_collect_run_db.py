"""Orchestrateur de collecte (Phase 5→6) — intégration base avec un adaptateur factice.
Vérifie le câblage complet discover → ingest et le marquage des annonces disparues (sans réseau)."""
from __future__ import annotations

import datetime as dt
import os
from collections.abc import Iterable

import pytest
from sqlalchemy import select, text

from backend.app.core.db import SessionLocal, engine
from backend.app.models import Listing
from backend.app.models.enums import PropertyType
from collectors.base import ListingSourceAdapter, NormalizedListing
from collectors.run import get_or_create_listing_source, run_collection


class FakeAdapter(ListingSourceAdapter):
    """Adaptateur factice : discovery et prix contrôlés, aucune requête réseau."""

    source_name = "fake"

    def __init__(self, ids: list[str], prices: dict[str, float], now: dt.datetime):
        self.ids = ids
        self.prices = prices
        self.now = now

    def discover(self) -> Iterable[str]:
        return self.ids

    def fetch(self, external_id: str) -> str:
        return external_id

    def parse(self, payload: str) -> dict:
        return {"id": payload}

    def normalize(self, parsed: dict) -> NormalizedListing:
        eid = parsed["id"]
        return NormalizedListing(
            source="fake",
            external_id=eid,
            price_eur=self.prices[eid],
            surface_m2=100,
            property_type=PropertyType.HOUSE,
            observed_at=self.now,
        )


@pytest.fixture(scope="module")
def session():
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL non défini — test base sauté.")
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1 FROM listing LIMIT 1"))
    except Exception:  # noqa: BLE001
        pytest.skip("Base injoignable ou non migrée — test base sauté.")
    s = SessionLocal()
    yield s
    s.rollback()
    s.close()


def test_run_collection_lifecycle(session):
    src = get_or_create_listing_source(session, "fake-collect-src")
    sid = src.id

    # Passe 1 : deux annonces découvertes et ingérées.
    t1 = dt.datetime(2027, 1, 10, tzinfo=dt.UTC)
    stats = run_collection(
        session, FakeAdapter(["FC-1", "FC-2"], {"FC-1": 400000, "FC-2": 300000}, t1), sid, now=t1
    )
    assert stats["discovered"] == 2
    assert stats["ingested"] == 2
    assert stats["missing"] == 0

    # Passe 2 : FC-1 baisse, FC-2 disparaît.
    t2 = dt.datetime(2027, 2, 10, tzinfo=dt.UTC)
    stats = run_collection(session, FakeAdapter(["FC-1"], {"FC-1": 380000}, t2), sid, now=t2)
    assert stats["ingested"] == 1
    assert stats["missing"] == 1

    l1 = session.execute(
        select(Listing).where(Listing.source_id == sid, Listing.external_listing_id == "FC-1")
    ).scalar_one()
    events = session.execute(
        text("SELECT event_type FROM listing_event WHERE listing_id=:l"), {"l": l1.id}
    ).scalars().all()
    assert "PRICE_DECREASE" in events

    l2 = session.execute(
        select(Listing).where(Listing.source_id == sid, Listing.external_listing_id == "FC-2")
    ).scalar_one()
    assert l2.status.value == "MISSING"  # 1 absence < seuil (3)
