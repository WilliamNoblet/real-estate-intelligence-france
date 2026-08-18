"""Cycle de vie complet d'une annonce en base (Phase 6) — intégration PostgreSQL.

Vérifie le critère du cahier des charges : 420000 -> 399000 crée un PRICE_DECREASE, et la
machine à états ACTIVE -> MISSING -> REMOVED -> REAPPEARED. Sauté en local si pas de base."""
from __future__ import annotations

import datetime as dt
import os

import pytest
from sqlalchemy import text

from backend.app.core.db import SessionLocal, engine
from backend.app.models import DataSource
from backend.app.models.enums import PropertyType, SourceType
from collectors.base import NormalizedListing
from pipelines.listings.ingest import ingest_observation, record_missing


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


def _obs(price: float, month: int, day: int, **kw) -> NormalizedListing:
    return NormalizedListing(
        source="test-portal",
        external_id="L1",
        price_eur=price,
        surface_m2=105,
        property_type=PropertyType.HOUSE,
        observed_at=dt.datetime(2027, month, day, tzinfo=dt.UTC),
        **kw,
    )


def test_full_lifecycle(session):
    src = DataSource(
        name="test-portal-lifecycle", source_type=SourceType.LISTING_PORTAL, free=True, enabled=True
    )
    session.add(src)
    session.commit()
    sid = src.id

    # 1) Découverte à 420 000 €.
    r = ingest_observation(session, _obs(420000, 1, 15), sid)
    assert r["created"] is True
    assert r["snapshot_created"] is True
    assert "LISTING_DISCOVERED" in r["events"]

    lid = session.execute(
        text("SELECT id FROM listing WHERE source_id=:s AND external_listing_id='L1'"),
        {"s": sid},
    ).scalar_one()

    # 2) Même prix -> aucun nouveau snapshot (seul last_seen/last_checked bouge).
    r = ingest_observation(session, _obs(420000, 1, 20), sid)
    assert r["snapshot_created"] is False

    # 3) Baisse à 399 000 € -> nouveau snapshot + PRICE_DECREASE (critère Phase 6).
    r = ingest_observation(session, _obs(399000, 2, 3), sid)
    assert r["snapshot_created"] is True
    assert "PRICE_DECREASE" in r["events"]

    # 4) Baisse à 385 000 €.
    r = ingest_observation(session, _obs(385000, 2, 20), sid)
    assert "PRICE_DECREASE" in r["events"]

    # 5) Trois vérifications négatives -> REMOVED au 3e (seuil par défaut = 3).
    record_missing(session, sid, "L1", dt.datetime(2027, 3, 1, tzinfo=dt.UTC))
    record_missing(session, sid, "L1", dt.datetime(2027, 3, 2, tzinfo=dt.UTC))
    r = record_missing(session, sid, "L1", dt.datetime(2027, 3, 3, tzinfo=dt.UTC))
    assert r["status"] == "REMOVED"
    assert "LISTING_REMOVED" in r["events"]

    # 6) L'annonce revient -> REAPPEARED (même prix -> pas de nouveau snapshot).
    r = ingest_observation(session, _obs(385000, 4, 1), sid)
    assert "LISTING_REAPPEARED" in r["events"]
    assert r["snapshot_created"] is False

    # Bilan : 3 snapshots (420k, 399k, 385k), statut final REAPPEARED.
    n_snap = session.execute(
        text("SELECT count(*) FROM listing_snapshot WHERE listing_id=:l"), {"l": lid}
    ).scalar_one()
    assert n_snap == 3

    status = session.execute(
        text("SELECT status FROM listing WHERE id=:l"), {"l": lid}
    ).scalar_one()
    assert status == "REAPPEARED"

    # La 1re baisse a bien enregistré une variation de -21 000 €.
    variation = session.execute(
        text(
            "SELECT (event_metadata->>'variation_eur')::numeric FROM listing_event "
            "WHERE listing_id=:l AND event_type='PRICE_DECREASE' ORDER BY id LIMIT 1"
        ),
        {"l": lid},
    ).scalar_one()
    assert float(variation) == -21000.0
