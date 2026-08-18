"""Contract test : tout adaptateur produit un NormalizedListing valide (§96)."""
from __future__ import annotations

import datetime as dt
from collections.abc import Iterable

from backend.app.models.enums import PropertyType
from collectors.base import ListingSourceAdapter, NormalizedListing


class MockAdapter(ListingSourceAdapter):
    source_name = "mock"

    def discover(self) -> Iterable[str]:
        return ["A1"]

    def fetch(self, external_id: str) -> str:
        return f"<html>bien {external_id} — 385000 EUR, 105 m2</html>"

    def parse(self, payload: str) -> dict:
        return {"id": "A1", "price": 385000, "surface": 105.0}

    def normalize(self, parsed: dict) -> NormalizedListing:
        return NormalizedListing(
            source=self.source_name,
            external_id=parsed["id"],
            price_eur=parsed["price"],
            surface_m2=parsed["surface"],
            property_type=PropertyType.HOUSE,
            observed_at=dt.datetime(2027, 1, 15, tzinfo=dt.UTC),
        )


def test_adapter_roundtrip():
    adapter = MockAdapter()
    ids = list(adapter.discover())
    assert ids == ["A1"]
    listing = adapter.normalize(adapter.parse(adapter.fetch(ids[0])))
    assert isinstance(listing, NormalizedListing)
    assert listing.property_type == PropertyType.HOUSE
    assert listing.price_eur == 385000
    assert adapter.validate(listing) is True


def test_validate_rejects_impossible_values():
    adapter = MockAdapter()
    bad = NormalizedListing(
        source="mock",
        external_id="X",
        price_eur=-1,
        observed_at=dt.datetime(2027, 1, 1, tzinfo=dt.UTC),
    )
    assert adapter.validate(bad) is False
