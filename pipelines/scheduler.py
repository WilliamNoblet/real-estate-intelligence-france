"""Scheduler local (Phase 7, APScheduler). Automatise la collecte à fréquence POLIE.

Une évolution de prix immobilier se mesure en jours, pas en secondes (§140) : les intervalles
sont volontairement larges. `scheduled_jobs` est pur (testable) ; `run()` bloque dans le worker."""
from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Callable

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

from backend.app.core.config import load_yaml_config, settings

log = logging.getLogger("reif.scheduler")


def scheduled_jobs(config: dict) -> list[dict]:
    """Spécifications des jobs activés (id + intervalle) depuis la config."""
    sched = config.get("scheduler", {})
    if not sched.get("enabled"):
        return []
    jobs = []
    for job_id, spec in (sched.get("jobs") or {}).items():
        if spec.get("enabled"):
            jobs.append({"id": job_id, "interval_seconds": int(spec["interval_seconds"])})
    return jobs


def build_scheduler(
    callables: dict[str, Callable], config: dict | None = None
) -> BlockingScheduler:
    """Construit (sans démarrer) un scheduler enregistrant les jobs config dont on a le callable."""
    config = config or load_yaml_config("default")
    run_at_start = bool(config.get("scheduler", {}).get("run_at_start"))
    scheduler = BlockingScheduler(timezone="UTC")
    for job in scheduled_jobs(config):
        func = callables.get(job["id"])
        if func is None:
            log.warning("job planifié '%s' sans callable — ignoré", job["id"])
            continue
        scheduler.add_job(
            func,
            IntervalTrigger(seconds=job["interval_seconds"]),
            id=job["id"],
            next_run_time=dt.datetime.now(dt.UTC) if run_at_start else None,
            max_instances=1,
            coalesce=True,
        )
    return scheduler


def _job_callables() -> dict[str, Callable]:
    """Résolution paresseuse des callables (évite les imports réseau au chargement du module)."""
    from collectors.run import main as collect_immonot

    callables: dict[str, Callable] = {"collect_immonot": collect_immonot}
    try:
        from pipelines.geocoding.run import geocode_pending as geocode_listings

        callables["geocode_listings"] = geocode_listings
    except Exception:  # noqa: BLE001 — job optionnel tant que le géocodage n'est pas branché
        pass
    return callables


def run() -> None:
    logging.basicConfig(
        level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    scheduler = build_scheduler(_job_callables())
    jobs = scheduler.get_jobs()
    if not jobs:
        log.info("Scheduler : aucun job planifié (voir config/default.yaml).")
        return
    log.info("Scheduler démarré avec %d job(s) : %s", len(jobs), [j.id for j in jobs])
    scheduler.start()  # bloquant


if __name__ == "__main__":
    run()
