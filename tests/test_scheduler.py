"""Tests du scheduler (Phase 7) — purs, sans démarrage réel."""
from __future__ import annotations

from pipelines.scheduler import build_scheduler, scheduled_jobs


def test_scheduled_jobs_keeps_only_enabled():
    cfg = {
        "scheduler": {
            "enabled": True,
            "jobs": {
                "a": {"enabled": True, "interval_seconds": 100},
                "b": {"enabled": False, "interval_seconds": 200},
            },
        }
    }
    jobs = scheduled_jobs(cfg)
    assert [j["id"] for j in jobs] == ["a"]
    assert jobs[0]["interval_seconds"] == 100


def test_scheduled_jobs_disabled_or_empty():
    assert scheduled_jobs({"scheduler": {"enabled": False}}) == []
    assert scheduled_jobs({}) == []


def test_scheduled_jobs_skips_missing_interval():
    # Un job sans interval_seconds ne doit pas faire crasher le worker (KeyError) : il est ignoré.
    cfg = {"scheduler": {"enabled": True, "jobs": {"k": {"enabled": True}}}}
    assert scheduled_jobs(cfg) == []


def test_job_is_scheduled_not_paused():
    # Régression : next_run_time=None mettait le job en PAUSE (jamais exécuté).
    from apscheduler.schedulers.background import BackgroundScheduler

    cfg = {
        "scheduler": {
            "enabled": True,
            "run_at_start": False,
            "jobs": {"j": {"enabled": True, "interval_seconds": 3600}},
        }
    }
    scheduler = build_scheduler({"j": lambda: None}, cfg, scheduler_factory=BackgroundScheduler)
    scheduler.start()
    try:
        job = scheduler.get_jobs()[0]
        assert job.next_run_time is not None  # planifié, PAS en pause
    finally:
        scheduler.shutdown(wait=False)


def test_build_scheduler_only_registers_known_callables():
    cfg = {
        "scheduler": {
            "enabled": True,
            "run_at_start": False,
            "jobs": {
                "collect_immonot": {"enabled": True, "interval_seconds": 3600},
                "unknown_job": {"enabled": True, "interval_seconds": 60},
            },
        }
    }
    scheduler = build_scheduler({"collect_immonot": lambda: None}, cfg)
    ids = {j.id for j in scheduler.get_jobs()}
    assert "collect_immonot" in ids
    assert "unknown_job" not in ids  # aucun callable fourni -> ignoré
