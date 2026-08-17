"""Modèles ORM. Importer ce module peuple Base.metadata (utilisé par Alembic)."""
from __future__ import annotations

from backend.app.models.base import Base
from backend.app.models.dvf import TransactionDVF
from backend.app.models.listings import (
    Listing,
    ListingCheck,
    ListingEvent,
    ListingSnapshot,
    Property,
)
from backend.app.models.matching import (
    DataQualityIssue,
    Dpe,
    DVFMatchCandidate,
    PropertyMatchCandidate,
)
from backend.app.models.reference import (
    Commune,
    DataSource,
    Department,
    IngestionBatch,
    Iris,
    JobRun,
    Region,
)

__all__ = [
    "Base",
    "Commune",
    "DataQualityIssue",
    "DataSource",
    "Department",
    "Dpe",
    "DVFMatchCandidate",
    "IngestionBatch",
    "Iris",
    "JobRun",
    "Listing",
    "ListingCheck",
    "ListingEvent",
    "ListingSnapshot",
    "Property",
    "PropertyMatchCandidate",
    "Region",
    "TransactionDVF",
]
