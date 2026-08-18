"""API de lecture des annonces (§107) — intégration base. Sauté en local si pas de base."""
from __future__ import annotations

import datetime as dt
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from backend.app.core.db import SessionLocal, engine
from backend.app.main import app
from backend.app.models import DataSource, Listing
from backend.app.models.enums import PropertyType, SourceType
from collectors.base import NormalizedListing
from pipelines.listings.ingest import ingest_observation

client = TestClient(app)


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


def _obs(price: float, month: int, day: int) -> NormalizedListing:
    return NormalizedListing(
        source="test-listings-api",
        external_id="LAPI-1",
        price_eur=price,
        surface_m2=105,
        property_type=PropertyType.HOUSE,
        city="Bordeaux",
        observed_at=dt.datetime(2027, month, day, tzinfo=dt.UTC),
    )


def test_listings_api(session):
    from analytics.listing_state import listing_state, price_drops

    src = DataSource(
        name="test-listings-api-src", source_type=SourceType.LISTING_PORTAL, free=True, enabled=True
    )
    session.add(src)
    session.commit()

    ingest_observation(session, _obs(420000, 1, 15), src.id)
    ingest_observation(session, _obs(399000, 2, 3), src.id)
    ingest_observation(session, _obs(385000, 2, 20), src.id)

    listing = session.execute(
        select(Listing).where(Listing.source_id == src.id, Listing.external_listing_id == "LAPI-1")
    ).scalar_one()
    lid = listing.id

    # État courant (dérivé des snapshots).
    state = listing_state(session, listing)
    assert state["current_price"] == 385000
    assert state["initial_price"] == 420000
    assert state["total_price_drop_pct"] == -8.33
    assert state["price_decrease_count"] == 2

    # /price-drops : notre annonce figure parmi les baisses >= 5 %.
    drops = price_drops(session, min_drop_pct=5.0, limit=200)
    mine = [d for d in drops if d["listing_id"] == lid]
    assert mine and mine[0]["drop_pct"] == -8.33

    # Couche HTTP.
    r = client.get(f"/listings/{lid}/price-history")
    assert r.status_code == 200
    points = r.json()["points"]
    assert len(points) == 3
    assert points[-1]["price_eur"] == 385000

    r = client.get(f"/listings/{lid}/events")
    assert r.status_code == 200
    types = [e["event_type"] for e in r.json()["items"]]
    assert types.count("PRICE_DECREASE") == 2

    r = client.get("/listings", params={"source_id": src.id})
    assert r.status_code == 200
    assert any(it["id"] == lid for it in r.json()["items"])

    assert client.get("/listings/999999999").status_code == 404
