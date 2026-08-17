"""Tests unitaires du schéma (sans base de données)."""
from __future__ import annotations

from backend.app.models import Base
from backend.app.models.enums import EventType, ListingStatus, PropertyType


def test_core_tables_registered() -> None:
    tables = set(Base.metadata.tables)
    expected = {
        "data_source",
        "ingestion_batch",
        "job_run",
        "region",
        "department",
        "commune",
        "iris",
        "transaction_dvf",
        "property",
        "listing",
        "listing_snapshot",
        "listing_check",
        "listing_event",
        "property_match_candidate",
        "dvf_match_candidate",
        "data_quality_issue",
        "dpe",
    }
    missing = expected - tables
    assert not missing, f"tables manquantes dans le metadata : {missing}"


def test_listing_unique_constraint() -> None:
    listing = Base.metadata.tables["listing"]
    uniques = {
        tuple(sorted(c.name for c in con.columns))
        for con in listing.constraints
        if con.__class__.__name__ == "UniqueConstraint"
    }
    assert ("external_listing_id", "source_id") in uniques


def test_snapshot_has_no_forbidden_price_overwrite_semantics() -> None:
    # Le prix vit dans listing_snapshot (append-only), pas comme colonne mutable de listing (§39).
    listing_cols = set(Base.metadata.tables["listing"].columns.keys())
    snapshot_cols = set(Base.metadata.tables["listing_snapshot"].columns.keys())
    assert "price_eur" not in listing_cols
    assert "price_eur" in snapshot_cols


def test_enums_values() -> None:
    assert PropertyType.HOUSE.value == "HOUSE"
    assert ListingStatus.REMOVED.value == "REMOVED"
    assert EventType.PRICE_DECREASE.value == "PRICE_DECREASE"
