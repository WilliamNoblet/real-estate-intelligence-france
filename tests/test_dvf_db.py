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

    # Phase 3 : la géolocalisation PostGIS a été matérialisée au chargement (depuis lat/lon).
    n_loc = session.execute(
        text("SELECT count(*) FROM transaction_dvf WHERE location IS NOT NULL")
    ).scalar_one()
    assert n_loc >= 1

    # Requête spatiale ST_DWithin : autour de Bordeaux on retrouve 2024-1, pas Libourne (2024-3).
    near = (
        session.execute(
            text(
                "SELECT id_mutation FROM transaction_dvf "
                "WHERE ST_DWithin(location, "
                "ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, :r)"
            ),
            {"lon": -0.5792, "lat": 44.8378, "r": 3000},
        )
        .scalars()
        .all()
    )
    assert "2024-1" in near
    assert "2024-3" not in near


def test_reimport_refreshes_location_and_counts(session):
    """Ré-import (nouveau file_hash) avec géoloc corrigée : location recalculée, updates comptés."""
    import polars as pl

    from pipelines.dvf.load import load_transactions
    from pipelines.dvf.reconstruct import read_geodvf_csv, reconstruct

    raw = read_geodvf_csv(str(FIXTURE))
    df = reconstruct(raw, source_year=2024)
    # Déplace la maison 2024-1 d'environ 1 km au nord (44.8378 -> 44.8478).
    df = df.with_columns(
        pl.when(pl.col("id_mutation") == "2024-1")
        .then(pl.lit(44.8478))
        .otherwise(pl.col("latitude"))
        .alias("latitude")
    )

    result = load_transactions(
        session, df, source_version="test-33-2024-v2",
        file_hash="phase2-fixture-hash-v2",  # hash différent => ré-import, pas de skip
        rows_read=raw.height, rows_rejected=0,
    )
    assert result["skipped"] is False
    # Les 6 mutations existaient déjà -> 6 updates, 0 insert (compteurs corrigés).
    assert result["rows_updated"] == 6
    assert result["rows_inserted"] == 0

    # location a bien été recalculée depuis la nouvelle latitude (bug de géométrie figée corrigé).
    new_lat = session.execute(
        text("SELECT ST_Y(location::geometry) FROM transaction_dvf WHERE id_mutation = '2024-1'")
    ).scalar_one()
    assert round(new_lat, 4) == 44.8478
