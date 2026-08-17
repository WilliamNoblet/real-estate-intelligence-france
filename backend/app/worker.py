"""Worker de fond. Phase 1 : simple battement de cœur qui garde le conteneur vivant.

Le scheduler réel (discovery + refresh à fréquences distinctes, §33) sera branché en Phase 7
(APScheduler) ; les pipelines (DVF, collecte) sont lancés à la demande via `make dvf-import` /
`make collect` en attendant."""
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
    log.info(
        "worker démarré (env=%s). En attente de tâches planifiées (Phase 7).",
        settings.app_env,
    )
    try:
        while True:
            time.sleep(3600)
            log.debug("worker heartbeat")
    except KeyboardInterrupt:
        log.info("worker arrêté.")


if __name__ == "__main__":
    main()
