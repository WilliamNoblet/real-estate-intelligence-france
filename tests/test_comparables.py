"""Tests des comparables DVF (Phase 9) : fonctions pures + intégration base."""
from __future__ import annotations

import datetime as dt
import os

import pytest
from sqlalchemy import text

from analytics.comparables import _months_before, _robust_stats
from backend.app.core.db import SessionLocal, engine
from backend.app.models.enums import PropertyType


def test_robust_stats():
    s = _robust_stats([3500.0, 3600.0, 3700.0])
    assert s["count"] == 3
    assert s["median"] == 3600.0
    assert s["q1"] <= s["median"] <= s["q3"]
    assert _robust_stats([])["count"] == 0
    single = _robust_stats([4000.0])
    assert single["median"] == 4000.0 and single["q1"] == 4000.0


def test_months_before_clamps_end_of_month():
    assert _months_before(dt.date(2026, 8, 17), 24) == dt.date(2024, 8, 17)
    assert _months_before(dt.date(2026, 1, 31), 1) == dt.date(2025, 12, 31)
    # 31 mars - 1 mois -> 28 février (2026 non bissextile).
    assert _months_before(dt.date(2026, 3, 31), 1) == dt.date(2026, 2, 28)


@pytest.fixture(scope="module")
def session():
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL non défini — test base sauté.")
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1 FROM transaction_dvf LIMIT 1"))
    except Exception:  # noqa: BLE001
        pytest.skip("Base injoignable ou non migrée — test base sauté.")
    s = SessionLocal()
    yield s
    s.rollback()
    s.close()


# Commune de test isolée (99990) pour ne pas polluer les stats d'autres tests sur la base CI
# partagée : la requête de comparables est purement spatiale, l'INSEE ne l'affecte pas.
def _row(id_m, ptype, surface, ppm2, lat, lon, day_iso, insee="99990"):
    return {
        "id_mutation": id_m,
        "mutation_date": dt.date.fromisoformat(day_iso),
        "mutation_type": "Vente",
        "sale_price": ppm2 * surface,
        "property_type": ptype,
        "surface_m2": float(surface),
        "land_surface_m2": None,
        "rooms": None,
        "city": "Bordeaux",
        "postal_code": "33000",
        "insee_code": insee,
        "latitude": lat,
        "longitude": lon,
        "parcel_id": None,
        "price_per_m2": float(ppm2),
        "source_year": 2026,
        "quality_flag": None,
    }


def test_find_comparable_sales(session):
    import polars as pl

    from pipelines.dvf.load import load_transactions

    rows = [
        _row("CMP-1", "HOUSE", 105, 3500, 44.841, -0.576, "2026-06-01"),
        _row("CMP-2", "HOUSE", 100, 3700, 44.842, -0.574, "2026-05-01"),
        _row("CMP-3", "HOUSE", 110, 3600, 44.843, -0.573, "2026-04-01"),
        _row("CMP-4", "HOUSE", 105, 9000, 44.900, -0.240, "2026-06-01"),  # trop loin (spatial)
        _row("CMP-5", "HOUSE", 300, 3000, 44.841, -0.575, "2026-06-01"),  # surface hors tolérance
        _row("CMP-6", "HOUSE", 105, 4000, 44.841, -0.575, "2018-01-01"),  # trop ancien
        _row("CMP-7", "APARTMENT", 105, 5000, 44.841, -0.575, "2026-06-01"),  # mauvais type
    ]
    df = pl.DataFrame(rows)
    load_transactions(
        session, df, source_version="test-comparables",
        file_hash="comparables-hash", rows_read=len(rows), rows_rejected=0,
    )

    from analytics.comparables import find_comparable_sales

    result = find_comparable_sales(
        session, lat=44.84, lon=-0.575, property_type=PropertyType.HOUSE,
        surface_m2=105, reference_date=dt.date(2026, 8, 17), asking_price_per_m2=3702,
    )

    ids = {c["id_mutation"] for c in result["comparables"]}
    assert ids == {"CMP-1", "CMP-2", "CMP-3"}  # seuls les 3 valides
    assert result["sample_size"] == 3
    assert result["median_price_per_m2"] == 3600.0
    assert result["insufficient_sample"] is True  # 3 < min_sample (5)
    # Élargi au maximum puisqu'on n'atteint jamais l'échantillon minimal.
    assert result["radius_m_used"] == 5000
    assert result["period_months_used"] == 36
    # Écart au marché : +2,83 % vs la médiane des comparables (formulation prudente §66).
    assert result["market_gap_pct"] == 2.83
