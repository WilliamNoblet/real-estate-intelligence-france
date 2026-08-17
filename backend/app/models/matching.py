"""Correspondances probabilistes (entity resolution, annonce↔DVF), qualité et enrichissement DPE."""
from __future__ import annotations

import datetime as dt

from geoalchemy2 import Geography
from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base, TimestampMixin
from backend.app.models.enums import IssueSeverity, ReviewStatus


class PropertyMatchCandidate(Base):
    """Deux properties potentiellement identiques — conservé pour revue si score incertain (§60)."""

    __tablename__ = "property_match_candidate"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    property_a_id: Mapped[int] = mapped_column(
        ForeignKey("property.id"), nullable=False, index=True
    )
    property_b_id: Mapped[int] = mapped_column(
        ForeignKey("property.id"), nullable=False, index=True
    )
    match_score: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    matching_version: Mapped[str] = mapped_column(String(40), nullable=False)
    matching_features: Mapped[dict | None] = mapped_column(JSONB)
    review_status: Mapped[ReviewStatus] = mapped_column(
        Enum(ReviewStatus, native_enum=False, length=20), default=ReviewStatus.PENDING
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DVFMatchCandidate(Base):
    """Rapprochement PROBABILISTE annonce↔transaction DVF.

    Jamais présenté comme certain : on stocke une confiance (§61, §66)."""

    __tablename__ = "dvf_match_candidate"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listing.id"), nullable=False, index=True)
    transaction_dvf_id: Mapped[int] = mapped_column(
        ForeignKey("transaction_dvf.id"), nullable=False, index=True
    )
    confidence: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    matching_version: Mapped[str] = mapped_column(String(40), nullable=False)
    matching_features: Mapped[dict | None] = mapped_column(JSONB)
    review_status: Mapped[ReviewStatus] = mapped_column(
        Enum(ReviewStatus, native_enum=False, length=20), default=ReviewStatus.PENDING
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DataQualityIssue(Base):
    """Anomalie détectée par une règle de qualité (§75-76)."""

    __tablename__ = "data_quality_issue"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(60), nullable=False)
    entity_id: Mapped[int | None] = mapped_column(BigInteger)
    rule: Mapped[str] = mapped_column(String(80), nullable=False)
    severity: Mapped[IssueSeverity] = mapped_column(
        Enum(IssueSeverity, native_enum=False, length=20), default=IssueSeverity.WARNING
    )
    detected_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    resolved_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    details: Mapped[dict | None] = mapped_column(JSONB)

    __table_args__ = (
        Index("ix_dq_entity", "entity_type", "entity_id"),
    )


class Dpe(Base, TimestampMixin):
    """DPE ADEME (enrichissement énergie + appui au matching via identifiant_ban)."""

    __tablename__ = "dpe"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    identifiant_ban: Mapped[str | None] = mapped_column(String(60), index=True)
    insee_code: Mapped[str | None] = mapped_column(String(5), index=True)
    postal_code: Mapped[str | None] = mapped_column(String(5))
    address: Mapped[str | None] = mapped_column(Text)
    surface_habitable_m2: Mapped[float | None] = mapped_column(Numeric(10, 2))
    etiquette_dpe: Mapped[str | None] = mapped_column(String(1))
    etiquette_ges: Mapped[str | None] = mapped_column(String(1))
    date_etablissement: Mapped[dt.date | None] = mapped_column(Date)
    latitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    location = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=False), nullable=True
    )
    ingestion_batch_id: Mapped[int | None] = mapped_column(ForeignKey("ingestion_batch.id"))

    __table_args__ = (Index("ix_dpe_location", "location", postgresql_using="gist"),)
