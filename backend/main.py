"""Entry point.

  python -m backend.main              # run bot + scheduler
  python -m backend.main --dry-run    # one scrape+score pass, no DB writes, no Telegram
  python -m backend.main --test-telegram   # send a test message and exit
"""
from __future__ import annotations

import argparse
import asyncio

from backend.config import get_settings
from backend.database.db import init_db
from backend.pipeline import scrape_and_match
from backend.scheduler import build_scheduler
from backend.telegram_bot.bot import build_application, send_job_card
from backend.utils.logger import get_logger

log = get_logger(__name__)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--test-telegram", action="store_true")
    args = ap.parse_args()

    if args.dry_run:
        async def run():
            await init_db()
            stats = await scrape_and_match(None, dry_run=True)
            results = sorted(stats.pop("results", []), reverse=True)
            print("\n=== Dry run results (highest score first) ===")
            for score, title, company, seniority, reason in results:
                print(f"{score:>3}  {title[:55]:<55} | {company[:22]:<22} | {seniority:<7} | {reason[:70]}")
            print(stats)
        asyncio.run(run())
        return

    if args.test_telegram:
        async def run():
            app = build_application()
            async with app.bot:
                await app.bot.send_message(get_settings().TELEGRAM_CHAT_ID, "✅ Telegram connection works.")
        asyncio.run(run())
        print("Sent.")
        return

    holder = {}

    async def post_init(app):
        await init_db()
        holder["app"] = app

        async def notify(job):
            await send_job_card(app, job)

        sched = build_scheduler(notify)
        sched.start()
        app.bot_data["scheduler"] = sched
        asyncio.create_task(scrape_and_match(notify))  # first run immediately
        log.info("started", interval_hours=get_settings().SCRAPE_INTERVAL_HOURS)

    build_application(post_init).run_polling()


if __name__ == "__main__":
    main()
