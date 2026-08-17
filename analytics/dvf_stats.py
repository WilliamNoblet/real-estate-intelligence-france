"""Statistiques de marché DVF par commune — robustes (médiane/Q1/Q3, §64) et honnêtes
sur la taille d'échantillon (§159 : « échantillon insuffisant » sous un seuil configurable)."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.config import load_yaml_config
from backend.app.models import TransactionDVF
from backend.app.models.enums import PropertyType


def _min_sample() -> int:
    return int(load_yaml_config("default").get("comparables", {}).get("min_sample", 5))


def commune_stats(
    session: Session,
    insee_code: str,
    property_type: PropertyType | None = None,
    min_sample: int | None = None,
) -> dict:
    """Prix de transaction (payés) pour une commune : nombre, médiane et quartiles du €/m²."""
    threshold = _min_sample() if min_sample is None else min_sample
    ppm2 = TransactionDVF.price_per_m2

    conditions = [TransactionDVF.insee_code == insee_code, ppm2.is_not(None)]
    if property_type is not None:
        conditions.append(TransactionDVF.property_type == property_type)

    stmt = select(
        func.count().label("n"),
        func.percentile_cont(0.5).within_group(ppm2.asc()).label("median_ppm2"),
        func.percentile_cont(0.25).within_group(ppm2.asc()).label("q1_ppm2"),
        func.percentile_cont(0.75).within_group(ppm2.asc()).label("q3_ppm2"),
        func.percentile_cont(0.5)
        .within_group(TransactionDVF.sale_price.asc())
        .label("median_price"),
    ).where(*conditions)

    row = session.execute(stmt).one()
    n = int(row.n or 0)

    def num(x: object) -> float | None:
        return round(float(x), 2) if x is not None else None

    return {
        "insee_code": insee_code,
        "property_type": property_type.value if property_type else None,
        "sample_size": n,
        "min_sample": threshold,
        "insufficient_sample": n < threshold,
        "median_price_per_m2": num(row.median_ppm2),
        "q1_price_per_m2": num(row.q1_ppm2),
        "q3_price_per_m2": num(row.q3_ppm2),
        "median_sale_price": num(row.median_price),
    }
