"""Connecteur Immonot — tests PURS (parser OpenGraph + helpers), sans réseau (§12, §95).
Fixtures 100% synthétiques (aucune donnée réelle ni personnelle)."""
from __future__ import annotations

from pathlib import Path

from backend.app.models.enums import PropertyType
from collectors.immonot.adapter import (
    ImmonotAdapter,
    _locs,
    extract_external_id,
    filter_urls_by_department,
    map_property_type,
    parse_listing,
    parse_og_title,
    postcode_from_url,
)

FIX = Path(__file__).parent / "fixtures" / "immonot"


def test_parse_og_title_house():
    f = parse_og_title("Maison à vendre Grand-Fort-Philippe (59153) Nord 2 pièces 65 m² 92 500 €")
    assert f["property_type"] == PropertyType.HOUSE
    assert f["city"] == "Grand-Fort-Philippe"
    assert f["postal_code"] == "59153"
    assert f["rooms"] == 2
    assert f["surface_m2"] == 65.0
    assert f["price_eur"] == 92500.0


def test_parse_og_title_apartment_narrow_space():
    # Espace fine insécable (U+202F) comme séparateur de milliers, comme sur le vrai site.
    f = parse_og_title(
        "Appartement à vendre Cesson-Sévigné (35510) Ille-et-Vilaine 5 pièces 123 m² 464 000 €"
    )
    assert f["property_type"] == PropertyType.APARTMENT
    assert f["price_eur"] == 464000.0
    assert f["surface_m2"] == 123.0


def test_parse_og_title_land_without_rooms():
    f = parse_og_title("Terrain à bâtir à vendre Testville (33000) Gironde 500 m² 90 000 €")
    assert f["property_type"] == PropertyType.LAND
    assert f["rooms"] is None
    assert f["surface_m2"] == 500.0
    assert f["price_eur"] == 90000.0


def test_map_property_type():
    assert map_property_type("Maison") == PropertyType.HOUSE
    assert map_property_type("Local commercial") == PropertyType.OTHER
    assert map_property_type("Parking") == PropertyType.PARKING
    assert map_property_type("Chose") == PropertyType.UNKNOWN


def test_extract_external_id_and_postcode():
    url = (
        "https://www.immonot.com/immobilier-notaire/detail/ABC__w1/"
        "achat-maison-a-vendre-33000-testville-gironde.html"
    )
    assert extract_external_id(url) == "ABC__w1"
    assert postcode_from_url(url) == "33000"


def test_filter_urls_by_department():
    urls = _locs((FIX / "sitemap.xml").read_text(encoding="utf-8"))
    assert len(urls) == 3
    kept = filter_urls_by_department(urls, "33")
    assert len(kept) == 2
    assert all(postcode_from_url(u).startswith("33") for u in kept)


def test_parse_and_normalize_fixture():
    html = (FIX / "listing.html").read_text(encoding="utf-8")
    listing = ImmonotAdapter(client=object()).normalize(parse_listing(html))  # pas de réseau
    assert listing.source == "Immonot"
    assert listing.external_id == "TESTID__wdemo"
    assert listing.property_type == PropertyType.HOUSE
    assert listing.price_eur == 385000.0
    assert listing.surface_m2 == 105.0
    assert listing.rooms == 4
    assert listing.postal_code == "33000"
    assert listing.city == "Testville"
    assert listing.seller_type == "notaire"
    assert listing.url.endswith("testville-gironde.html")
