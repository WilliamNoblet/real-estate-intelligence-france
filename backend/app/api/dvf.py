"""Endpoints DVF — transactions PAYÉES et statistiques de marché par commune (§107).

Distinct des futurs endpoints d'annonces (prix DEMANDÉS) : ici, ce sont des prix réels."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy import select
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
    stmt = stmt.order_by(TransactionDVF.mutation_date.desc()).limit(limit).offset(offset)

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
                "quality_flag": t.quality_flag,
            }
        )
    return {"items": items, "limit": limit, "offset": offset, "count": len(items)}


@router.get("/markets/{insee_code}")
def market(
    session: SessionDep,
    insee_code: Annotated[str, Path(description="Code INSEE commune")],
    property_type: PropertyType | None = Query(default=None),
) -> dict[str, Any]:
    """Statistiques de marché DVF (prix payés) pour une commune (§67, §107)."""
    return commune_stats(session, insee_code, property_type)
