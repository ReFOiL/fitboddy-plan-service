"""Отдельный процесс планировщика. API поднимает его же только по NOTIFICATIONS_SCHEDULER_ENABLED."""

from __future__ import annotations

import logging
import signal
import threading

from application.config import Settings
from application.runtime import PlanApplicationRuntime

logger = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = Settings()
    if not settings.telegram_bot_token.strip():
        logger.warning("TELEGRAM_BOT_TOKEN is empty; workout notifications will not be sent")
    runtime = PlanApplicationRuntime(settings=settings)
    runtime.start_scheduler(force=True)
    runtime.dispatch_notifications()
    stop = threading.Event()

    def _request_stop(_signum: int, _frame: object) -> None:
        stop.set()

    signal.signal(signal.SIGTERM, _request_stop)
    signal.signal(signal.SIGINT, _request_stop)
    try:
        stop.wait()
    finally:
        runtime.shutdown()


if __name__ == "__main__":
    main()
