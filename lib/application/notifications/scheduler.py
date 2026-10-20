from __future__ import annotations

import logging
from collections.abc import Callable

from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)


def start_notification_scheduler(tick: Callable[[], None], poll_seconds: int) -> BackgroundScheduler:
    # Один тик за раз: следующий не стартует, пока предыдущий не закончил обход.
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        tick,
        "interval",
        seconds=poll_seconds,
        id="workout-notifications",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=poll_seconds,
        replace_existing=True,
    )
    scheduler.start()
    logger.info("workout notification scheduler started", extra={"poll_seconds": poll_seconds})
    return scheduler
