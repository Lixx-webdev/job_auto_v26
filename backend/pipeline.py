"""scrape -> dedupe -> AI score -> queue -> notify."""
from __future__ import annotations

import json
from typing import Awaitable, Callable

from sqlalchemy import select

from backend.ai.matcher import score_job
from backend.config import get_settings
from backend.database.db import get_session
from backend.database.models import ApplicationLog, Job
from backend.profile.parser import load_profile
from backend.scrapers.base import RawJob
from backend.scrapers.glassdoor import GlassdoorScraper
from backend.scrapers.indeed import IndeedScraper
from backend.scrapers.linkedin import LinkedInScraper
from backend.utils.logger import get_logger

log = get_logger(__name__)

Notify = Callable[[Job], Awaitable[None]]


def _passes_filters(job: RawJob, s) -> bool:
    if job.seniority != "unknown" and job.seniority not in s.target_seniority_list:
        return False
    if not job.is_remote and job.location and not any(
        loc.lower() in job.location.lower() for loc in s.target_locations_list
    ):
        return False
    return True


async def scrape_and_match(notify: Notify | None = None, dry_run: bool = False) -> dict:
    s = get_settings()
    profile = load_profile()
    filters = {
        "keywords": s.target_keywords_list,
        "locations": s.target_locations_list,
        "seniority": s.target_seniority_list,
        "max_age_days": s.MAX_JOB_AGE_DAYS,
        "max_jobs": s.MAX_JOBS_PER_RUN,
    }
    stats = {"scraped": 0, "new": 0, "queued": 0, "discarded": 0}

    raw: list[RawJob] = []
    for cls in (LinkedInScraper, IndeedScraper, GlassdoorScraper):
        try:
            raw.extend(await cls(filters).scrape())
        except Exception as exc:  # noqa: BLE001
            log.error("scraper_failed", scraper=cls.__name__, error=str(exc))
    stats["scraped"] = len(raw)

    async with get_session() as session:
        seen = set((await session.execute(select(Job.external_id))).scalars().all())
    fresh = [j for j in raw if j.external_id not in seen and _passes_filters(j, s)]
    fresh = fresh[: s.MAX_JOBS_PER_RUN]
    stats["new"] = len(fresh)

    for rj in fresh:
        result = await score_job(rj.description or rj.title, rj.title, rj.company, profile)
        matched = result["score"] >= s.AI_MATCH_THRESHOLD
        log.info("job_scored", title=rj.title, company=rj.company, score=result["score"], dry_run=dry_run)
        if dry_run:
            stats["queued" if matched else "discarded"] += 1
            stats.setdefault("results", []).append(
                (result["score"], rj.title, rj.company, rj.seniority, (result["reasons"] or [""])[0])
            )
            continue
        async with get_session() as session:
            job = Job(
                external_id=rj.external_id, platform=rj.platform, title=rj.title, company=rj.company,
                location=rj.location, is_remote=rj.is_remote, seniority=rj.seniority,
                description=rj.description, apply_url=rj.apply_url, posted_at=rj.posted_at,
                recruiter_email=rj.recruiter_email, ai_score=result["score"],
                ai_reasons=json.dumps({"reasons": result["reasons"], "red_flags": result["red_flags"]}),
                status="pending" if matched else "discarded",
            )
            session.add(job)
            await session.flush()
            session.add(ApplicationLog(job_id=job.id, event_type="ai_scored", message=f"score={result['score']}"))
        stats["queued" if matched else "discarded"] += 1
        if matched and notify:
            await notify(job)
    log.info("run_complete", **stats)
    return stats
