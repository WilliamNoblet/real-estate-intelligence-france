"""Orchestration de l'import DVF pour un département.

Usage :
    python -m pipelines.dvf.run --dep 33 --years 2024 2025
Défaut : département pilote de config/default.yaml, deux années les plus récentes.
Étapes : download (+SHA256) → parse → reconstruct (regroupement id_mutation) → quality → load."""
from __future__ import annotations

import argparse
import datetime as dt
import logging

import httpx

from backend.app.core.config import load_yaml_config, settings
from backend.app.core.db import SessionLocal
from backend.app.models import JobRun
from backend.app.models.enums import JobStatus
from pipelines.dvf.client import download_department
from pipelines.dvf.load import get_or_create_source, load_transactions
from pipelines.dvf.reconstruct import count_rejected_rows, read_geodvf_csv, reconstruct

logging.basicConfig(
    level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s"
)
log = logging.getLogger("reif.dvf")


def default_department() -> str:
    return str(load_yaml_config("default").get("pilot", {}).get("department", "33"))


def default_years() -> list[int]:
    y = dt.date.today().year
    return [y - 1, y - 2]


def import_year(dep: str, year: int) -> dict:
    log.info("DVF %s %s : téléchargement…", dep, year)
    path, file_hash = download_department(dep, year)
    raw = read_geodvf_csv(str(path))
    rows_read = raw.height
    rejected = count_rejected_rows(raw)
    txns = reconstruct(raw, source_year=year)
    log.info(
        "DVF %s %s : %d lignes → %d transactions (%d lignes hors-vente).",
        dep, year, rows_read, txns.height, rejected,
    )
    with SessionLocal() as session:
        result = load_transactions(
            session,
            txns,
            source_version=f"{dep}-{year}",
            file_hash=file_hash,
            rows_read=rows_read,
            rows_rejected=rejected,
        )
    log.info("DVF %s %s : %s", dep, year, result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import DVF géolocalisées par département.")
    parser.add_argument("--dep", default=default_department(), help="Code département (ex. 33).")
    parser.add_argument(
        "--years", type=int, nargs="+", default=default_years(), help="Années à importer."
    )
    args = parser.parse_args(argv)

    with SessionLocal() as session:
        source = get_or_create_source(session)
        session.commit()
        job = JobRun(
            job_type="dvf_import",
            source_id=source.id,
            started_at=dt.datetime.now(dt.UTC),
            status=JobStatus.RUNNING,
        )
        session.add(job)
        session.commit()
        job_id = job.id

    totals = {"read": 0, "inserted": 0, "rejected": 0}
    status = JobStatus.SUCCESS
    error: str | None = None
    try:
        for year in args.years:
            try:
                res = import_year(args.dep, year)
            except httpx.HTTPStatusError as exc:
                log.warning("DVF %s %s indisponible (HTTP %s) — ignoré.", args.dep, year,
                            exc.response.status_code)
                continue
            if res.get("skipped"):
                continue
            totals["read"] += res.get("rows_read", 0)
            totals["inserted"] += res.get("rows_inserted", 0)
            totals["rejected"] += res.get("rows_rejected", 0)
    except Exception as exc:  # noqa: BLE001
        status = JobStatus.FAILED
        error = str(exc)
        log.exception("Import DVF échoué.")

    with SessionLocal() as session:
        job = session.get(JobRun, job_id)
        job.finished_at = dt.datetime.now(dt.UTC)
        job.status = status
        job.items_read = totals["read"]
        job.items_inserted = totals["inserted"]
        job.items_rejected = totals["rejected"]
        job.error_message = error
        session.commit()

    log.info("Import DVF terminé : %s (%s)", totals, status.value)
    return 0 if status == JobStatus.SUCCESS else 1


if __name__ == "__main__":
    raise SystemExit(main())
