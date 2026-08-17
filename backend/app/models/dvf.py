"""Transactions DVF — prix réellement PAYÉS (à ne jamais confondre avec les prix demandés, §3)."""
from __future__ import annotations

import datetime as dt

from geoalchemy2 import Geography
from sqlalchemy import (
    BigInteger,
    Date,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base, TimestampMixin
from backend.app.models.enums import PropertyType


class TransactionDVF(Base, TimestampMixin):
    """Une transaction reconstruite. ATTENTION : 1 ligne DVF brute != 1 vente (§26).
    On regroupe par id_mutation ; la valeur foncière n'est jamais sommée sur les lignes."""

    __tablename__ = "transaction_dvf"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # Unique : une transaction reconstruite par mutation → upsert idempotent (§80).
    id_mutation: Mapped[str] = mapped_column(String(40), nullable=False)
    mutation_date: Mapped[dt.date | None] = mapped_column(Date)
    mutation_type: Mapped[str | None] = mapped_column(String(80))
    sale_price: Mapped[float | None] = mapped_column(Numeric(12, 2))  # € — NUMERIC exact (§154)
    property_type: Mapped[PropertyType] = mapped_column(
        Enum(PropertyType, native_enum=False, length=20), default=PropertyType.UNKNOWN
    )
    surface_m2: Mapped[float | None] = mapped_column(Numeric(10, 2))
    land_surface_m2: Mapped[float | None] = mapped_column(Numeric(12, 2))
    rooms: Mapped[int | None] = mapped_column(SmallInteger)
    raw_address: Mapped[str | None] = mapped_column(Text)
    normalized_address: Mapped[str | None] = mapped_column(Text)
    postal_code: Mapped[str | None] = mapped_column(String(5))
    city: Mapped[str | None] = mapped_column(String(200))
    insee_code: Mapped[str | None] = mapped_column(ForeignKey("commune.insee_code"), index=True)
    latitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    # Point géographique (WGS-84) pour ST_DWithin / ST_Distance en mètres (§28).
    location = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=False), nullable=True
    )
    parcel_id: Mapped[str | None] = mapped_column(String(20), index=True)
    price_per_m2: Mapped[float | None] = mapped_column(Numeric(12, 2))
    source_year: Mapped[int | None] = mapped_column(SmallInteger)
    source_row_reference: Mapped[str | None] = mapped_column(String(120))
    quality_flag: Mapped[str | None] = mapped_column(String(40))
    ingestion_batch_id: Mapped[int | None] = mapped_column(ForeignKey("ingestion_batch.id"))

    __table_args__ = (
        UniqueConstraint("id_mutation", name="uq_transaction_dvf_id_mutation"),
        Index("ix_transaction_dvf_insee_date", "insee_code", "mutation_date"),
        Index("ix_transaction_dvf_location", "location", postgresql_using="gist"),
    )
