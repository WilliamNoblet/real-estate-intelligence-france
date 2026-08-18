"""Comparables DVF (Phase 9) : transactions réellement PAYÉES proches d'un bien (§62-66).

- filtre : même type, distance (ST_DWithin), tolérance de surface, période ;
- élargissement PROGRESSIF (rayon puis période) tant que l'échantillon est insuffisant (§63) ;
- statistiques ROBUSTES (médiane / Q1 / Q3 / IQR / n, §64) ;
- écart au marché formulé prudemment : « écart vs la médiane des comparables sélectionnés »,
  JAMAIS « surévalué de X % » (§66)."""
from __future__ import annotations

import calendar
import datetime as dt
import statistics

from geoalchemy2 import Geography
from sqlalchemy import cast, func, select
from sqlalchemy.orm import Session

from backend.app.core.config import load_yaml_config
from backend.app.models import TransactionDVF
from backend.app.models.enums import PropertyType


def _months_before(d: dt.date, months: int) -> dt.date:
    total = d.year * 12 + (d.month - 1) - months
    year, month = divmod(total, 12)
    month += 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return dt.date(year, month, day)


def _robust_stats(values: list[float]) -> dict:
    n = len(values)
    if n == 0:
        return {"count": 0, "median": None, "q1": None, "q3": None, "iqr": None}
    median = round(statistics.median(values), 2)
    if n >= 2:
        quartiles = statistics.quantiles(values, n=4, method="inclusive")
        q1, q3 = round(quartiles[0], 2), round(quartiles[2], 2)
    else:
        q1 = q3 = median
    return {"count": n, "median": median, "q1": q1, "q3": q3, "iqr": round(q3 - q1, 2)}


def find_comparable_sales(
    session: Session,
    lat: float,
    lon: float,
    property_type: PropertyType | str,
    surface_m2: float,
    reference_date: dt.date | None = None,
    asking_price_per_m2: float | None = None,
) -> dict:
    """Transactions comparables autour d'un point + statistiques et écart au marché."""
    cfg = load_yaml_config("default").get("comparables", {})
    radii = sorted(cfg.get("radius_steps_m", [1000]))
    periods = sorted(cfg.get("period_steps_months", [24]))
    tol = float(cfg.get("surface_tolerance_pct", 0.20))
    min_sample = int(cfg.get("min_sample", 5))

    reference_date = reference_date or dt.date.today()
    ptype = (
        property_type if isinstance(property_type, PropertyType) else PropertyType(property_type)
    )
    smin, smax = surface_m2 * (1 - tol), surface_m2 * (1 + tol)

    point = cast(func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326), Geography)
    dist = func.ST_Distance(TransactionDVF.location, point)

    def query(radius: int, months: int) -> list:
        date_min = _months_before(reference_date, months)
        stmt = (
            select(
                TransactionDVF.id_mutation,
                TransactionDVF.price_per_m2,
                TransactionDVF.sale_price,
                TransactionDVF.surface_m2,
                TransactionDVF.mutation_date,
                TransactionDVF.latitude,
                TransactionDVF.longitude,
                dist.label("dist"),
            )
            .where(
                TransactionDVF.property_type == ptype,
                TransactionDVF.price_per_m2.is_not(None),
                TransactionDVF.location.is_not(None),
                TransactionDVF.surface_m2 >= smin,
                TransactionDVF.surface_m2 <= smax,
                TransactionDVF.mutation_date >= date_min,
                func.ST_DWithin(TransactionDVF.location, point, radius),
            )
            .order_by(dist)
        )
        return session.execute(stmt).all()

    # Élargissement progressif : rayon d'abord (proximité prioritaire), puis période (§63).
    rows: list = []
    used_r, used_p = radii[-1], periods[-1]
    found = False
    for radius in radii:
        for months in periods:
            rows = query(radius, months)
            if len(rows) >= min_sample:
                used_r, used_p, found = radius, months, True
                break
        if found:
            break
    if not found:
        used_r, used_p = radii[-1], periods[-1]
        rows = query(used_r, used_p)

    values = [float(r.price_per_m2) for r in rows]
    stats = _robust_stats(values)

    comparables = [
        {
            "id_mutation": r.id_mutation,
            "price_per_m2": float(r.price_per_m2),
            "sale_price": float(r.sale_price) if r.sale_price is not None else None,
            "surface_m2": float(r.surface_m2) if r.surface_m2 is not None else None,
            "distance_m": round(float(r.dist), 1) if r.dist is not None else None,
            "latitude": float(r.latitude) if r.latitude is not None else None,
            "longitude": float(r.longitude) if r.longitude is not None else None,
            "mutation_date": r.mutation_date.isoformat() if r.mutation_date else None,
        }
        for r in rows
    ]

    market_gap_pct = None
    if asking_price_per_m2 and stats["median"]:
        market_gap_pct = round((asking_price_per_m2 - stats["median"]) / stats["median"] * 100, 2)

    return {
        "property_type": ptype.value,
        "reference_surface_m2": surface_m2,
        "reference_date": reference_date.isoformat(),
        "radius_m_used": used_r,
        "period_months_used": used_p,
        "surface_range_m2": [round(smin, 1), round(smax, 1)],
        "sample_size": stats["count"],
        "insufficient_sample": stats["count"] < min_sample,
        "min_sample": min_sample,
        "median_price_per_m2": stats["median"],
        "q1_price_per_m2": stats["q1"],
        "q3_price_per_m2": stats["q3"],
        "iqr_price_per_m2": stats["iqr"],
        "asking_price_per_m2": asking_price_per_m2,
        # Prudence (§66) : écart vs la médiane des comparables, pas une « vraie valeur ».
        "market_gap_pct": market_gap_pct,
        "comparables": comparables,
    }
