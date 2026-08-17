"""Nomenclatures internes standardisées (§156-157).
Chaque connecteur mappe sa terminologie propre vers ces valeurs."""
from __future__ import annotations

import enum


class PropertyType(enum.StrEnum):
    HOUSE = "HOUSE"
    APARTMENT = "APARTMENT"
    LAND = "LAND"
    BUILDING = "BUILDING"
    PARKING = "PARKING"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


class ListingStatus(enum.StrEnum):
    ACTIVE = "ACTIVE"
    MISSING = "MISSING"
    REMOVED = "REMOVED"
    REAPPEARED = "REAPPEARED"
    UNKNOWN = "UNKNOWN"


class EventType(enum.StrEnum):
    LISTING_DISCOVERED = "LISTING_DISCOVERED"
    PRICE_DECREASE = "PRICE_DECREASE"
    PRICE_INCREASE = "PRICE_INCREASE"
    DESCRIPTION_CHANGED = "DESCRIPTION_CHANGED"
    PROPERTY_DETAILS_CHANGED = "PROPERTY_DETAILS_CHANGED"
    STATUS_CHANGED = "STATUS_CHANGED"
    LISTING_MISSING = "LISTING_MISSING"
    LISTING_REMOVED = "LISTING_REMOVED"
    LISTING_REAPPEARED = "LISTING_REAPPEARED"
    POSSIBLE_REPUBLICATION = "POSSIBLE_REPUBLICATION"
    SOURCE_TRANSFER = "SOURCE_TRANSFER"


class HistoryOrigin(enum.StrEnum):
    """D'où provient une valeur historique — ne jamais inventer l'historique (§141)."""

    OBSERVED = "OBSERVED"
    SOURCE_PROVIDED = "SOURCE_PROVIDED"
    EXTERNAL_PUBLIC_SOURCE = "EXTERNAL_PUBLIC_SOURCE"
    UNKNOWN = "UNKNOWN"


class SourceType(enum.StrEnum):
    OPEN_DATA = "OPEN_DATA"
    LISTING_PORTAL = "LISTING_PORTAL"
    GEO = "GEO"
    OTHER = "OTHER"


class JobStatus(enum.StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    QUARANTINED = "QUARANTINED"


class ReviewStatus(enum.StrEnum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"


class IssueSeverity(enum.StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
