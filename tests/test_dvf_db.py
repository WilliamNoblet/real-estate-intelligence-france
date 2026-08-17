"""Test d'intégration DVF avec base (chargement idempotent + stats de marché).

Nécessite une base PostgreSQL/PostGIS migrée (DATABASE_URL). Exécuté en CI ; sauté en local
si la base est injoignable."""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy import text

from backend.app.core.db import SessionLocal, engine
from backend.app.models.enums import PropertyType

FIXTURE = Path(__file__).parent / "fixtures" / "dvf" / "sample.csv"


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


def test_load_then_stats(session):
    from analytics.dvf_stats import commune_stats
    from pipelines.dvf.load import load_transactions
    from pipelines.dvf.reconstruct import count_rejected_rows, read_geodvf_csv, reconstruct

    raw = read_geodvf_csv(str(FIXTURE))
    df = reconstruct(raw, source_year=2024)

    result = load_transactions(
        session,
        df,
        source_version="test-33-2024",
        file_hash="phase2-fixture-hash",
        rows_read=raw.height,
        rows_rejected=count_rejected_rows(raw),
    )
    assert result["skipped"] is False
    assert result["rows_inserted"] == 6  # 6 mutations de vente

    # Idempotence : relancer le même fichier (même hash) est ignoré, sans doublon.
    again = load_transactions(
        session, df, source_version="test-33-2024", file_hash="phase2-fixture-hash",
        rows_read=raw.height, rows_rejected=count_rejected_rows(raw),
    )
    assert again["skipped"] is True

    # Maisons à Bordeaux (33063) avec €/m² exploitable : seule la mutation 2024-1 (3666.67).
    stats = commune_stats(session, "33063", PropertyType.HOUSE)
    assert stats["sample_size"] == 1
    assert stats["median_price_per_m2"] == 3666.67
    assert stats["insufficient_sample"] is True  # < min_sample (5)
