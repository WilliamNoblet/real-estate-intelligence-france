"""Détection d'un « vendeur pressé » à partir de l'historique d'une annonce (logique PURE).

Objectif métier (demande utilisateur) : repérer les annonces dont le comportement de prix
suggère un vendeur pressé — baisses répétées, rapides et/ou importantes — ce qui *peut*
correspondre à une succession/un héritage, une mutation, un divorce, une correction d'un prix
initial trop haut, etc.

⚠ SIGNAL PROBABILISTE, JAMAIS UNE CONCLUSION (§66). On ne dit jamais « c'est une succession » :
on renvoie un score, un niveau et des motifs factuels (« 3 baisses », « −12 % »). La cause exacte
n'est pas observable dans les données publiques et une succession n'est qu'UNE explication parmi
plusieurs. Aucune donnée personnelle n'entre dans ce calcul.

S'appuie sur `pipelines.listings.history.listing_indicators` (baisse cumulée %, nombre de baisses,
délai avant 1ʳᵉ baisse). Ne nécessite ni base ni réseau : s'activera dès que la collecte d'annonces
alimentera l'historique (snapshots).
"""
from __future__ import annotations

from dataclasses import dataclass

# Rappel affiché en tête de toute restitution : le signal ne conclut rien sur la cause.
DISCLAIMER = (
    "Signal indicatif de vendeur possiblement pressé — hypothèse à confirmer, "
    "jamais une certitude. Une succession n'est qu'une cause possible parmi d'autres "
    "(mutation, divorce, prix initial trop haut…)."
)


@dataclass(frozen=True)
class RapidSaleConfig:
    """Seuils calibrables (à ajuster sur données réelles, §58). Non-secrets → versionnables."""

    drop_pct_full: float = 20.0   # baisse (%) au-delà de laquelle le sous-signal « ampleur » = 1
    drops_full: int = 3           # nb de baisses au-delà duquel le sous-signal « répétition » = 1
    quick_drop_days: int = 60     # 1ʳᵉ baisse en deçà de ce délai → sous-signal « rapidité »
    w_magnitude: float = 0.5      # poids ampleur de la baisse cumulée
    w_count: float = 0.3          # poids répétition des baisses
    w_speed: float = 0.2          # poids rapidité de la première baisse
    flag_threshold: float = 0.5   # score ≥ seuil → annonce signalée
    watch_threshold: float = 0.33 # score ≥ seuil → « à surveiller »


def _clamp01(x: float) -> float:
    return 0.0 if x < 0 else (1.0 if x > 1 else x)


def rapid_sale_signal(indicators: dict, config: RapidSaleConfig | None = None) -> dict:
    """Score de « vendeur pressé » ∈ [0,1] à partir des indicateurs d'une annonce.

    `indicators` : sortie de `listing_indicators` (total_price_drop_pct, price_decrease_count,
    days_before_first_drop). Renvoie score, niveau, flag, sous-composantes et motifs factuels.
    """
    cfg = config or RapidSaleConfig()
    drop_pct = indicators.get("total_price_drop_pct")          # négatif si baisse
    decreases = indicators.get("price_decrease_count") or 0
    days_first = indicators.get("days_before_first_drop")

    # Sans aucune baisse observée, pas de signal (une annonce stable n'est pas « pressée »).
    if decreases <= 0 or not drop_pct or drop_pct >= 0:
        return {
            "score": 0.0, "level": "aucun", "flag": False,
            "components": {"magnitude": 0.0, "count": 0.0, "speed": 0.0},
            "reasons": [], "disclaimer": DISCLAIMER,
        }

    magnitude = _clamp01(-drop_pct / cfg.drop_pct_full)
    count = _clamp01(decreases / cfg.drops_full)
    speed = (
        _clamp01(1 - days_first / cfg.quick_drop_days)
        if days_first is not None and days_first >= 0
        else 0.0
    )

    score = round(cfg.w_magnitude * magnitude + cfg.w_count * count + cfg.w_speed * speed, 3)
    level = (
        "élevé" if score >= 0.66
        else ("à surveiller" if score >= cfg.watch_threshold else "faible")
    )

    reasons: list[str] = [f"baisse cumulée de {abs(drop_pct):.1f} %"]
    if decreases >= 2:
        reasons.append(f"{decreases} baisses successives")
    if days_first is not None and days_first >= 0:
        reasons.append(f"1ʳᵉ baisse après {days_first} jour" + ("s" if days_first != 1 else ""))

    return {
        "score": score,
        "level": level,
        "flag": score >= cfg.flag_threshold,
        "components": {
            "magnitude": round(magnitude, 3),
            "count": round(count, 3),
            "speed": round(speed, 3),
        },
        "reasons": reasons,
        "disclaimer": DISCLAIMER,
    }


def rank_motivated_sellers(
    items: list[tuple], config: RapidSaleConfig | None = None, only_flagged: bool = True
) -> list[dict]:
    """Classe des annonces par score de vendeur pressé (décroissant).

    `items` : liste de (identifiant, indicators). Renvoie une liste de dicts
    {id, score, level, reasons, ...}, triée. Utile pour un futur « top annonces à surveiller ».
    """
    out = []
    for ident, indicators in items:
        sig = rapid_sale_signal(indicators, config)
        if only_flagged and not sig["flag"]:
            continue
        out.append({"id": ident, **sig})
    out.sort(key=lambda r: r["score"], reverse=True)
    return out
