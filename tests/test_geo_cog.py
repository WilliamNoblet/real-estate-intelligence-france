"""Tests des transformations COG (pures, sans réseau ni base)."""
from __future__ import annotations

from pipelines.geo.cog import transform_communes, transform_departments, transform_regions


def test_transform_regions():
    assert transform_regions([{"code": "75", "nom": "Nouvelle-Aquitaine"}]) == [
        {"insee_code": "75", "name": "Nouvelle-Aquitaine"}
    ]


def test_transform_departments_keeps_region():
    out = transform_departments([{"code": "33", "nom": "Gironde", "codeRegion": "75"}])
    assert out == [{"insee_code": "33", "name": "Gironde", "region_code": "75"}]


def test_transform_communes_keeps_department():
    out = transform_communes(
        [{"code": "33063", "nom": "Bordeaux", "codeDepartement": "33", "codeRegion": "75"}]
    )
    assert out == [{"insee_code": "33063", "name": "Bordeaux", "department_code": "33"}]


def test_transform_skips_items_without_code():
    assert transform_regions([{"nom": "sans code"}]) == []
    assert transform_communes([{"nom": "x", "codeDepartement": "33"}]) == []


def test_transform_communes_filtre_departements_inconnus():
    # Régression : les communes de collectivités d'outre-mer (dépt 975 absent de /departements)
    # doivent être écartées, sinon violation de la clé étrangère commune -> department.
    items = [
        {"code": "35238", "nom": "Rennes", "codeDepartement": "35"},
        {"code": "97501", "nom": "Miquelon-Langlade", "codeDepartement": "975"},  # COM sans dept
        {"code": "22001", "nom": "Sans dept", "codeDepartement": None},  # department_code None
    ]
    out = transform_communes(items, valid_departments={"35", "22", "29", "56"})
    assert out == [{"insee_code": "35238", "name": "Rennes", "department_code": "35"}]
    # Sans filtre (compat ascendante), tout est conservé.
    assert len(transform_communes(items)) == 3
