"""Analyse régionale hors-base du marché DVF (prix de TRANSACTION, §26, §160).

Fonctions PURES opérant sur un DataFrame de transactions déjà reconstruites
(`pipelines.dvf.reconstruct.reconstruct`). Aucune base de données : on agrège des
médianes/quartiles de €/m² robustes par département, par an et par commune.

⚠ On ne raisonne QUE sur le prix payé (DVF). Jamais de prix demandé ici, jamais de
jugement « surévalué » : uniquement des médianes de prix constatés (§66).
"""

from __future__ import annotations

import polars as pl

from pipelines.dvf.source import MAX_PLAUSIBLE_PPM2, MIN_PLAUSIBLE_PPM2

# Groupes de départements nommés (extensible). Un « pilote » ou une région = une liste.
REGIONS: dict[str, list[str]] = {
    "bretagne": ["22", "29", "35", "56"],
    "gironde": ["33"],
    "nouvelle-aquitaine-littoral": ["33", "40", "64", "17"],
    "paca": ["06", "83", "13", "84", "04", "05"],
}

# Noms de départements (repli sur le code si absent). Étendre au besoin.
DEPARTMENT_NAMES: dict[str, str] = {
    "17": "Charente-Maritime",
    "22": "Côtes-d'Armor",
    "29": "Finistère",
    "33": "Gironde",
    "35": "Ille-et-Vilaine",
    "40": "Landes",
    "56": "Morbihan",
    "64": "Pyrénées-Atlantiques",
}

MIN_SAMPLE_DEFAULT = 20  # en dessous : médiane communale jugée peu robuste (§159)


def dep_name(dep: str) -> str:
    return DEPARTMENT_NAMES.get(dep, dep)


def clean_ppm2(df: pl.DataFrame) -> pl.DataFrame:
    """Transactions exploitables au €/m² : logement unique, €/m² dans la bande plausible (§76)."""
    return df.filter(
        pl.col("property_type").is_in(["HOUSE", "APARTMENT"])
        & pl.col("price_per_m2").is_not_null()
        & (pl.col("price_per_m2") >= MIN_PLAUSIBLE_PPM2)
        & (pl.col("price_per_m2") <= MAX_PLAUSIBLE_PPM2)
    )


def stats_ppm2(df: pl.DataFrame) -> dict:
    """€/m² robuste (médiane, quartiles, moyenne) sur un sous-ensemble déjà nettoyé."""
    if df.is_empty():
        return {"n": 0, "median": None, "q1": None, "q3": None, "mean": None}
    q = df.select(
        pl.col("price_per_m2").median().alias("median"),
        pl.col("price_per_m2").quantile(0.25, "linear").alias("q1"),
        pl.col("price_per_m2").quantile(0.75, "linear").alias("q3"),
        pl.col("price_per_m2").mean().alias("mean"),
    ).row(0, named=True)
    return {
        "n": df.height,
        "median": round(q["median"], 0),
        "q1": round(q["q1"], 0),
        "q3": round(q["q3"], 0),
        "mean": round(q["mean"], 0),
    }


def by_type(df: pl.DataFrame) -> dict:
    return {t: stats_ppm2(df.filter(pl.col("property_type") == t)) for t in ("HOUSE", "APARTMENT")}


def _commune_medians(clean: pl.DataFrame, min_sample: int) -> pl.DataFrame:
    # Identité d'une commune = code INSEE (+ dep). Le libellé `city` n'est PAS une clef de
    # regroupement (une variation d'orthographe entre millésimes fragmenterait la commune) :
    # on le porte comme attribut via first().
    return (
        clean.group_by(["insee_code", "dep"])
        .agg(
            pl.len().alias("n"),
            pl.col("price_per_m2").median().round(0).alias("median_ppm2"),
            pl.col("city").first().alias("city"),
        )
        .filter(pl.col("n") >= min_sample)
    )


def _rows(df: pl.DataFrame) -> list[dict]:
    return [
        {
            "insee": r["insee_code"],
            "commune": r["city"],
            "dep": r["dep"],
            "median_ppm2": r["median_ppm2"],
            "n": int(r["n"]),
        }
        for r in df.to_dicts()
    ]


def regional_summary(
    df: pl.DataFrame,
    *,
    departments: list[str],
    years: list[int],
    min_sample: int = MIN_SAMPLE_DEFAULT,
    meta: dict | None = None,
    top_n: int = 20,
) -> dict:
    """Construit l'agrégat régional complet à partir des transactions reconstruites.

    `df` doit contenir : dep (str), year (int), property_type, price_per_m2, insee_code,
    city, quality_flag. Renvoie un dict JSON-sérialisable (volumes, prix, tendance, tops, qualité).
    """
    clean = clean_ppm2(df)
    result: dict = {
        "period": f"{min(years)}-{max(years)}" if years else None,
        "departments": departments,
        "meta": meta or {"transactions": df.height},
    }

    # Volumes de ventes par département et par an.
    result["volumes"] = {
        dep: {
            str(y): int(df.filter((pl.col("dep") == dep) & (pl.col("year") == y)).height)
            for y in years
        }
        for dep in departments
    }

    # Répartition par type de bien (région).
    typ = df.group_by("property_type").agg(pl.len().alias("n")).sort("n", descending=True)
    result["type_mix_region"] = {r["property_type"]: int(r["n"]) for r in typ.to_dicts()}

    # Prix par département (période entière) + région.
    result["prix_departement"] = {}
    for dep in departments:
        d = clean.filter(pl.col("dep") == dep)
        result["prix_departement"][dep] = {
            "nom": dep_name(dep),
            "global": stats_ppm2(d),
            "par_type": by_type(d),
        }
    result["prix_region"] = {"global": stats_ppm2(clean), "par_type": by_type(clean)}

    # Tendance : médiane €/m² par an et par département (maison / appartement).
    trend: dict = {}
    for dep in departments:
        trend[dep] = {}
        for y in years:
            sub = clean.filter((pl.col("dep") == dep) & (pl.col("year") == y))
            trend[dep][str(y)] = {
                "HOUSE": stats_ppm2(sub.filter(pl.col("property_type") == "HOUSE"))["median"],
                "APARTMENT": stats_ppm2(sub.filter(pl.col("property_type") == "APARTMENT"))[
                    "median"
                ],
                "n": sub.height,
            }
    result["tendance_annuelle"] = trend

    # Tops de communes (échantillon suffisant). Départage déterministe (insee_code, clef unique)
    # car le JSON produit est un livrable : le tri ne doit pas dépendre de l'ordre (non garanti)
    # de group_by ni du nombre de threads, notamment quand median_ppm2 (arrondi) crée des ex aequo.
    commune = _commune_medians(clean, min_sample)
    result["top_communes_cheres"] = _rows(
        commune.sort(["median_ppm2", "n", "insee_code"], descending=[True, True, False]).head(top_n)
    )
    result["top_communes_volume"] = _rows(
        commune.sort(["n", "median_ppm2", "insee_code"], descending=[True, True, False]).head(top_n)
    )
    result["communes_moins_cheres"] = _rows(
        commune.sort(["median_ppm2", "n", "insee_code"], descending=[False, True, False]).head(
            top_n
        )
    )

    # Qualité / transparence.
    result["qualite"] = {
        "transactions_reconstruites": df.height,
        "transactions_avec_drapeau_qualite": df.filter(pl.col("quality_flag").is_not_null()).height,
        "transactions_exploitables_ppm2": clean.height,
        **(meta or {}),
    }
    return result
