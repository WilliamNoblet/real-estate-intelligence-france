"""Chargement idempotent des transactions DVF en base.

- get_or_create de la source (catalogue data_source).
- ingestion_batch avec file_hash : un fichier déjà importé (même hash) est ignoré (§22-23).
- upsert par id_mutation (ON CONFLICT) : relancer ne duplique pas (§80).
- les communes sont amorcées depuis DVF pour satisfaire la FK
  (la géographie complète arrive en Phase 3)."""
from __future__ import annotations

import datetime as dt

import polars as pl
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from backend.app.core.bulk import chunked, safe_chunk_size
from backend.app.models import Commune, DataSource, IngestionBatch, TransactionDVF
from backend.app.models.enums import JobStatus, PropertyType, SourceType
from pipelines.dvf.source import SOURCE_META
from pipelines.geo.location import backfill_transaction_locations

_UPDATABLE = [
    "mutation_date",
    "mutation_type",
    "sale_price",
    "property_type",
    "surface_m2",
    "land_surface_m2",
    "rooms",
    "city",
    "postal_code",
    "insee_code",
    "latitude",
    "longitude",
    "parcel_id",
    "price_per_m2",
    "source_year",
    "quality_flag",
    "ingestion_batch_id",
]


def get_or_create_source(session: Session) -> DataSource:
    src = session.scalar(select(DataSource).where(DataSource.name == SOURCE_META["name"]))
    if src is not None:
        return src
    src = DataSource(
        name=SOURCE_META["name"],
        source_type=SourceType(SOURCE_META["source_type"]),
        provider=SOURCE_META["provider"],
        url=SOURCE_META["url"],
        access_method=SOURCE_META["access_method"],
        license=SOURCE_META["license"],
        terms_url=SOURCE_META["terms_url"],
        refresh_frequency=SOURCE_META["refresh_frequency"],
        free=SOURCE_META["free"],
        enabled=True,
        notes=SOURCE_META["notes"],
    )
    session.add(src)
    session.flush()
    return src


def _ensure_communes(session: Session, df: pl.DataFrame) -> None:
    """Amorce le référentiel commune (insee_code, name) depuis les transactions.
    department_code reste NULL : la hiérarchie/géométrie est chargée en Phase 3."""
    communes = (
        df.select(["insee_code", "city"])
        .filter(pl.col("insee_code").is_not_null())
        .unique(subset=["insee_code"])
    )
    rows = [
        {"insee_code": r["insee_code"], "name": r["city"] or r["insee_code"]}
        for r in communes.to_dicts()
    ]
    if not rows:
        return
    for chunk in chunked(rows, safe_chunk_size(2)):
        stmt = pg_insert(Commune.__table__).values(chunk).on_conflict_do_nothing(
            index_elements=["insee_code"]
        )
        session.execute(stmt)


def _already_imported(session: Session, source_id: int, file_hash: str) -> bool:
    return (
        session.scalar(
            select(IngestionBatch.id).where(
                IngestionBatch.source_id == source_id,
                IngestionBatch.file_hash == file_hash,
                IngestionBatch.status == JobStatus.SUCCESS,
            )
        )
        is not None
    )


def load_transactions(
    session: Session,
    df: pl.DataFrame,
    *,
    source_version: str,
    file_hash: str,
    rows_read: int,
    rows_rejected: int,
) -> dict:
    """Charge un DataFrame de transactions reconstruites. Idempotent au fichier + à la mutation."""
    source = get_or_create_source(session)

    if _already_imported(session, source.id, file_hash):
        return {"skipped": True, "reason": "file_hash déjà importé", "file_hash": file_hash}

    batch = IngestionBatch(
        source_id=source.id,
        started_at=dt.datetime.now(dt.UTC),
        status=JobStatus.RUNNING,
        source_version=source_version,
        file_hash=file_hash,
        rows_read=rows_read,
        rows_rejected=rows_rejected,
    )
    session.add(batch)
    session.flush()

    _ensure_communes(session, df)

    inserted = updated = 0
    if not df.is_empty():
        values = []
        for d in df.to_dicts():
            values.append(
                {
                    "id_mutation": d["id_mutation"],
                    "mutation_date": d["mutation_date"],
                    "mutation_type": d["mutation_type"],
                    "sale_price": d["sale_price"],
                    "property_type": PropertyType(d["property_type"]),
                    "surface_m2": d["surface_m2"],
                    "land_surface_m2": d["land_surface_m2"],
                    "rooms": d["rooms"],
                    "city": d["city"],
                    "postal_code": d["postal_code"],
                    "insee_code": d["insee_code"],
                    "latitude": d["latitude"],
                    "longitude": d["longitude"],
                    "parcel_id": d["parcel_id"],
                    "price_per_m2": d["price_per_m2"],
                    "source_year": d["source_year"],
                    "quality_flag": d["quality_flag"],
                    "ingestion_batch_id": batch.id,
                }
            )
        # Découpage en lots : un INSERT unique dépasserait la limite de 65535 paramètres
        # de PostgreSQL sur un vrai département (ex. Gironde ≈ 29 000 lignes × 18 colonnes).
        for chunk in chunked(values, safe_chunk_size(len(values[0]))):
            ids = [v["id_mutation"] for v in chunk]
            existing = set(
                session.execute(
                    select(TransactionDVF.id_mutation).where(
                        TransactionDVF.id_mutation.in_(ids)
                    )
                ).scalars()
            )
            n_updated = sum(1 for i in ids if i in existing)
            updated += n_updated
            inserted += len(chunk) - n_updated
            stmt = pg_insert(TransactionDVF.__table__).values(chunk)
            stmt = stmt.on_conflict_do_update(
                index_elements=["id_mutation"],
                set_={col: getattr(stmt.excluded, col) for col in _UPDATABLE}
                | {"updated_at": func.now()},
            )
            session.execute(stmt)
        # Recalcule location depuis lat/lon (only_missing=False : un ré-import peut la corriger).
        backfill_transaction_locations(session, batch.id, only_missing=False)

    batch.completed_at = dt.datetime.now(dt.UTC)
    batch.status = JobStatus.SUCCESS
    batch.rows_inserted = inserted
    batch.rows_updated = updated
    session.commit()
    return {
        "skipped": False,
        "batch_id": batch.id,
        "rows_read": rows_read,
        "rows_inserted": inserted,
        "rows_updated": updated,
        "rows_rejected": rows_rejected,
    }
