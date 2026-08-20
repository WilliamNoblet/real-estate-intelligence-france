"""Analyse régionale DVF hors-base — sans Docker ni PostgreSQL.

Télécharge (une fois, idempotent §23-24) les fichiers geo-dvf départementaux, reconstruit
les transactions avec les MÊMES règles que l'ingestion (`pipelines.dvf.reconstruct`) puis
agrège des statistiques robustes de prix PAYÉ au m² (`analytics.regional`).

Exemples :
    python -m scripts.analyse_dvf_regionale --region bretagne
    python -m scripts.analyse_dvf_regionale --departments 22 29 35 56 --years 2023 2024 2025
    python -m scripts.analyse_dvf_regionale --region gironde --no-download   # réutilise l'existant

Sortie : data/analysis/<nom>.json (agrégats) + data/analysis/<nom>.parquet (transactions).
Aucune donnée personnelle, aucune écriture en base. Open data Etalab (Licence Ouverte 2.0).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import polars as pl

from analytics.regional import REGIONS, regional_summary
from backend.app.core.config import ROOT_DIR
from pipelines.dvf.client import RAW_DIR, download_department
from pipelines.dvf.reconstruct import count_rejected_rows, read_geodvf_csv, reconstruct
from pipelines.dvf.source import EXCLUDED_DEPARTMENTS

DEFAULT_YEARS = [2021, 2022, 2023, 2024, 2025]
OUT_DIR = ROOT_DIR / "data" / "analysis"


def _ensure_file(dep: str, year: int, download: bool) -> Path | None:
    """Chemin du fichier départemental ; télécharge si absent et autorisé. None si indisponible."""
    path = RAW_DIR / str(year) / f"{dep}.csv.gz"
    if path.exists() and path.stat().st_size > 10_000:
        return path
    if not download:
        print(f"  ! {dep}/{year} absent (et --no-download) — ignoré", file=sys.stderr)
        return None
    try:
        path, _sha = download_department(dep, year)
        return path
    except Exception as exc:  # noqa: BLE001 — un département/année manquant ne doit pas tout stopper
        print(f"  ! échec téléchargement {dep}/{year} : {exc}", file=sys.stderr)
        return None


def build(departments: list[str], years: list[int], download: bool, min_sample: int) -> dict:
    frames: list[pl.DataFrame] = []
    raw_lines = 0
    rejected = 0
    for dep in departments:
        if dep in EXCLUDED_DEPARTMENTS:
            print(f"  · {dep} hors périmètre DVF — ignoré", file=sys.stderr)
            continue
        for year in years:
            path = _ensure_file(dep, year, download)
            if path is None:
                continue
            try:
                raw = read_geodvf_csv(str(path))
            except Exception as exc:  # noqa: BLE001 — fichier corrompu/tronqué : sauter sans tout stopper
                print(f"  ! {dep}/{year} illisible ({exc}) — ignoré", file=sys.stderr)
                continue
            raw_lines += raw.height
            rejected += count_rejected_rows(raw)
            tx = reconstruct(raw, year).with_columns(
                pl.lit(dep).alias("dep"), pl.lit(year).alias("year")
            )
            frames.append(tx)
            print(f"  ✓ {dep}/{year} : {tx.height:,} transactions", file=sys.stderr)

    if not frames:
        raise SystemExit("Aucune donnée exploitable — vérifier départements/années/réseau.")

    df = pl.concat(frames, how="vertical")
    meta = {"raw_lines": raw_lines, "rejected_non_sale_rows": rejected, "transactions": df.height}
    kept = [d for d in departments if d not in EXCLUDED_DEPARTMENTS]
    summary = regional_summary(df, departments=kept, years=years, min_sample=min_sample, meta=meta)
    return {"summary": summary, "df": df}


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Analyse régionale DVF hors-base (prix payé au m²).")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--region", choices=sorted(REGIONS), help="Groupe de départements prédéfini.")
    g.add_argument(
        "--departments", nargs="+", metavar="DEP", help="Codes département (22 29 35 56)."
    )
    p.add_argument(
        "--years", nargs="+", type=int, default=DEFAULT_YEARS, help="Années (défaut 5 ans)."
    )
    p.add_argument(
        "--no-download", dest="download", action="store_false", help="Réutiliser l'existant."
    )
    p.add_argument("--min-sample", type=int, default=20, help="Seuil n pour une médiane communale.")
    p.add_argument("--name", default=None, help="Nom de sortie (défaut : région ou depts joints).")
    args = p.parse_args(argv)

    departments = REGIONS[args.region] if args.region else [str(d) for d in args.departments]
    name = args.name or args.region or "-".join(departments)

    print(f"Analyse DVF : {name} — dépts {departments} — années {args.years}", file=sys.stderr)
    built = build(departments, sorted(args.years), args.download, args.min_sample)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUT_DIR / f"{name}.json"
    parquet_path = OUT_DIR / f"{name}.parquet"
    json_path.write_text(
        json.dumps(built["summary"], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    built["df"].write_parquet(parquet_path)

    s = built["summary"]
    reg = s["prix_region"]["global"]
    q = s["qualite"]
    print("\n=== Résumé ===", file=sys.stderr)
    print(f"Transactions reconstruites : {q['transactions_reconstruites']:,}", file=sys.stderr)
    print(f"Exploitables au €/m²       : {q['transactions_exploitables_ppm2']:,}", file=sys.stderr)
    if reg["median"] is not None:
        print(
            f"Médiane régionale €/m²     : {reg['median']:.0f} "
            f"(Q1 {reg['q1']:.0f} / Q3 {reg['q3']:.0f})",
            file=sys.stderr,
        )
    else:
        print(
            "Médiane régionale €/m²     : n/d (aucune vente exploitable au €/m²)", file=sys.stderr
        )
    print(f"Écrit : {json_path} + {parquet_path.name}", file=sys.stderr)


if __name__ == "__main__":
    main()
