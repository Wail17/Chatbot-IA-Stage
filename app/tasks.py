"""Background task scheduler using APScheduler.

Manages recurring tasks like the nightly learning cycle and
weekly report generation.
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.utils.logger import logger

scheduler = AsyncIOScheduler()


async def nightly_learning_task() -> None:
    """Execute the nightly learning cycle.

    Runs pattern detection, signal processing, and weekly stats generation.
    Scheduled to run at the configured hour (default: 2:00 AM).
    """
    logger.info("Nightly learning task triggered by scheduler")

    try:
        from app.services.learning_engine import run_nightly_learning

        stats = await run_nightly_learning()
        logger.info("Nightly learning complete: %s", stats)
    except Exception as exc:
        logger.error("Nightly learning task failed: %s", str(exc), exc_info=True)


def start_scheduler() -> None:
    """Start the background task scheduler.

    Registers the nightly learning cycle job and starts the scheduler.
    Only adds jobs if the scheduler is not already running.
    """
    if scheduler.running:
        logger.warning("Scheduler is already running")
        return

    scheduler.add_job(
        nightly_learning_task,
        trigger="cron",
        hour=settings.nightly_learning_hour,
        minute=0,
        id="nightly_learning",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    scheduler.start()
    logger.info(
        "Scheduler started - nightly learning at %02d:00",
        settings.nightly_learning_hour,
    )


def stop_scheduler() -> None:
    """Stop the background task scheduler gracefully."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
