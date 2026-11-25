"""Indeed scraper (Playwright). Indeed blocks plain HTTP clients, so we render the page.

Best-effort: Indeed may show a captcha; in that case this returns [] and logs a warning.
Selectors may need adjusting.
"""
from __future__ import annotations

import asyncio
import random
from typing import List
from urllib.parse import quote_plus

from playwright.async_api import async_playwright

from backend.scrapers.base import BaseScraper, RawJob
from backend.utils.logger import get_logger

log = get_logger(__name__)


class IndeedScraper(BaseScraper):
    async def scrape(self) -> List[RawJob]:
        f = self.filters
        max_jobs = f.get("max_jobs", 30)
        days = int(f.get("max_age_days", 7))
        jobs: dict[str, RawJob] = {}
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            page = await browser.new_page()
            try:
                for kw in f.get("keywords", []):
                    if len(jobs) >= max_jobs:
                        break
                    url = f"https://in.indeed.com/jobs?q={quote_plus(kw)}&l=India&fromage={days}"
                    try:
                        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                        await page.wait_for_timeout(2500)
                        cards = await page.locator("div.job_seen_beacon").all()
                        if not cards:
                            log.warning("indeed_no_cards", kw=kw, note="captcha or markup change?")
                        for c in cards:
                            link = c.locator("h2 a").first
                            jk = await link.get_attribute("data-jk")
                            if not jk or f"indeed:{jk}" in jobs:
                                continue
                            title = (await link.inner_text()).strip()
                            comp = c.locator("[data-testid=company-name]").first
                            loc = c.locator("[data-testid=text-layout], [data-testid=text-location]").first
                            company = (await comp.inner_text()).strip() if await comp.count() else "Unknown"
                            location = (await loc.inner_text()).strip() if await loc.count() else ""
                            snippet = (await c.locator(".css-9446fg, ul").first.inner_text()) if await c.locator("ul").count() else ""
                            jobs[f"indeed:{jk}"] = RawJob(
                                external_id=f"indeed:{jk}", platform="indeed", title=title,
                                company=company, location=location,
                                is_remote=self.infer_remote(location, snippet),
                                seniority=self.infer_seniority(title), description=snippet,
                                apply_url=f"https://in.indeed.com/viewjob?jk={jk}", posted_at=None,
                            )
                    except Exception as exc:  # noqa: BLE001
                        log.warning("indeed_error", error=str(exc), kw=kw)
                    await asyncio.sleep(random.uniform(3, 6))

                # fetch full descriptions
                for job in list(jobs.values())[:max_jobs]:
                    try:
                        await page.goto(job.apply_url, wait_until="domcontentloaded", timeout=30000)
                        d = page.locator("#jobDescriptionText").first
                        if await d.count():
                            job.description = (await d.inner_text()).strip()
                            job.is_remote = self.infer_remote(job.location, job.description)
                    except Exception:  # noqa: BLE001
                        pass
                    await asyncio.sleep(random.uniform(2, 4))
            finally:
                await browser.close()
        result = list(jobs.values())[:max_jobs]
        log.info("indeed_scraped", count=len(result))
        return result
