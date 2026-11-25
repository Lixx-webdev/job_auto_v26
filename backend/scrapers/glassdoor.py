"""Glassdoor scraper (Playwright). Aggressive bot protection — expect frequent empty results.

Best-effort; failures are logged and return [] so other platforms still run.
"""
from __future__ import annotations

import asyncio
import random
import re
from typing import List
from urllib.parse import quote_plus

from playwright.async_api import async_playwright

from backend.scrapers.base import BaseScraper, RawJob
from backend.utils.logger import get_logger

log = get_logger(__name__)


class GlassdoorScraper(BaseScraper):
    async def scrape(self) -> List[RawJob]:
        f = self.filters
        max_jobs = f.get("max_jobs", 30)
        jobs: dict[str, RawJob] = {}
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            page = await browser.new_page()
            try:
                for kw in f.get("keywords", []):
                    if len(jobs) >= max_jobs:
                        break
                    url = f"https://www.glassdoor.co.in/Job/jobs.htm?sc.keyword={quote_plus(kw)}&fromAge={f.get('max_age_days', 7)}"
                    try:
                        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                        await page.wait_for_timeout(3000)
                        cards = await page.locator("li[data-test=jobListing]").all()
                        if not cards:
                            log.warning("glassdoor_no_cards", kw=kw, note="blocked or markup change?")
                        for c in cards:
                            link = c.locator("a[data-test=job-link]").first
                            if not await link.count():
                                continue
                            href = await link.get_attribute("href") or ""
                            m = re.search(r"jobListingId=(\d+)", href) or re.search(r"(\d{8,})", href)
                            jid = m.group(1) if m else href[-24:]
                            if f"glassdoor:{jid}" in jobs:
                                continue
                            title = (await link.inner_text()).strip()
                            comp = c.locator("[class*=EmployerProfile_compactEmployerName], [data-test=employer-short-name]").first
                            loc = c.locator("[data-test=emp-location]").first
                            company = (await comp.inner_text()).strip() if await comp.count() else "Unknown"
                            location = (await loc.inner_text()).strip() if await loc.count() else ""
                            if href.startswith("/"):
                                href = "https://www.glassdoor.co.in" + href
                            jobs[f"glassdoor:{jid}"] = RawJob(
                                external_id=f"glassdoor:{jid}", platform="glassdoor", title=title,
                                company=company, location=location,
                                is_remote=self.infer_remote(location, ""),
                                seniority=self.infer_seniority(title), description=title,
                                apply_url=href, posted_at=None,
                            )
                    except Exception as exc:  # noqa: BLE001
                        log.warning("glassdoor_error", error=str(exc), kw=kw)
                    await asyncio.sleep(random.uniform(3, 6))
            finally:
                await browser.close()
        result = list(jobs.values())[:max_jobs]
        log.info("glassdoor_scraped", count=len(result))
        return result
