"""Référentiels : catalogue des sources, lots d'ingestion, jobs, et géographie officielle."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base, TimestampMixin
from backend.app.models.enums import JobStatus, SourceType


class DataSource(Base, TimestampMixin):
    """Catalogue des sources (§19). Chaque donnée importante s'y rattache (provenance, §20)."""

    __tablename__ = "data_source"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    source_type: Mapped[SourceType] = mapped_column(
        Enum(SourceType, native_enum=False, length=32), nullable=False
    )
    provider: Mapped[str | None] = mapped_column(String(200))
    url: Mapped[str | None] = mapped_column(Text)
    access_method: Mapped[str | None] = mapped_column(String(120))
    license: Mapped[str | None] = mapped_column(String(120))
    terms_url: Mapped[str | None] = mapped_column(Text)
    refresh_frequency: Mapped[str | None] = mapped_column(String(120))
    free: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_checked_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)


class IngestionBatch(Base):
    """Lot d'ingestion incrémental et idempotent (§22). file_hash = SHA256 de la source (§23)."""

    __tablename__ = "ingestion_batch"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("data_source.id"), nullable=False, index=True)
    started_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, native_enum=False, length=32), default=JobStatus.PENDING, nullable=False
    )
    source_version: Mapped[str | None] = mapped_column(String(120))
    file_hash: Mapped[str | None] = mapped_column(String(64))
    rows_read: Mapped[int] = mapped_column(Integer, default=0)
    rows_inserted: Mapped[int] = mapped_column(Integer, default=0)
    rows_updated: Mapped[int] = mapped_column(Integer, default=0)
    rows_rejected: Mapped[int] = mapped_column(Integer, default=0)

    source: Mapped[DataSource] = relationship()


class JobRun(Base):
    """Observabilité des jobs (§78-79)."""

    __tablename__ = "job_run"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    job_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("data_source.id"), index=True)
    started_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, native_enum=False, length=32), default=JobStatus.PENDING, nullable=False
    )
    items_read: Mapped[int] = mapped_column(Integer, default=0)
    items_inserted: Mapped[int] = mapped_column(Integer, default=0)
    items_updated: Mapped[int] = mapped_column(Integer, default=0)
    items_rejected: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)


# --- Géographie officielle (codes INSEE comme identifiants, §27) ---


class Region(Base):
    __tablename__ = "region"

    insee_code: Mapped[str] = mapped_column(String(3), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)


class Department(Base):
    __tablename__ = "department"

    insee_code: Mapped[str] = mapped_column(String(3), primary_key=True)  # 2A/2B possibles
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    region_code: Mapped[str | None] = mapped_column(ForeignKey("region.insee_code"), index=True)


class Commune(Base):
    __tablename__ = "commune"

    insee_code: Mapped[str] = mapped_column(String(5), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    department_code: Mapped[str | None] = mapped_column(
        ForeignKey("department.insee_code"), index=True
    )
    postal_codes: Mapped[str | None] = mapped_column(String(200))  # CSV des CP rattachés


class Iris(Base):
    __tablename__ = "iris"

    code: Mapped[str] = mapped_column(String(9), primary_key=True)
    commune_code: Mapped[str | None] = mapped_column(ForeignKey("commune.insee_code"), index=True)
    name: Mapped[str | None] = mapped_column(String(200))
