"""Détection de vendeur pressé (analytics.motivated_seller) — logique PURE.

Vérifie le scoring (ampleur/répétition/rapidité des baisses), les niveaux, le drapeau,
le tri, et l'absence de conclusion catégorique (signal probabiliste, §66)."""
from __future__ import annotations

from analytics.motivated_seller import (
    DISCLAIMER,
    RapidSaleConfig,
    rank_motivated_sellers,
    rapid_sale_signal,
)


def _ind(pct, dec, days):
    return {
        "total_price_drop_pct": pct,
        "price_decrease_count": dec,
        "days_before_first_drop": days,
    }


def _norm(reasons):
    # Les motifs utilisent l'espace insécable (typographie FR) : on normalise pour tester.
    return [r.replace(" ", " ") for r in reasons]


def test_aucune_baisse_pas_de_signal():
    sig = rapid_sale_signal(_ind(None, 0, None))
    assert sig["score"] == 0.0 and sig["level"] == "aucun" and sig["flag"] is False
    assert sig["reasons"] == []


def test_hausse_de_prix_pas_de_signal():
    # Un prix qui monte (drop_pct positif) n'est pas un vendeur pressé.
    assert rapid_sale_signal(_ind(6.0, 0, None))["score"] == 0.0


def test_cas_fort():
    sig = rapid_sale_signal(_ind(-18.0, 3, 10))
    reasons = _norm(sig["reasons"])
    assert sig["flag"] is True
    assert sig["level"] == "élevé"
    assert sig["score"] > 0.85
    assert any("18.0 %" in r for r in reasons)
    assert any("3 baisses" in r for r in reasons)
    assert any("10 jours" in r for r in reasons)


def test_cas_faible_non_signale():
    sig = rapid_sale_signal(_ind(-4.0, 1, 120))
    assert sig["flag"] is False
    assert sig["level"] == "faible"
    assert sig["components"]["speed"] == 0.0  # 1re baisse tardive -> rapidité nulle


def test_seuil_a_surveiller():
    # -10 %, 2 baisses, 1re à 45 j -> score pile au seuil de signalement, niveau intermédiaire.
    sig = rapid_sale_signal(_ind(-10.0, 2, 45))
    assert sig["score"] == 0.5
    assert sig["flag"] is True
    assert sig["level"] == "à surveiller"


def test_pluriel_singulier_jour():
    reasons = _norm(rapid_sale_signal(_ind(-9.0, 2, 1))["reasons"])
    day_reason = [r for r in reasons if "baisse après" in r][0]
    assert day_reason.endswith("1 jour")  # singulier (pas « jours »)


def test_config_personnalisee():
    # Seuil de flag plus strict -> le même cas n'est plus signalé.
    strict = RapidSaleConfig(flag_threshold=0.95)
    assert rapid_sale_signal(_ind(-18.0, 3, 10), strict)["flag"] is False


def test_classement_filtre_et_trie():
    items = [
        ("faible", _ind(-4.0, 1, 120)),
        ("fort", _ind(-18.0, 3, 10)),
        ("moyen", _ind(-10.0, 2, 45)),
    ]
    ranked = rank_motivated_sellers(items)
    ids = [r["id"] for r in ranked]
    assert ids == ["fort", "moyen"]  # "faible" filtré (non signalé), tri décroissant
    assert ranked[0]["score"] >= ranked[1]["score"]
    # Sans filtre, les trois sont présents.
    assert len(rank_motivated_sellers(items, only_flagged=False)) == 3


def test_disclaimer_probabiliste():
    # Le signal ne conclut jamais : le disclaimer parle d'hypothèse, pas de certitude.
    sig = rapid_sale_signal(_ind(-18.0, 3, 10))
    assert sig["disclaimer"] == DISCLAIMER
    assert "hypothèse" in DISCLAIMER and "jamais une certitude" in DISCLAIMER
