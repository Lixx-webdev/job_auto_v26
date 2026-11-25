from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from backend.config import get_settings
from backend.pipeline import scrape_and_match
from backend.utils.logger import get_logger

log = get_logger(__name__)


def build_scheduler(notify) -> AsyncIOScheduler:
    sched = AsyncIOScheduler()

    async def job():
        try:
            await scrape_and_match(notify)
        except Exception as exc:  # noqa: BLE001
            log.error("scheduled_run_failed", error=str(exc))

    sched.add_job(job, "interval", hours=get_settings().SCRAPE_INTERVAL_HOURS,
                  id="scrape_and_match", max_instances=1, coalesce=True)
    return sched
