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
    """Adaptateur factice, sans réseau. `discover()` renvoie des URLs, `normalize()` un
    identifiant canonique DIFFÉRENT — pour vérifier que le marquage des disparues compare
    les bons identifiants (sinon tout serait marqué absent à tort)."""

    source_name = "fake"

    def __init__(self, urls: list[str], price_by_id: dict[str, float], now: dt.datetime):
        self.urls = urls
        self.price_by_id = price_by_id
        self.now = now

    def discover(self) -> Iterable[str]:
        return self.urls

    def fetch(self, url: str) -> str:
        return url

    def parse(self, payload: str) -> dict:
        return {"url": payload, "id": payload.rsplit("/", 1)[-1]}

    def normalize(self, parsed: dict) -> NormalizedListing:
        cid = parsed["id"]
        return NormalizedListing(
            source="fake",
            external_id=cid,
            url=parsed["url"],
            price_eur=self.price_by_id[cid],
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

    # Passe 1 : deux annonces découvertes (par URL) et ingérées ; aucune disparue.
    t1 = dt.datetime(2027, 1, 10, tzinfo=dt.UTC)
    stats = run_collection(
        session,
        FakeAdapter(["u/FC-1", "u/FC-2"], {"FC-1": 400000, "FC-2": 300000}, t1),
        sid,
        now=t1,
    )
    assert stats["discovered"] == 2
    assert stats["ingested"] == 2
    assert stats["missing"] == 0  # id URL != id canonique : ne doit PAS tout marquer absent

    # Passe 2 : FC-1 baisse, FC-2 disparaît.
    t2 = dt.datetime(2027, 2, 10, tzinfo=dt.UTC)
    stats = run_collection(session, FakeAdapter(["u/FC-1"], {"FC-1": 380000}, t2), sid, now=t2)
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
