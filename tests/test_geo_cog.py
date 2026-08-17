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
