"""Reconstruction des transactions DVF à partir des lignes brutes geo-dvf.

RÈGLE FONDAMENTALE (§26) : 1 ligne DVF ≠ 1 vente. Une mutation s'éclate sur plusieurs
lignes (par local / parcelle) et `valeur_fonciere` est RÉPÉTÉE — on ne la somme jamais.
On regroupe par `id_mutation` → 1 transaction. Règles de reconstruction documentées dans
docs/dvf-reconstruction.md."""
from __future__ import annotations

import polars as pl

from pipelines.dvf.source import (
    HABITABLE_TYPES,
    MAX_PLAUSIBLE_PPM2,
    MAX_SURFACE_M2,
    MIN_PLAUSIBLE_PPM2,
    SALE_NATURES,
    USED_COLUMNS,
)

_DTYPES = {
    "id_mutation": pl.Utf8,
    "date_mutation": pl.Utf8,
    "nature_mutation": pl.Utf8,
    "valeur_fonciere": pl.Float64,
    "code_postal": pl.Utf8,
    "code_commune": pl.Utf8,
    "nom_commune": pl.Utf8,
    "code_departement": pl.Utf8,
    "id_parcelle": pl.Utf8,
    "type_local": pl.Utf8,
    "surface_reelle_bati": pl.Float64,
    "nombre_pieces_principales": pl.Float64,
    "surface_terrain": pl.Float64,
    "longitude": pl.Float64,
    "latitude": pl.Float64,
}

# Colonnes de sortie (alignées sur le modèle transaction_dvf).
OUTPUT_COLUMNS = [
    "id_mutation",
    "mutation_date",
    "mutation_type",
    "sale_price",
    "property_type",
    "surface_m2",
    "land_surface_m2",
    "rooms",
    "city",
    "postal_code",
    "insee_code",
    "latitude",
    "longitude",
    "parcel_id",
    "price_per_m2",
    "source_year",
    "quality_flag",
]


def read_geodvf_csv(path: str) -> pl.DataFrame:
    """Lit un CSV geo-dvf (gzip ou non), en ne gardant que les colonnes utiles et en
    forçant les codes en texte (préserve les zéros initiaux des codes INSEE/postaux)."""
    return pl.read_csv(path, columns=USED_COLUMNS, schema_overrides=_DTYPES)


def reconstruct(raw: pl.DataFrame, source_year: int) -> pl.DataFrame:
    """Regroupe les lignes brutes en transactions (une par mutation de vente)."""
    # 1) Ne garder que les mutations de vente ; le reste est rejeté.
    sales = raw.filter(pl.col("nature_mutation").is_in(list(SALE_NATURES)))
    if sales.is_empty():
        return pl.DataFrame(schema={c: pl.Utf8 for c in OUTPUT_COLUMNS})

    habitable = pl.col("type_local").is_in(HABITABLE_TYPES)

    # 2) Agrégation par mutation. valeur_fonciere : max (répétée), JAMAIS somme.
    agg = sales.group_by("id_mutation").agg(
        pl.col("valeur_fonciere").max().alias("sale_price"),
        pl.col("date_mutation").first().alias("mutation_date"),
        pl.col("nature_mutation").first().alias("mutation_type"),
        pl.col("code_commune").first().alias("insee_code"),
        pl.col("nom_commune").first().alias("city"),
        pl.col("code_postal").first().alias("postal_code"),
        (pl.col("type_local") == "Maison").sum().alias("n_maison"),
        (pl.col("type_local") == "Appartement").sum().alias("n_appart"),
        pl.col("surface_reelle_bati").filter(habitable).sum().alias("surface_m2"),
        pl.col("nombre_pieces_principales").filter(habitable).sum().alias("rooms"),
        pl.col("id_parcelle").first().alias("parcel_id"),
        pl.col("longitude").drop_nulls().first().alias("longitude"),
        pl.col("latitude").drop_nulls().first().alias("latitude"),
    )

    # 3) Surface de terrain : somme des parcelles DISTINCTES (surface_terrain est répétée
    #    sur chaque local d'une même parcelle → on dédoublonne par parcelle avant de sommer).
    land = (
        sales.filter(pl.col("surface_terrain").is_not_null())
        .group_by(["id_mutation", "id_parcelle"])
        .agg(pl.col("surface_terrain").max().alias("_pt"))
        .group_by("id_mutation")
        .agg(pl.col("_pt").sum().alias("land_surface_m2"))
    )
    agg = agg.join(land, on="id_mutation", how="left")

    # 4) Classification du bien + normalisations.
    agg = agg.with_columns(
        pl.when((pl.col("n_maison") == 1) & (pl.col("n_appart") == 0))
        .then(pl.lit("HOUSE"))
        .when((pl.col("n_appart") == 1) & (pl.col("n_maison") == 0))
        .then(pl.lit("APARTMENT"))
        .when((pl.col("n_maison") + pl.col("n_appart") == 0) & (pl.col("land_surface_m2") > 0))
        .then(pl.lit("LAND"))
        .when(pl.col("n_maison") + pl.col("n_appart") >= 1)
        .then(pl.lit("OTHER"))
        .otherwise(pl.lit("OTHER"))
        .alias("property_type"),
        (pl.col("n_maison") + pl.col("n_appart") > 1).alias("is_multi"),
    ).with_columns(
        # Surfaces/pièces à 0 → NULL (absence, pas zéro — §158).
        pl.when(pl.col("surface_m2") > 0)
        .then(pl.col("surface_m2"))
        .otherwise(None)
        .alias("surface_m2"),
        pl.when(pl.col("rooms") > 0)
        .then(pl.col("rooms").cast(pl.Int32))
        .otherwise(None)
        .alias("rooms"),
        pl.col("mutation_date").str.to_date(strict=False).alias("mutation_date"),
        pl.lit(source_year).alias("source_year"),
    )

    # 5) €/m² : uniquement pour un logement unique (maison/appartement) avec surface et prix.
    single = pl.col("property_type").is_in(["HOUSE", "APARTMENT"]) & ~pl.col("is_multi")
    agg = agg.with_columns(
        pl.when(
            single
            & pl.col("surface_m2").is_not_null()
            & (pl.col("surface_m2") > 0)
            & pl.col("sale_price").is_not_null()
            & (pl.col("sale_price") > 0)
        )
        .then((pl.col("sale_price") / pl.col("surface_m2")).round(2))
        .otherwise(None)
        .alias("price_per_m2")
    )

    # 6) Drapeaux qualité (§76). Concaténés en une chaîne "flag1;flag2" ou NULL.
    no_price = pl.col("sale_price").is_null() | (pl.col("sale_price") <= 0)
    no_surface = pl.col("property_type").is_in(["HOUSE", "APARTMENT"]) & pl.col(
        "surface_m2"
    ).is_null()
    surface_big = pl.col("surface_m2") > MAX_SURFACE_M2
    extreme_ppm2 = pl.col("price_per_m2").is_not_null() & (
        (pl.col("price_per_m2") < MIN_PLAUSIBLE_PPM2)
        | (pl.col("price_per_m2") > MAX_PLAUSIBLE_PPM2)
    )
    flags = (
        pl.concat_list(
            [
                pl.when(pl.col("is_multi")).then(pl.lit("multi_bien")).otherwise(None),
                pl.when(no_price).then(pl.lit("no_price")).otherwise(None),
                pl.when(no_surface).then(pl.lit("no_surface")).otherwise(None),
                pl.when(surface_big).then(pl.lit("surface_gt_5000")).otherwise(None),
                pl.when(extreme_ppm2).then(pl.lit("extreme_ppm2")).otherwise(None),
            ]
        )
        .list.drop_nulls()
        .list.join(";")
    )
    agg = agg.with_columns(
        pl.when(flags.str.len_chars() > 0).then(flags).otherwise(None).alias("quality_flag")
    )

    return agg.select(OUTPUT_COLUMNS)


def count_rejected_rows(raw: pl.DataFrame) -> int:
    """Nombre de lignes hors périmètre 'vente' (échange, expropriation, donation…)."""
    return raw.filter(~pl.col("nature_mutation").is_in(list(SALE_NATURES))).height
