"""Contrat commun à tous les connecteurs d'annonces (§34, §96-97).

Chaque source implémente `ListingSourceAdapter` et produit le schéma unique `NormalizedListing`.
Aucun connecteur ne contient les règles d'un autre site (§30)."""
from __future__ import annotations

import datetime as dt
from abc import ABC, abstractmethod
from collections.abc import Iterable

from pydantic import BaseModel, Field

from backend.app.models.enums import PropertyType


class NormalizedListing(BaseModel):
    """Schéma normalisé unique produit par tous les connecteurs (§97).
    Représente une observation d'annonce (prix DEMANDÉ), pas une transaction."""

    source: str
    external_id: str
    url: str | None = None

    price_eur: float | None = None
    surface_m2: float | None = None
    land_surface_m2: float | None = None
    rooms: int | None = None
    bedrooms: int | None = None
    property_type: PropertyType = PropertyType.UNKNOWN

    city: str | None = None
    postal_code: str | None = None
    insee_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None

    energy_rating: str | None = None
    ghg_rating: str | None = None
    seller_type: str | None = None
    agency_name: str | None = None

    title: str | None = None
    description: str | None = None
    photo_count: int | None = None

    # Date de PREMIÈRE OBSERVATION distincte d'une éventuelle date de publication (§48).
    observed_at: dt.datetime
    source_publication_date: dt.date | None = None

    # Empreinte perceptuelle des photos (hash, pas l'image — §57).
    photo_fingerprint: str | None = Field(default=None)


class ListingSourceAdapter(ABC):
    """Interface d'un connecteur. Discovery et Refresh sont deux opérations distinctes (§33)."""

    source_name: str

    @abstractmethod
    def discover(self) -> Iterable[str]:
        """Renvoie des identifiants externes (ou URLs) d'annonces à collecter."""

    @abstractmethod
    def fetch(self, external_id: str) -> str:
        """Récupère la charge brute (HTML/JSON) d'une annonce."""

    @abstractmethod
    def parse(self, payload: str) -> dict:
        """Extrait les champs bruts depuis la charge."""

    @abstractmethod
    def normalize(self, parsed: dict) -> NormalizedListing:
        """Transforme les champs bruts en NormalizedListing."""

    def validate(self, listing: NormalizedListing) -> bool:
        """Validation minimale par défaut : identifiants présents et valeurs plausibles."""
        if not listing.source or not listing.external_id:
            return False
        if listing.price_eur is not None and listing.price_eur <= 0:
            return False
        if listing.surface_m2 is not None and listing.surface_m2 <= 0:
            return False
        return True
