"""Tests de la reconstruction DVF (pure, sans base de données) — le cœur métier (§94, §26)."""
from __future__ import annotations

from pathlib import Path

import pytest

from pipelines.dvf.reconstruct import count_rejected_rows, read_geodvf_csv, reconstruct

FIXTURE = Path(__file__).parent / "fixtures" / "dvf" / "sample.csv"


@pytest.fixture(scope="module")
def transactions():
    raw = read_geodvf_csv(str(FIXTURE))
    df = reconstruct(raw, source_year=2024)
    return {row["id_mutation"]: row for row in df.to_dicts()}, raw


def test_only_sales_kept(transactions):
    txns, raw = transactions
    # 6 mutations de vente ; l'Échange (2024-6) est exclu.
    assert set(txns) == {"2024-1", "2024-2", "2024-3", "2024-4", "2024-5", "2024-7"}
    assert "2024-6" not in txns
    assert count_rejected_rows(raw) == 1


def test_empty_result_is_typed_and_concatenable():
    # Régression : un fichier sans aucune vente renvoyait un frame tout-Utf8, qui cassait
    # pl.concat(..., how="vertical") avec des frames pleins (analyse multi-départements).
    import polars as pl

    raw = read_geodvf_csv(str(FIXTURE))
    full = reconstruct(raw, source_year=2024)
    empty = reconstruct(raw.filter(pl.col("nature_mutation") == "__aucune__"), source_year=2024)
    assert empty.height == 0
    assert empty.schema == full.schema  # frame vide AU BON schéma typé, pas tout-Utf8
    # Concat strict (dtypes) : ne doit plus lever SchemaError.
    assert pl.concat([full, empty], how="vertical").height == full.height


def test_valeur_fonciere_not_summed(transactions):
    txns, _ = transactions
    # 2 lignes à 385000 → 385000, PAS 770000 (§26).
    assert float(txns["2024-1"]["sale_price"]) == 385000.0


def test_single_house_metrics(transactions):
    txns, _ = transactions
    m = txns["2024-1"]
    assert m["property_type"] == "HOUSE"
    assert float(m["surface_m2"]) == 105.0          # dépendance exclue de l'habitable
    assert float(m["land_surface_m2"]) == 850.0      # parcelle unique, pas 1700
    assert m["rooms"] == 4
    assert round(float(m["price_per_m2"]), 2) == 3666.67
    assert m["quality_flag"] is None


def test_apartment(transactions):
    txns, _ = transactions
    m = txns["2024-2"]
    assert m["property_type"] == "APARTMENT"
    assert float(m["price_per_m2"]) == 4000.0
    assert m["land_surface_m2"] is None


def test_multi_bien_flagged_no_ppm2(transactions):
    txns, _ = transactions
    m = txns["2024-3"]
    assert m["property_type"] == "OTHER"
    assert float(m["surface_m2"]) == 170.0
    assert float(m["land_surface_m2"]) == 1100.0     # 2 parcelles distinctes
    assert m["price_per_m2"] is None
    assert "multi_bien" in m["quality_flag"]


def test_land_only(transactions):
    txns, _ = transactions
    m = txns["2024-4"]
    assert m["property_type"] == "LAND"
    assert m["surface_m2"] is None
    assert float(m["land_surface_m2"]) == 500.0
    assert m["price_per_m2"] is None


def test_missing_surface_flagged(transactions):
    txns, _ = transactions
    m = txns["2024-5"]
    assert m["property_type"] == "HOUSE"
    assert m["surface_m2"] is None
    assert m["price_per_m2"] is None
    assert "no_surface" in m["quality_flag"]


def test_missing_price_flagged(transactions):
    txns, _ = transactions
    m = txns["2024-7"]
    assert m["sale_price"] is None
    assert m["price_per_m2"] is None
    assert "no_price" in m["quality_flag"]
