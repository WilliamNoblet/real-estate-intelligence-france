"""Géocodage (Phase 7) : parser pur (fixture) + enrichissement base (géocodeur factice)."""
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path

import pytest
from sqlalchemy import text

from backend.app.core.db import SessionLocal, engine
from backend.app.models import DataSource
from backend.app.models.enums import PropertyType, SourceType
from collectors.base import NormalizedListing
from pipelines.geocoding.client import parse_geocode_response

FIX = Path(__file__).parent / "fixtures" / "geocoding"


def test_parse_geocode_response():
    payload = json.loads((FIX / "bordeaux.json").read_text(encoding="utf-8"))
    result = parse_geocode_response(payload)
    assert result["latitude"] == 44.851895
    assert result["longitude"] == -0.587877
    assert result["insee_code"] == "33063"
    assert round(result["score"], 3) == 0.961


def test_parse_geocode_empty():
    assert parse_geocode_response({"features": []}) is None
    assert parse_geocode_response({}) is None


def test_geocode_place_whitespace_city_falls_back_to_postcode():
    from pipelines.geocoding.client import geocode_place

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"features": []}

    class _Client:
        def __init__(self):
            self.last_params = None

        def get(self, url, params=None):
            self.last_params = params
            return _Resp()

    client = _Client()
    geocode_place("  ", "33000", client=client)  # ville faite d'espaces
    assert client.last_params["q"] == "33000"  # repli sur le code postal


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


def test_geocode_pending_enriches_listing(session):
    from pipelines.geocoding.run import geocode_pending
    from pipelines.listings.ingest import ingest_observation

    src = DataSource(
        name="test-geocode-src", source_type=SourceType.LISTING_PORTAL, free=True, enabled=True
    )
    session.add(src)
    session.commit()

    obs = NormalizedListing(
        source="test-geocode",
        external_id="GEO-1",
        price_eur=250000,
        surface_m2=90,
        property_type=PropertyType.HOUSE,
        city="Bordeaux",
        postal_code="33000",
        observed_at=dt.datetime(2027, 1, 10, tzinfo=dt.UTC),
    )
    ingest_observation(session, obs, src.id)

    # Géocodeur factice (aucun réseau) renvoyant Bordeaux.
    def fake_geocoder(city, postcode):
        assert city == "Bordeaux" and postcode == "33000"
        return {"latitude": 44.8519, "longitude": -0.5879, "insee_code": "33063", "score": 0.96}

    n = geocode_pending(session, geocoder=fake_geocoder, limit=100, source_id=src.id)
    assert n >= 1

    row = session.execute(
        text(
            "SELECT insee_code, ST_Y(location::geometry) AS lat FROM listing "
            "WHERE source_id=:s AND external_listing_id='GEO-1'"
        ),
        {"s": src.id},
    ).one()
    assert row.insee_code == "33063"
    assert round(row.lat, 4) == 44.8519
