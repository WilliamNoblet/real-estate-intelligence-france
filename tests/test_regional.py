"""Analyse régionale DVF (analytics.regional) : agrégation PURE sur frame synthétique.

Aucun réseau, aucune base : on vérifie les règles (exclusion des €/m² aberrants et des
types non-logement, médianes robustes, volumes, seuil d'échantillon communal)."""

from __future__ import annotations

import polars as pl

from analytics.regional import REGIONS, clean_ppm2, regional_summary, stats_ppm2


def _frame() -> pl.DataFrame:
    rows = [
        # dep, year, property_type, price_per_m2, insee_code, city, quality_flag
        ("35", 2024, "HOUSE", 3000.0, "35238", "Rennes", None),
        ("35", 2024, "HOUSE", 4000.0, "35238", "Rennes", None),
        ("35", 2024, "HOUSE", 5000.0, "35238", "Rennes", None),
        ("22", 2024, "APARTMENT", 1500.0, "22278", "Saint-Brieuc", None),
        ("22", 2024, "APARTMENT", 2000.0, "22278", "Saint-Brieuc", None),
        ("22", 2024, "LAND", None, "22278", "Saint-Brieuc", None),  # exclu du €/m²
        ("22", 2024, "HOUSE", 50000.0, "22278", "Saint-Brieuc", "extreme_ppm2"),  # aberrant, exclu
    ]
    cols = ["dep", "year", "property_type", "price_per_m2", "insee_code", "city", "quality_flag"]
    return pl.DataFrame(rows, schema=cols, orient="row")


def test_clean_ppm2_exclut_aberrants_et_non_logement():
    clean = clean_ppm2(_frame())
    assert clean.height == 5  # 3 maisons Rennes + 2 apparts St-Brieuc (land + extreme exclus)
    assert clean["price_per_m2"].max() == 5000.0


def test_stats_ppm2_robuste():
    s = stats_ppm2(clean_ppm2(_frame()))
    assert s["n"] == 5
    assert s["median"] == 3000.0  # médiane de [1500,2000,3000,4000,5000]


def test_stats_ppm2_vide():
    assert stats_ppm2(pl.DataFrame(schema={"price_per_m2": pl.Float64}))["n"] == 0


def test_regional_summary():
    summary = regional_summary(_frame(), departments=["35", "22"], years=[2024], min_sample=2)
    # Volumes : toutes les transactions comptent (y compris land/aberrant).
    assert summary["volumes"]["35"]["2024"] == 3
    assert summary["volumes"]["22"]["2024"] == 4
    # Répartition par type.
    assert summary["type_mix_region"]["HOUSE"] == 4
    assert summary["type_mix_region"]["APARTMENT"] == 2
    assert summary["type_mix_region"]["LAND"] == 1
    # Prix département : l'aberrant et le terrain sont écartés du €/m².
    assert summary["prix_departement"]["35"]["global"]["median"] == 4000.0
    assert summary["prix_departement"]["35"]["nom"] == "Ille-et-Vilaine"
    assert summary["prix_departement"]["22"]["global"]["n"] == 2
    assert summary["prix_departement"]["22"]["global"]["median"] == 1750.0
    # Région.
    assert summary["prix_region"]["global"]["n"] == 5
    assert summary["prix_region"]["global"]["median"] == 3000.0
    # Top communes (n >= min_sample) : Rennes la plus chère.
    assert summary["top_communes_cheres"][0]["commune"] == "Rennes"
    assert summary["top_communes_cheres"][0]["median_ppm2"] == 4000.0
    # Qualité.
    assert summary["qualite"]["transactions_reconstruites"] == 7
    assert summary["qualite"]["transactions_avec_drapeau_qualite"] == 1
    assert summary["qualite"]["transactions_exploitables_ppm2"] == 5


def test_registry_bretagne():
    assert REGIONS["bretagne"] == ["22", "29", "35", "56"]
