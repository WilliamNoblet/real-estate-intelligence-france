"""Annonces (prix DEMANDÉS) et leur historisation : property, listing, snapshot, check, event."""
from __future__ import annotations

import datetime as dt

from geoalchemy2 import Geography
from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base, TimestampMixin
from backend.app.models.enums import EventType, HistoryOrigin, ListingStatus, PropertyType


class Property(Base, TimestampMixin):
    """Bien immobilier canonique PRÉSUMÉ (§36). Une property peut avoir plusieurs listings."""

    __tablename__ = "property"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    property_type: Mapped[PropertyType] = mapped_column(
        Enum(PropertyType, native_enum=False, length=20), default=PropertyType.UNKNOWN
    )
    normalized_address: Mapped[str | None] = mapped_column(Text)
    postal_code: Mapped[str | None] = mapped_column(String(5))
    city: Mapped[str | None] = mapped_column(String(200))
    insee_code: Mapped[str | None] = mapped_column(ForeignKey("commune.insee_code"), index=True)
    location = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=False), nullable=True
    )
    surface_m2: Mapped[float | None] = mapped_column(Numeric(10, 2))
    land_surface_m2: Mapped[float | None] = mapped_column(Numeric(12, 2))
    rooms: Mapped[int | None] = mapped_column(SmallInteger)
    bedrooms: Mapped[int | None] = mapped_column(SmallInteger)
    construction_year: Mapped[int | None] = mapped_column(SmallInteger)
    energy_rating: Mapped[str | None] = mapped_column(String(1))
    ghg_rating: Mapped[str | None] = mapped_column(String(1))

    listings: Mapped[list[Listing]] = relationship(back_populates="property")

    __table_args__ = (Index("ix_property_location", "location", postgresql_using="gist"),)


class Listing(Base, TimestampMixin):
    """Une annonce sur une source donnée (§35). Identifiée par (source_id, external_listing_id)."""

    __tablename__ = "listing"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("data_source.id"), nullable=False)
    external_listing_id: Mapped[str] = mapped_column(String(120), nullable=False)
    canonical_property_id: Mapped[int | None] = mapped_column(
        ForeignKey("property.id"), index=True
    )
    canonical_url: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ListingStatus] = mapped_column(
        Enum(ListingStatus, native_enum=False, length=20),
        default=ListingStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    property_type: Mapped[PropertyType] = mapped_column(
        Enum(PropertyType, native_enum=False, length=20),
        default=PropertyType.UNKNOWN,
        nullable=False,
    )
    # Distinguer la date de publication fournie par la source de notre 1re observation (§48).
    source_publication_date: Mapped[dt.date | None] = mapped_column(Date)
    first_seen_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_seen_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    last_checked_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    history_origin: Mapped[HistoryOrigin] = mapped_column(
        Enum(HistoryOrigin, native_enum=False, length=32), default=HistoryOrigin.OBSERVED
    )
    parser_version: Mapped[str | None] = mapped_column(String(40))

    # Géolocalisation (§29) : renseignée par l'enrichissement (ville+CP -> insee+coords via IGN).
    # Précision commune (approximative) : ne jamais présenter comme une adresse certaine.
    latitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    location = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=False), nullable=True
    )
    insee_code: Mapped[str | None] = mapped_column(String(5), index=True)
    geocoded_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    geocoding_score: Mapped[float | None] = mapped_column(Numeric(4, 3))

    property: Mapped[Property | None] = relationship(back_populates="listings")
    snapshots: Mapped[list[ListingSnapshot]] = relationship(back_populates="listing")

    __table_args__ = (
        UniqueConstraint("source_id", "external_listing_id", name="uq_listing_source_external"),
        Index("ix_listing_location", "location", postgresql_using="gist"),
    )


class ListingSnapshot(Base):
    """Observation horodatée APPEND-ONLY (§38, §86). Ne jamais écraser un prix (§39)."""

    __tablename__ = "listing_snapshot"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listing.id"), nullable=False)
    observed_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    price_eur: Mapped[float | None] = mapped_column(Numeric(12, 2))  # prix DEMANDÉ
    price_per_m2: Mapped[float | None] = mapped_column(Numeric(12, 2))
    title: Mapped[str | None] = mapped_column(Text)
    surface_m2: Mapped[float | None] = mapped_column(Numeric(10, 2))
    land_surface_m2: Mapped[float | None] = mapped_column(Numeric(12, 2))
    rooms: Mapped[int | None] = mapped_column(SmallInteger)
    bedrooms: Mapped[int | None] = mapped_column(SmallInteger)
    energy_rating: Mapped[str | None] = mapped_column(String(1))
    ghg_rating: Mapped[str | None] = mapped_column(String(1))
    seller_type: Mapped[str | None] = mapped_column(String(40))
    agency_name: Mapped[str | None] = mapped_column(String(200))
    city: Mapped[str | None] = mapped_column(String(200))
    postal_code: Mapped[str | None] = mapped_column(String(5))
    latitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    location = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=False), nullable=True
    )
    photo_count: Mapped[int | None] = mapped_column(Integer)
    description_hash: Mapped[str | None] = mapped_column(String(64))
    photo_fingerprint: Mapped[str | None] = mapped_column(Text)  # pHash/dHash, pas l'image (§57)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    pipeline_version: Mapped[str | None] = mapped_column(String(40))
    parser_version: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    listing: Mapped[Listing] = relationship(back_populates="snapshots")

    __table_args__ = (
        Index("ix_listing_snapshot_listing_observed", "listing_id", "observed_at"),
        Index("ix_listing_snapshot_location", "location", postgresql_using="gist"),
    )


class ListingCheck(Base):
    """Trace « on a vérifié l'annonce » — distinct de « la donnée a changé » (§42)."""

    __tablename__ = "listing_check"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listing.id"), nullable=False, index=True)
    checked_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    found: Mapped[bool] = mapped_column(Boolean, nullable=False)
    http_status: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    parser_success: Mapped[bool | None] = mapped_column(Boolean)
    error_code: Mapped[str | None] = mapped_column(String(40))


class ListingEvent(Base):
    """Événement typé issu d'un diff entre snapshots (§43-44)."""

    __tablename__ = "listing_event"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listing.id"), nullable=False)
    event_type: Mapped[EventType] = mapped_column(
        Enum(EventType, native_enum=False, length=32), nullable=False
    )
    event_date: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    event_metadata: Mapped[dict | None] = mapped_column(JSONB)
    snapshot_id: Mapped[int | None] = mapped_column(ForeignKey("listing_snapshot.id"))

    __table_args__ = (
        Index("ix_listing_event_listing_date", "listing_id", "event_date"),
    )
