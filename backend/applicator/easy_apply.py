"""LinkedIn Easy Apply via Playwright.

NOTE: LinkedIn's DOM changes often and this has not been tested against a live
account. It is deliberately conservative: if it meets a required field it cannot
fill, it aborts without submitting and reports why, so you can apply manually.
Run once with EASY_APPLY_HEADLESS=false to log in and clear any checkpoint; the
session is kept in .playwright_profile/.
"""
from __future__ import annotations

import os
import random
from pathlib import Path

from playwright.async_api import async_playwright

from backend.config import get_settings

USER_DATA_DIR = str(Path(".playwright_profile").resolve())
MAX_STEPS = 8


async def _pause(page, lo=0.8, hi=2.2):
    await page.wait_for_timeout(int(random.uniform(lo, hi) * 1000))


async def _ensure_login(page) -> bool:
    s = get_settings()
    await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
    if "/feed" in page.url:
        return True
    if not (s.LINKEDIN_EMAIL and s.LINKEDIN_PASSWORD):
        return False
    await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
    await page.fill("#username", s.LINKEDIN_EMAIL)
    await page.fill("#password", s.LINKEDIN_PASSWORD)
    await page.click("button[type=submit]")
    await page.wait_for_timeout(4000)
    return "/feed" in page.url


async def easy_apply(apply_url: str, profile: dict) -> tuple[bool, str]:
    headless = os.getenv("EASY_APPLY_HEADLESS", "true").lower() != "false"
    async with async_playwright() as pw:
        ctx = await pw.chromium.launch_persistent_context(USER_DATA_DIR, headless=headless)
        try:
            page = ctx.pages[0] if ctx.pages else await ctx.new_page()
            if not await _ensure_login(page):
                return False, "LinkedIn login failed (checkpoint/captcha?). Run with EASY_APPLY_HEADLESS=false."
            await page.goto(apply_url, wait_until="domcontentloaded")
            await _pause(page)
            btn = page.locator("button.jobs-apply-button:has-text('Easy Apply')").first
            if await btn.count() == 0:
                return False, "No Easy Apply button — apply manually."
            await btn.click()
            await _pause(page)

            for _ in range(MAX_STEPS):
                modal = page.locator("div.jobs-easy-apply-modal, div[role=dialog]").first
                # contact fields
                for sel, val in (
                    ("input[id*=phoneNumber]", profile.get("phone", "")),
                    ("input[type=email]", profile.get("email", "")),
                ):
                    loc = modal.locator(sel).first
                    if val and await loc.count() and not (await loc.input_value()):
                        await loc.fill(val)
                resume = profile.get("resume_path")
                up = modal.locator("input[type=file]").first
                if resume and await up.count():
                    await up.set_input_files(resume)

                submit = modal.locator("button:has-text('Submit application')").first
                if await submit.count():
                    await submit.click()
                    await _pause(page, 2, 3)
                    return True, "Submitted via LinkedIn Easy Apply"

                nxt = modal.locator("button:has-text('Next'), button:has-text('Review')").first
                if await nxt.count() == 0:
                    return False, "Could not find Next/Submit button."
                await nxt.click()
                await _pause(page)
                if await modal.locator("[aria-invalid=true], .artdeco-inline-feedback--error").count():
                    return False, "Form has required questions I can't answer — apply manually."
            return False, "Too many steps; aborted without submitting."
        except Exception as exc:  # noqa: BLE001
            return False, f"Easy Apply error: {exc}"
        finally:
            await ctx.close()
