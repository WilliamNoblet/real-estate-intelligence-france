"""Client de géocodage IGN (data.geopf.fr). `parse_geocode_response` est pur (testable)."""
from __future__ import annotations

import time

import httpx

from backend.app.core.config import settings

GEOCODE_URL = "https://data.geopf.fr/geocodage/search"
# L'IGN autorise 50 req/s/IP ; on plafonne largement en dessous (§5).
_THROTTLE_SECONDS = 0.05


def parse_geocode_response(payload: dict) -> dict | None:
    """Extrait lat/lon/insee/score du 1er résultat d'une FeatureCollection IGN."""
    features = payload.get("features") or []
    if not features:
        return None
    feature = features[0]
    coords = (feature.get("geometry") or {}).get("coordinates") or []
    if len(coords) < 2 or coords[0] is None or coords[1] is None:
        return None
    props = feature.get("properties") or {}
    return {
        "longitude": float(coords[0]),
        "latitude": float(coords[1]),
        "insee_code": props.get("citycode"),
        "score": props.get("score"),
        "label": props.get("label"),
    }


def geocode_place(
    city: str | None, postcode: str | None, client: httpx.Client | None = None
) -> dict | None:
    """Géocode une commune (ville + code postal) -> {latitude, longitude, insee_code, score}."""
    # strip AVANT le repli : une ville faite d'espaces ne doit pas bloquer le repli sur le CP.
    query = (city or "").strip() or (postcode or "").strip()
    if not query:
        return None
    params = {"q": query, "type": "municipality", "limit": 1}
    if postcode:
        params["postcode"] = postcode
    owns = client is None
    client = client or httpx.Client(
        timeout=30.0, headers={"User-Agent": settings.user_agent}
    )
    try:
        resp = client.get(GEOCODE_URL, params=params)
        resp.raise_for_status()
        result = parse_geocode_response(resp.json())
        time.sleep(_THROTTLE_SECONDS)
        return result
    finally:
        if owns:
            client.close()
