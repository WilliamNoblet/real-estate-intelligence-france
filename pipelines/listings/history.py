"""Moteur d'historisation des annonces (Phase 6) — logique pure.

- payload_hash sur les champs signifiants → décider si un nouveau snapshot est nécessaire (§41).
- has_meaningful_change(prev, curr) (§40).
- diff_events(prev, curr) → événements typés (PRICE_DECREASE/INCREASE, DESCRIPTION_CHANGED,
  PROPERTY_DETAILS_CHANGED) avec variation_eur / variation_pct (§45).
- listing_indicators(snapshots) → prix initial/actuel/min, baisse cumulée, nombre de baisses,
  durée observée, délai avant première baisse (§46-47).

Fonctionne sur des dicts « snapshot-like » ou des NormalizedListing (Pydantic)."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import unicodedata
from typing import Any

from backend.app.models.enums import EventType, ListingStatus

# Champs dont un changement est « significatif » (§40).
DETAIL_FIELDS = [
    "surface_m2", "land_surface_m2", "rooms", "bedrooms", "energy_rating", "ghg_rating",
]


def _as_dict(data: Any) -> dict:
    if hasattr(data, "model_dump"):
        return data.model_dump()
    if isinstance(data, dict):
        return data
    raise TypeError(f"attendu dict ou modèle Pydantic, reçu {type(data)!r}")


def normalized_text_hash(text: str | None) -> str | None:
    """Hash d'un texte normalisé (minuscules, sans accents/ponctuation, espaces réduits — §56)."""
    if not text:
        return None
    lowered = text.lower()
    no_accents = "".join(
        c for c in unicodedata.normalize("NFKD", lowered) if not unicodedata.combining(c)
    )
    cleaned = re.sub(r"[^\w\s]", " ", no_accents)
    collapsed = re.sub(r"\s+", " ", cleaned).strip()
    if not collapsed:
        return None
    return hashlib.sha256(collapsed.encode("utf-8")).hexdigest()


def _significant(data: Any) -> dict:
    d = _as_dict(data)
    title = (d.get("title") or "").strip() or None
    return {
        "price_eur": d.get("price_eur"),
        "surface_m2": d.get("surface_m2"),
        "land_surface_m2": d.get("land_surface_m2"),
        "rooms": d.get("rooms"),
        "bedrooms": d.get("bedrooms"),
        "energy_rating": d.get("energy_rating"),
        "ghg_rating": d.get("ghg_rating"),
        # property_type n'entre PAS ici : il n'est pas stocké dans le snapshot ni diffé
        # (c'est un attribut du bien/annonce, pas de l'observation) → pas de snapshot fantôme.
        "title": title,
        # Accepte un description_hash déjà stocké (snapshot) ou le calcule depuis le texte brut.
        "description_hash": d.get("description_hash") or normalized_text_hash(d.get("description")),
        "agency_name": d.get("agency_name"),
    }


def compute_payload_hash(data: Any) -> str:
    """Empreinte normalisée des champs signifiants (§41)."""
    payload = json.dumps(_significant(data), sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def has_meaningful_change(prev: Any, curr: Any) -> bool:
    """True si un champ signifiant a changé entre l'observation précédente et la nouvelle (§40)."""
    return compute_payload_hash(prev) != compute_payload_hash(curr)


def _price_pct(old: float, new: float) -> float | None:
    if old is None or new is None or old == 0:
        return None
    return round((new - old) / old * 100, 2)


def diff_events(prev: Any, curr: Any, event_date: dt.datetime) -> list[dict]:
    """Événements typés entre deux observations. Ne modifie jamais l'historique (§86)."""
    p, c = _significant(prev), _significant(curr)
    events: list[dict] = []

    old_price, new_price = p["price_eur"], c["price_eur"]
    if old_price is not None and new_price is not None and old_price != new_price:
        variation_eur = round(new_price - old_price, 2)
        variation_pct = _price_pct(old_price, new_price)
        event_type = EventType.PRICE_DECREASE if new_price < old_price else EventType.PRICE_INCREASE
        events.append(
            {
                "event_type": event_type,
                "event_date": event_date,
                "old_value": str(old_price),
                "new_value": str(new_price),
                "metadata": {"variation_eur": variation_eur, "variation_pct": variation_pct},
            }
        )

    if p["description_hash"] != c["description_hash"]:
        events.append(
            {
                "event_type": EventType.DESCRIPTION_CHANGED,
                "event_date": event_date,
                "old_value": None,
                "new_value": None,
                "metadata": None,
            }
        )

    changed_details = [f for f in DETAIL_FIELDS if p.get(f) != c.get(f)]
    if changed_details:
        events.append(
            {
                "event_type": EventType.PROPERTY_DETAILS_CHANGED,
                "event_date": event_date,
                "old_value": None,
                "new_value": None,
                "metadata": {
                    "changed": {f: {"old": p.get(f), "new": c.get(f)} for f in changed_details}
                },
            }
        )
    return events


def listing_indicators(snapshots: list[dict]) -> dict:
    """Indicateurs dérivés d'une annonce, reconstruits depuis ses snapshots (§46-47).

    Chaque snapshot est un dict avec au moins `observed_at` (datetime) et `price_eur`."""
    if not snapshots:
        return {}
    ordered = sorted(snapshots, key=lambda s: s["observed_at"])
    first_seen = ordered[0]["observed_at"]
    last_seen = ordered[-1]["observed_at"]

    priced = [s for s in ordered if s.get("price_eur") is not None]
    prices = [s["price_eur"] for s in priced]

    initial_price = prices[0] if prices else None
    current_price = prices[-1] if prices else None
    lowest_price = min(prices) if prices else None
    highest_price = max(prices) if prices else None

    total_drop_eur = (
        round(current_price - initial_price, 2)
        if initial_price is not None and current_price is not None
        else None
    )
    total_drop_pct = _price_pct(initial_price, current_price) if initial_price else None

    decreases = increases = 0
    first_drop_at: dt.datetime | None = None
    for older, newer in zip(priced, priced[1:], strict=False):
        if newer["price_eur"] < older["price_eur"]:
            decreases += 1
            if first_drop_at is None:
                first_drop_at = newer["observed_at"]
        elif newer["price_eur"] > older["price_eur"]:
            increases += 1

    days_before_first_drop = (first_drop_at - first_seen).days if first_drop_at else None

    return {
        "initial_price": initial_price,
        "current_price": current_price,
        "lowest_price": lowest_price,
        "highest_price": highest_price,
        "total_price_drop_eur": total_drop_eur,
        "total_price_drop_pct": total_drop_pct,
        "price_change_count": decreases + increases,
        "price_decrease_count": decreases,
        "price_increase_count": increases,
        "first_seen_at": first_seen,
        "last_seen_at": last_seen,
        "observed_days_online": (last_seen - first_seen).days,
        "days_before_first_drop": days_before_first_drop,
    }


def transition(
    current: ListingStatus, found: bool, consecutive_missing: int, threshold: int
) -> tuple[ListingStatus, EventType | None]:
    """Machine à états d'une annonce (§50, §157). Renvoie (nouveau_statut, event_type | None).

    Une annonce absente n'est jamais « vendue » : elle passe MISSING puis REMOVED après
    `threshold` vérifications négatives consécutives (§49-50)."""
    if found:
        if current == ListingStatus.REMOVED:
            return ListingStatus.REAPPEARED, EventType.LISTING_REAPPEARED
        return ListingStatus.ACTIVE, None
    # Non trouvée.
    if consecutive_missing >= threshold:
        if current != ListingStatus.REMOVED:
            return ListingStatus.REMOVED, EventType.LISTING_REMOVED
        return ListingStatus.REMOVED, None
    if current != ListingStatus.MISSING:
        return ListingStatus.MISSING, EventType.LISTING_MISSING
    return ListingStatus.MISSING, None
