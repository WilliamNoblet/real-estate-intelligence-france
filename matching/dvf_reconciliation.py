"""Rapprochement PROBABILISTE annonce ↔ transaction DVF (§61, §198).

Objectif : estimer, pour une annonce retirée, quelle transaction DVF pourrait correspondre à sa
vente réelle. Le résultat est TOUJOURS une confiance, jamais une certitude (§61, §66) :
on n'affirme jamais « ce bien a été vendu à X ».

Le scoring `score_dvf_match` est PUR (dicts en entrée) et donc testable/calibrable isolément.
Features : type (éliminatoire), commune, surface, chronologie (mutation autour du retrait),
plausibilité de prix (transaction généralement ≤ dernier prix demandé)."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import DVFMatchCandidate, Listing, ListingSnapshot, TransactionDVF
from backend.app.models.enums import PropertyType

MATCHING_VERSION = "dvf-recon-0.1"

# Poids (somme = 1.0). Point de départ à calibrer sur données réelles (§58).
_W_COMMUNE = 0.25
_W_SURFACE = 0.30
_W_CHRONO = 0.25
_W_PRICE = 0.20


def _chrono_weight(delta_days: int) -> float:
    """Poids de plausibilité chronologique : la mutation survient autour du retrait de l'annonce.
    Pic sur 0–120 j après le retrait ; décroissance avant/après ; nul hors [-90, 540] jours."""
    if 0 <= delta_days <= 120:
        return 1.0
    if -90 <= delta_days < 0:
        return 1.0 - (-delta_days) / 90.0
    if 120 < delta_days <= 540:
        return max(0.0, 1.0 - (delta_days - 120) / 420.0)
    return 0.0


def score_dvf_match(
    listing: dict,
    txn: dict,
    *,
    surface_tol: float = 0.15,
    price_margin: float = 0.25,
) -> tuple[float, dict]:
    """Confiance [0..1] qu'une transaction DVF corresponde à une annonce, + features.

    listing : {property_type, surface_m2, asking_price, removal_date, insee_code}
    txn      : {property_type, surface_m2, sale_price, mutation_date, insee_code}
    Le type est ÉLIMINATOIRE : types différents -> confiance 0."""
    features: dict = {}

    # Type ÉLIMINATOIRE : exclut aussi UNKNOWN (deux types INCONNUS ne valident pas un match).
    pt = listing.get("property_type")
    type_ok = pt is not None and pt != PropertyType.UNKNOWN and pt == txn.get("property_type")
    features["type_match"] = bool(type_ok)
    if not type_ok:
        return 0.0, features

    score = 0.0

    same_commune = bool(
        listing.get("insee_code") and listing.get("insee_code") == txn.get("insee_code")
    )
    features["same_commune"] = same_commune
    if same_commune:
        score += _W_COMMUNE

    ls, ts = listing.get("surface_m2"), txn.get("surface_m2")
    if ls and ts and ls > 0:
        ratio = abs(ts - ls) / ls
        features["surface_ratio_diff"] = round(ratio, 3)
        if ratio <= surface_tol:
            score += _W_SURFACE * (1.0 - ratio / surface_tol)

    removal, mutation = listing.get("removal_date"), txn.get("mutation_date")
    if isinstance(removal, dt.date) and isinstance(mutation, dt.date):
        delta = (mutation - removal).days
        features["mutation_minus_removal_days"] = delta
        score += _W_CHRONO * _chrono_weight(delta)

    asking, sale = listing.get("asking_price"), txn.get("sale_price")
    if asking and sale and asking > 0:
        gap = (sale - asking) / asking  # < 0 : vendu moins cher que demandé (cas usuel)
        features["price_gap"] = round(gap, 3)
        if -2.0 * price_margin <= gap <= 0.10:
            score += _W_PRICE * (1.0 - min(abs(gap), price_margin) / price_margin)

    return round(min(score, 1.0), 3), features


def find_dvf_candidates(
    session: Session,
    listing_id: int,
    min_confidence: float = 0.5,
    limit: int = 10,
    persist: bool = False,
) -> list[dict]:
    """Transactions DVF potentiellement correspondantes à une annonce, triées par confiance.

    Nécessite que l'annonce soit géocodée (insee_code). Résultat PROBABILISTE (§61) : ne jamais
    présenter comme certain. Filtre grossier par commune + type, puis scoring fin en Python."""
    listing = session.get(Listing, listing_id)
    # Nécessite une annonce géocodée (insee) ET un type CONNU (le type inconnu n'autorise pas
    # un rapprochement fiable — §61).
    if listing is None or not listing.insee_code or listing.property_type == PropertyType.UNKNOWN:
        return []

    snap = session.execute(
        select(ListingSnapshot.surface_m2, ListingSnapshot.price_eur)
        .where(ListingSnapshot.listing_id == listing_id)
        .order_by(ListingSnapshot.observed_at.desc(), ListingSnapshot.id.desc())
        .limit(1)
    ).first()
    listing_features = {
        "property_type": listing.property_type,
        "insee_code": listing.insee_code,
        "surface_m2": float(snap.surface_m2) if snap and snap.surface_m2 is not None else None,
        "asking_price": float(snap.price_eur) if snap and snap.price_eur is not None else None,
        "removal_date": listing.last_seen_at.date() if listing.last_seen_at else None,
    }

    txns = session.execute(
        select(TransactionDVF).where(
            TransactionDVF.insee_code == listing.insee_code,
            TransactionDVF.property_type == listing.property_type,
        )
    ).scalars().all()

    candidates: list[dict] = []
    for t in txns:
        txn_features = {
            "property_type": t.property_type,
            "insee_code": t.insee_code,
            "surface_m2": float(t.surface_m2) if t.surface_m2 is not None else None,
            "sale_price": float(t.sale_price) if t.sale_price is not None else None,
            "mutation_date": t.mutation_date,
        }
        confidence, feats = score_dvf_match(listing_features, txn_features)
        if confidence >= min_confidence:
            candidates.append(
                {
                    "transaction_dvf_id": t.id,
                    "id_mutation": t.id_mutation,
                    "confidence": confidence,
                    "sale_price": txn_features["sale_price"],
                    "mutation_date": t.mutation_date.isoformat() if t.mutation_date else None,
                    "features": feats,
                }
            )

    candidates.sort(key=lambda c: c["confidence"], reverse=True)
    candidates = candidates[:limit]

    if persist:
        for c in candidates:
            session.add(
                DVFMatchCandidate(
                    listing_id=listing_id,
                    transaction_dvf_id=c["transaction_dvf_id"],
                    confidence=c["confidence"],
                    matching_version=MATCHING_VERSION,
                    matching_features=c["features"],
                )
            )
        session.commit()

    return candidates
