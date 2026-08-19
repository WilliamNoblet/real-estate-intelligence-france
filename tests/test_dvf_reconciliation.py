"""Rapprochement annonce ↔ DVF : scoring PUR (calibrable isolément)."""
from __future__ import annotations

import datetime as dt

from backend.app.models.enums import PropertyType
from matching.dvf_reconciliation import _chrono_weight, score_dvf_match


def _listing(**kw):
    base = {
        "property_type": PropertyType.HOUSE,
        "surface_m2": 105,
        "asking_price": 400000,
        "removal_date": dt.date(2027, 3, 1),
        "insee_code": "33063",
    }
    base.update(kw)
    return base


def _txn(**kw):
    base = {
        "property_type": PropertyType.HOUSE,
        "surface_m2": 105,
        "sale_price": 385000,
        "mutation_date": dt.date(2027, 4, 15),
        "insee_code": "33063",
    }
    base.update(kw)
    return base


def test_strong_match_high_confidence():
    conf, feats = score_dvf_match(_listing(), _txn())
    assert conf > 0.9
    assert feats["type_match"] and feats["same_commune"]


def test_type_is_eliminatory():
    conf, feats = score_dvf_match(_listing(), _txn(property_type=PropertyType.APARTMENT))
    assert conf == 0.0
    assert feats["type_match"] is False


def test_wrong_commune_lowers_confidence():
    high, _ = score_dvf_match(_listing(), _txn())
    low, _ = score_dvf_match(_listing(), _txn(insee_code="33999"))
    assert low < high


def test_far_chronology_out_of_window():
    conf, feats = score_dvf_match(_listing(), _txn(mutation_date=dt.date(2020, 1, 1)))
    assert feats["mutation_minus_removal_days"] < -90
    # La transaction reste possible (commune/surface/prix) mais la chronologie n'apporte rien.
    high, _ = score_dvf_match(_listing(), _txn())
    assert conf < high


def test_chrono_weight():
    assert _chrono_weight(30) == 1.0
    assert _chrono_weight(-45) == 0.5
    assert _chrono_weight(1000) == 0.0


# --- Intégration base ---
import os  # noqa: E402

import pytest  # noqa: E402
from sqlalchemy import select, text  # noqa: E402

from backend.app.core.db import SessionLocal, engine  # noqa: E402
from backend.app.models import DataSource, Listing  # noqa: E402
from backend.app.models.enums import SourceType  # noqa: E402
from collectors.base import NormalizedListing  # noqa: E402


def _dvf_row(id_m, ptype, surface, price, insee, day_iso):
    return {
        "id_mutation": id_m,
        "mutation_date": dt.date.fromisoformat(day_iso),
        "mutation_type": "Vente",
        "sale_price": price,
        "property_type": ptype,
        "surface_m2": float(surface),
        "land_surface_m2": None,
        "rooms": None,
        "city": "Testcommune",
        "postal_code": "99980",
        "insee_code": insee,
        "latitude": 44.85,
        "longitude": -0.58,
        "parcel_id": None,
        "price_per_m2": round(price / surface, 2),
        "source_year": 2027,
        "quality_flag": None,
    }


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


def test_find_dvf_candidates(session):
    import polars as pl

    from matching.dvf_reconciliation import find_dvf_candidates
    from pipelines.dvf.load import load_transactions
    from pipelines.listings.ingest import ingest_observation

    # Transactions DVF isolées en commune de test 99980.
    rows = [
        _dvf_row("RECON-1", "HOUSE", 105, 385000, "99980", "2027-04-15"),  # correspond
        _dvf_row("RECON-2", "HOUSE", 300, 500000, "99980", "2020-01-01"),  # surface/date hors cible
    ]
    load_transactions(
        session, pl.DataFrame(rows), source_version="test-recon",
        file_hash="recon-hash", rows_read=len(rows), rows_rejected=0,
    )

    src = DataSource(
        name="test-recon-src", source_type=SourceType.LISTING_PORTAL, free=True, enabled=True
    )
    session.add(src)
    session.commit()

    obs = NormalizedListing(
        source="test-recon", external_id="RL-1", price_eur=400000, surface_m2=105,
        property_type=PropertyType.HOUSE, city="Testcommune", postal_code="99980",
        observed_at=dt.datetime(2027, 3, 1, tzinfo=dt.UTC),
    )
    ingest_observation(session, obs, src.id)
    listing = session.execute(
        select(Listing).where(Listing.source_id == src.id, Listing.external_listing_id == "RL-1")
    ).scalar_one()
    listing.insee_code = "99980"  # simule le géocodage
    session.commit()

    candidates = find_dvf_candidates(session, listing.id, min_confidence=0.5)
    ids = [c["id_mutation"] for c in candidates]
    assert "RECON-1" in ids
    assert "RECON-2" not in ids  # écartée (surface + chronologie)
    top = candidates[0]
    assert top["id_mutation"] == "RECON-1"
    assert top["confidence"] > 0.9
    assert top["sale_price"] == 385000

    # Annonce non géocodée -> aucun candidat.
    obs2 = NormalizedListing(
        source="test-recon", external_id="RL-2", price_eur=300000, surface_m2=80,
        property_type=PropertyType.HOUSE, observed_at=dt.datetime(2027, 3, 1, tzinfo=dt.UTC),
    )
    ingest_observation(session, obs2, src.id)
    l2 = session.execute(
        select(Listing).where(Listing.source_id == src.id, Listing.external_listing_id == "RL-2")
    ).scalar_one()
    assert find_dvf_candidates(session, l2.id) == []
