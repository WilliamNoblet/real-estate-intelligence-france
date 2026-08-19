"""Worker de fond : lance le scheduler (Phase 7, APScheduler) qui automatise la collecte.

Les pipelines restent lançables à la main : `make dvf-import`, `make collect`, `make geo-load`."""
from __future__ import annotations

import logging
import time

from backend.app.core.config import settings

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("reif.worker")


def main() -> None:
    log.info("worker démarré (env=%s).", settings.app_env)
    try:
        from pipelines.scheduler import run as run_scheduler

        run_scheduler()  # bloquant tant qu'il existe des jobs planifiés
    except (KeyboardInterrupt, SystemExit):
        log.info("worker arrêté.")
        return
    # Aucun job planifié : garder le conteneur vivant.
    log.info("worker en veille (aucun job planifié).")
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
