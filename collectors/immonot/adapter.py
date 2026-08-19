"""Adaptateur Immonot : discovery (sitemap) -> fetch -> parse (OpenGraph) -> NormalizedListing.

Les fonctions au niveau module (parse_og_title, map_property_type, extract_external_id,
postcode_from_url, filter_urls_by_department, parse_listing) sont PURES et testées sur fixtures
synthétiques (sans réseau). Les méthodes réseau (discover/fetch) ne tournent jamais en CI (§12).

Note : en mode Unicode (motifs str), `\\s` couvre déjà l'espace insécable (U+00A0) et l'espace
fine insécable (U+202F) utilisées comme séparateurs de milliers dans les titres."""
from __future__ import annotations

import datetime as dt
import logging
import re
import time
from collections.abc import Iterable

import httpx
from selectolax.parser import HTMLParser

from backend.app.core.config import settings
from backend.app.models.enums import PropertyType
from collectors.base import ListingSourceAdapter, NormalizedListing

log = logging.getLogger("reif.immonot")

SITEMAP_INDEX = "https://www.immonot.com/sitemap.xml"


def _to_number(raw: str | None) -> float | None:
    if not raw:
        return None
    cleaned = re.sub(r"\s", "", raw).replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def map_property_type(type_str: str | None) -> PropertyType:
    t = (type_str or "").lower()
    if "maison" in t:
        return PropertyType.HOUSE
    if "appartement" in t:
        return PropertyType.APARTMENT
    if "terrain" in t:
        return PropertyType.LAND
    if "immeuble" in t:
        return PropertyType.BUILDING
    if "parking" in t or "garage" in t:
        return PropertyType.PARKING
    if any(k in t for k in ("local", "bureau", "commerce", "fonds")):
        return PropertyType.OTHER
    return PropertyType.UNKNOWN


def parse_og_title(title: str | None) -> dict:
    """Extrait type/ville/CP/pièces/surface/prix d'un og:title Immonot.

    Ex. « Maison à vendre Cesson-Sévigné (35510) Ille-et-Vilaine 5 pièces 123 m² 464 000 € »."""
    out: dict = {
        "property_type": PropertyType.UNKNOWN,
        "city": None,
        "postal_code": None,
        "rooms": None,
        "surface_m2": None,
        "price_eur": None,
    }
    if not title:
        return out

    m_type = re.match(r"^\s*(.+?)\s+à\s+vendre\b", title)
    if m_type:
        out["property_type"] = map_property_type(m_type.group(1))

    m_city = re.search(r"à\s+vendre\s+(.+?)\s+\((\d{5})\)", title)
    if m_city:
        out["city"] = m_city.group(1).strip()
        out["postal_code"] = m_city.group(2)

    m_rooms = re.search(r"(\d+)\s+pièces?", title)
    if m_rooms:
        out["rooms"] = int(m_rooms.group(1))

    m_surface = re.search(r"(\d[\d\s]*?)\s*m²", title)
    if m_surface:
        out["surface_m2"] = _to_number(m_surface.group(1))

    m_price = re.search(r"([\d\s]+)\s*€\s*$", title)
    if m_price:
        out["price_eur"] = _to_number(m_price.group(1))

    return out


def extract_external_id(url: str | None) -> str | None:
    """Identifiant stable = segment d'URL entre /detail/ et le slug."""
    if not url:
        return None
    m = re.search(r"/detail/([^/]+)/", url)
    return m.group(1) if m else None


def postcode_from_url(url: str | None) -> str | None:
    if not url:
        return None
    m = re.search(r"a-vendre-(\d{5})-", url)
    return m.group(1) if m else None


def filter_urls_by_department(urls: Iterable[str], department: str | None) -> list[str]:
    """Ne garde que les annonces d'un département (préfixe de code postal). None = tout garder."""
    if not department:
        return list(urls)
    return [u for u in urls if (postcode_from_url(u) or "").startswith(department)]


def _locs(xml: str) -> list[str]:
    return re.findall(r"<loc>\s*(.*?)\s*</loc>", xml, re.S)


def parse_listing(html: str) -> dict:
    """Extrait les champs d'une fiche depuis ses balises OpenGraph (rendu serveur)."""
    tree = HTMLParser(html)

    def og(prop: str) -> str | None:
        node = tree.css_first(f'meta[property="{prop}"]')
        return node.attributes.get("content") if node else None

    def meta_name(name: str) -> str | None:
        node = tree.css_first(f'meta[name="{name}"]')
        return node.attributes.get("content") if node else None

    title = og("og:title")
    fields = parse_og_title(title)
    fields["title"] = title
    fields["url"] = og("og:url")
    fields["description"] = og("og:description") or meta_name("description")
    return fields


class ImmonotAdapter(ListingSourceAdapter):
    """Connecteur Immonot. Contraintes LIMITED : sitemap-only, débit faible, UA honnête."""

    source_name = "Immonot"

    def __init__(
        self,
        department: str | None = None,
        max_listings: int = 200,
        rate_delay: float = 1.0,
        client: httpx.Client | None = None,
    ):
        self.department = department
        self.max_listings = max_listings
        self.rate_delay = rate_delay
        self._client = client or httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            headers={"User-Agent": settings.user_agent},
        )

    def _get(self, url: str) -> str:
        resp = self._client.get(url)
        resp.raise_for_status()
        time.sleep(self.rate_delay)  # politesse réseau (§82, §140)
        return resp.text

    def discover(self) -> Iterable[str]:
        """URLs de fiches, via les sitemaps de détail, bornées au département et à max_listings."""
        index = self._get(SITEMAP_INDEX)
        detail_sitemaps = [loc for loc in _locs(index) if "annonce_detail_" in loc]
        urls: list[str] = []
        for sitemap in detail_sitemaps:
            if len(urls) >= self.max_listings:
                break
            listing_urls = filter_urls_by_department(_locs(self._get(sitemap)), self.department)
            for url in listing_urls:
                urls.append(url)
                if len(urls) >= self.max_listings:
                    break
        log.info("Immonot discover : %d fiches (dept=%s)", len(urls), self.department)
        return urls

    def fetch(self, external_id: str) -> str:
        return self._get(external_id)

    def parse(self, payload: str) -> dict:
        return parse_listing(payload)

    def normalize(self, parsed: dict) -> NormalizedListing:
        url = parsed.get("url")
        external_id = extract_external_id(url) or url or ""
        return NormalizedListing(
            source=self.source_name,
            external_id=external_id,
            url=url,
            price_eur=parsed.get("price_eur"),
            surface_m2=parsed.get("surface_m2"),
            rooms=parsed.get("rooms"),
            property_type=parsed.get("property_type", PropertyType.UNKNOWN),
            city=parsed.get("city"),
            postal_code=parsed.get("postal_code"),
            title=parsed.get("title"),
            description=parsed.get("description"),
            seller_type="notaire",
            observed_at=dt.datetime.now(dt.UTC),
        )
