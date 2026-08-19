"""Scheduler local (Phase 7, APScheduler). Automatise la collecte à fréquence POLIE.

Une évolution de prix immobilier se mesure en jours, pas en secondes (§140) : les intervalles
sont volontairement larges. `scheduled_jobs` est pur (testable) ; `run()` bloque dans le worker."""
from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Callable

from apscheduler.schedulers.base import BaseScheduler
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

from backend.app.core.config import load_yaml_config, settings

log = logging.getLogger("reif.scheduler")


def scheduled_jobs(config: dict) -> list[dict]:
    """Spécifications des jobs activés (id + intervalle) depuis la config.
    Un job sans `interval_seconds` valide est ignoré (jamais de crash du worker)."""
    sched = config.get("scheduler", {})
    if not sched.get("enabled"):
        return []
    jobs = []
    for job_id, spec in (sched.get("jobs") or {}).items():
        if not spec.get("enabled"):
            continue
        interval = spec.get("interval_seconds")
        if interval is None:
            log.warning("job planifié '%s' sans interval_seconds — ignoré", job_id)
            continue
        jobs.append({"id": job_id, "interval_seconds": int(interval)})
    return jobs


def build_scheduler(
    callables: dict[str, Callable],
    config: dict | None = None,
    scheduler_factory: type[BaseScheduler] = BlockingScheduler,
) -> BaseScheduler:
    """Construit (sans démarrer) un scheduler enregistrant les jobs config dont on a le callable."""
    config = config or load_yaml_config("default")
    run_at_start = bool(config.get("scheduler", {}).get("run_at_start"))
    scheduler = scheduler_factory(timezone="UTC")
    for job in scheduled_jobs(config):
        func = callables.get(job["id"])
        if func is None:
            log.warning("job planifié '%s' sans callable — ignoré", job["id"])
            continue
        # ⚠ next_run_time=None METTRAIT le job en PAUSE (jamais exécuté). On ne le passe donc
        # QUE pour run_at_start ; sinon APScheduler planifie la 1re exécution à now + intervalle.
        job_kwargs: dict = {"max_instances": 1, "coalesce": True}
        if run_at_start:
            job_kwargs["next_run_time"] = dt.datetime.now(dt.UTC)
        scheduler.add_job(
            func,
            IntervalTrigger(seconds=job["interval_seconds"]),
            id=job["id"],
            **job_kwargs,
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
