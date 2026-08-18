"""Endpoints DVF — transactions PAYÉES et statistiques de marché par commune (§107).

Distinct des futurs endpoints d'annonces (prix DEMANDÉS) : ici, ce sont des prix réels."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query
from geoalchemy2 import Geography
from sqlalchemy import cast, func, select
from sqlalchemy.orm import Session

from analytics.dvf_stats import commune_stats
from backend.app.core.db import get_session
from backend.app.models import TransactionDVF
from backend.app.models.enums import PropertyType

router = APIRouter(tags=["transactions"])

SessionDep = Annotated[Session, Depends(get_session)]


@router.get("/transactions")
def list_transactions(
    session: SessionDep,
    insee_code: str | None = Query(default=None, description="Code INSEE commune"),
    property_type: PropertyType | None = Query(default=None),
    min_price: float | None = Query(default=None, ge=0),
    max_price: float | None = Query(default=None, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    """Liste paginée des transactions DVF (§108 : tout endpoint volumineux est paginé)."""
    stmt = select(TransactionDVF)
    if insee_code:
        stmt = stmt.where(TransactionDVF.insee_code == insee_code)
    if property_type is not None:
        stmt = stmt.where(TransactionDVF.property_type == property_type)
    if min_price is not None:
        stmt = stmt.where(TransactionDVF.sale_price >= min_price)
    if max_price is not None:
        stmt = stmt.where(TransactionDVF.sale_price <= max_price)
    # Clé de départage unique (id) : sans elle, la pagination OFFSET est non déterministe
    # à égalité de mutation_date (doublons/omissions entre pages).
    stmt = (
        stmt.order_by(TransactionDVF.mutation_date.desc(), TransactionDVF.id.desc())
        .limit(limit)
        .offset(offset)
    )

    items = []
    for t in session.execute(stmt).scalars().all():
        items.append(
            {
                "id_mutation": t.id_mutation,
                "mutation_date": t.mutation_date.isoformat() if t.mutation_date else None,
                "property_type": t.property_type.value,
                "sale_price": float(t.sale_price) if t.sale_price is not None else None,
                "surface_m2": float(t.surface_m2) if t.surface_m2 is not None else None,
                "price_per_m2": float(t.price_per_m2) if t.price_per_m2 is not None else None,
                "rooms": t.rooms,
                "city": t.city,
                "insee_code": t.insee_code,
                "latitude": float(t.latitude) if t.latitude is not None else None,
                "longitude": float(t.longitude) if t.longitude is not None else None,
                "quality_flag": t.quality_flag,
            }
        )
    return {"items": items, "limit": limit, "offset": offset, "count": len(items)}


@router.get("/transactions/nearby")
def transactions_nearby(
    session: SessionDep,
    lat: Annotated[float, Query(ge=-90, le=90, description="Latitude WGS-84")],
    lon: Annotated[float, Query(ge=-180, le=180, description="Longitude WGS-84")],
    radius_m: int = Query(default=1000, ge=1, le=50000, description="Rayon en mètres"),
    property_type: PropertyType | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    """Transactions DVF autour d'un point (requête spatiale PostGIS ST_DWithin, §28)."""
    point = cast(func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326), Geography)
    dist = func.ST_Distance(TransactionDVF.location, point).label("dist")
    stmt = select(TransactionDVF, dist).where(
        TransactionDVF.location.is_not(None),
        func.ST_DWithin(TransactionDVF.location, point, radius_m),
    )
    if property_type is not None:
        stmt = stmt.where(TransactionDVF.property_type == property_type)
    stmt = stmt.order_by(dist, TransactionDVF.id).limit(limit)

    items = []
    for t, distance in session.execute(stmt).all():
        items.append(
            {
                "id_mutation": t.id_mutation,
                "property_type": t.property_type.value,
                "sale_price": float(t.sale_price) if t.sale_price is not None else None,
                "price_per_m2": float(t.price_per_m2) if t.price_per_m2 is not None else None,
                "surface_m2": float(t.surface_m2) if t.surface_m2 is not None else None,
                "distance_m": round(float(distance), 1) if distance is not None else None,
                "latitude": float(t.latitude) if t.latitude is not None else None,
                "longitude": float(t.longitude) if t.longitude is not None else None,
                "mutation_date": t.mutation_date.isoformat() if t.mutation_date else None,
            }
        )
    return {
        "center": {"lat": lat, "lon": lon},
        "radius_m": radius_m,
        "count": len(items),
        "items": items,
    }


@router.get("/markets/{insee_code}")
def market(
    session: SessionDep,
    insee_code: Annotated[str, Path(description="Code INSEE commune")],
    property_type: PropertyType | None = Query(default=None),
) -> dict[str, Any]:
    """Statistiques de marché DVF (prix payés) pour une commune (§67, §107)."""
    return commune_stats(session, insee_code, property_type)
