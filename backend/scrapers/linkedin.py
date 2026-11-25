"""LinkedIn scraper using the public guest job-search endpoints (no login, no Playwright).

Conservative by design: randomized delays, capped result count. Selectors may need
adjusting if LinkedIn changes its markup.
"""
from __future__ import annotations

import asyncio
import random
import re
from datetime import datetime, timedelta
from typing import List

import httpx
from bs4 import BeautifulSoup

from backend.scrapers.base import BaseScraper, RawJob
from backend.utils.logger import get_logger

log = get_logger(__name__)

SEARCH = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
DETAIL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{id}"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


class LinkedInScraper(BaseScraper):
    async def scrape(self) -> List[RawJob]:
        f = self.filters
        max_jobs = f.get("max_jobs", 30)
        seconds = int(f.get("max_age_days", 7)) * 86400
        jobs: dict[str, RawJob] = {}
        seen_pairs: set[tuple[str, str]] = set()
        keywords = f.get("keywords", [])
        quota = max(3, -(-max_jobs // max(len(keywords), 1)))  # ceil: share the cap across keywords
        async with httpx.AsyncClient(headers=HEADERS, timeout=20, follow_redirects=True) as client:
            for kw in keywords:
                got = 0
                # On-site/hybrid in India, then India-only remote (f_WT=2) — avoids worldwide "Remote".
                for extra in ({}, {"f_WT": "2"}):
                    if got >= quota:
                        break
                    try:
                        r = await self._get(
                            client, SEARCH,
                            {"keywords": kw, "location": "India", "f_TPR": f"r{seconds}", "start": 0, **extra},
                        )
                        if r.status_code != 200:
                            log.warning("linkedin_search_status", status=r.status_code, kw=kw)
                            continue
                        for card in BeautifulSoup(r.text, "html.parser").select("li"):
                            job = self._parse_card(card)
                            if not job or job.external_id in jobs:
                                continue
                            pair = (job.title.lower(), job.company.lower())
                            if pair in seen_pairs:
                                continue
                            seen_pairs.add(pair)
                            jobs[job.external_id] = job
                            got += 1
                            if got >= quota:
                                break
                    except httpx.HTTPError as exc:
                        log.warning("linkedin_search_error", error=str(exc))
                    await asyncio.sleep(random.uniform(2, 5))

            result = list(jobs.values())[:max_jobs]
            for job in result:
                try:
                    r = await self._get(client, DETAIL.format(id=job.external_id.split(":")[1]))
                    if r.status_code == 200:
                        soup = BeautifulSoup(r.text, "html.parser")
                        desc = soup.select_one(".show-more-less-html__markup, .description__text")
                        if desc:
                            job.description = desc.get_text("\n", strip=True)
                        crit = " ".join(t.get_text(" ", strip=True) for t in soup.select(".description__job-criteria-text"))
                        if job.seniority == "unknown":
                            job.seniority = self.infer_seniority(crit + " " + job.title)
                        job.is_remote = self.infer_remote(job.location, job.description)
                except httpx.HTTPError:
                    pass
                await asyncio.sleep(random.uniform(1.5, 3.5))
        log.info("linkedin_scraped", count=len(result))
        return result

    async def _get(self, client: httpx.AsyncClient, url: str, params: dict | None = None, tries: int = 3):
        """GET with backoff on 429 (LinkedIn rate limiting)."""
        r = await client.get(url, params=params)
        for i in range(1, tries):
            if r.status_code != 429:
                break
            await asyncio.sleep(10 * i + random.uniform(0, 3))
            r = await client.get(url, params=params)
        return r

    def _parse_card(self, card) -> RawJob | None:
        link = card.select_one("a.base-card__full-link, a[href*='/jobs/view/']")
        title = card.select_one(".base-search-card__title")
        if not (link and title):
            return None
        m = re.search(r"-(\d{6,})\?|/view/(\d+)", link["href"])
        if not m:
            return None
        jid = m.group(1) or m.group(2)
        company = card.select_one(".base-search-card__subtitle")
        loc = card.select_one(".job-search-card__location")
        t = card.select_one("time")
        posted = None
        if t and t.get("datetime"):
            try:
                posted = datetime.fromisoformat(t["datetime"])
            except ValueError:
                posted = datetime.utcnow() - timedelta(days=1)
        title_s = title.get_text(strip=True)
        loc_s = loc.get_text(strip=True) if loc else ""
        return RawJob(
            external_id=f"linkedin:{jid}",
            platform="linkedin",
            title=title_s,
            company=company.get_text(strip=True) if company else "Unknown",
            location=loc_s,
            is_remote=self.infer_remote(loc_s, ""),
            seniority=self.infer_seniority(title_s),
            description="",
            apply_url=f"https://www.linkedin.com/jobs/view/{jid}",
            posted_at=posted,
        )
