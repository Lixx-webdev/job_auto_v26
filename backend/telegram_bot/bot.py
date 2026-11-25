"""Telegram review queue: job cards, approve/reject, cover letter, send."""
from __future__ import annotations

import html
import json
from datetime import datetime

from sqlalchemy import func, select
from telegram import Update
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters,
)

from backend.ai.cover_letter import generate_cover_letter
from backend.applicator.easy_apply import easy_apply
from backend.applicator.email_apply import send_application_email
from backend.config import get_settings
from backend.database.db import get_session
from backend.database.models import ApplicationLog, Job
from backend.profile.parser import load_profile
from backend.telegram_bot.keyboards import job_card_keyboard, send_keyboard
from backend.utils.logger import get_logger

log = get_logger(__name__)
E = html.escape


def _authorized(update: Update) -> bool:
    chat = update.effective_chat
    return bool(chat) and str(chat.id) == str(get_settings().TELEGRAM_CHAT_ID)


def _card(job: Job) -> str:
    try:
        reasons = json.loads(job.ai_reasons or "{}").get("reasons", [])
    except json.JSONDecodeError:
        reasons = []
    age = ""
    if job.posted_at:
        age = f"\n📅 Posted: {(datetime.utcnow() - job.posted_at).days}d ago"
    loc = job.location or "—"
    if job.is_remote:
        loc += " (Remote)"
    why = "\n".join(f"  • {E(r)}" for r in reasons[:3])
    return (
        f"🆕 <b>New Job Match</b> [Score: {job.ai_score:.0f}/100]\n\n"
        f"🏢 {E(job.company)}\n💼 <b>{E(job.title)}</b>\n📍 {E(loc)}\n"
        f"🔗 {E(job.platform.title())}{age}\n\n🤖 Why it matches:\n{why}"
    )


async def send_job_card(app: Application, job: Job) -> None:
    await app.bot.send_message(
        chat_id=get_settings().TELEGRAM_CHAT_ID, text=_card(job),
        parse_mode="HTML", reply_markup=job_card_keyboard(job.id),
    )


async def _log(session, job_id: int, event: str, msg: str = "") -> None:
    session.add(ApplicationLog(job_id=job_id, event_type=event, message=msg))


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update):
        return
    await update.message.reply_text(
        "👋 Job automation bot is running.\n/status — queue stats\n/queue — pending jobs"
    )


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update):
        return
    async with get_session() as session:
        rows = (await session.execute(select(Job.status, func.count()).group_by(Job.status))).all()
    await update.message.reply_text("\n".join(f"{s}: {n}" for s, n in rows) or "No jobs yet.")


async def cmd_queue(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update):
        return
    async with get_session() as session:
        jobs = (await session.execute(
            select(Job).where(Job.status == "pending").order_by(Job.ai_score.desc()).limit(10)
        )).scalars().all()
    if not jobs:
        await update.message.reply_text("Queue is empty.")
    for j in jobs:
        await update.message.reply_text(_card(j), parse_mode="HTML", reply_markup=job_card_keyboard(j.id))


async def on_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not _authorized(update):
        return
    await q.answer()
    action, _, jid = q.data.partition("_")
    job_id = int(jid)

    async with get_session() as session:
        job = await session.get(Job, job_id)
        if not job:
            await q.message.reply_text("Job not found.")
            return

        if action == "reject":
            job.status = "rejected"
            await _log(session, job_id, "rejected")
            await q.edit_message_reply_markup(None)
            await q.message.reply_text(f"❌ Rejected: {job.title} @ {job.company}")

        elif action == "details":
            desc = (job.description or "No description captured.")[:3500]
            await q.message.reply_text(f"<b>{E(job.title)}</b>\n{E(job.apply_url or '')}\n\n{E(desc)}", parse_mode="HTML")

        elif action == "approve":
            if job.status in ("applied",):
                await q.message.reply_text("Already applied.")
                return
            job.status = "approved"
            await q.edit_message_reply_markup(None)
            await q.message.reply_text("✍️ Generating cover letter…")
            letter = await generate_cover_letter(
                {"title": job.title, "company": job.company, "location": job.location, "description": job.description},
                load_profile(),
            )
            if not letter:
                await q.message.reply_text("⚠️ Cover letter generation failed (check Gemini key/model). Job stays approved; tap Approve again from /queue later.")
                job.status = "pending"
                return
            job.cover_letter = letter
            await _log(session, job_id, "approved")
            await q.message.reply_text(f"{letter[:3800]}\n\nApply now?", reply_markup=send_keyboard(job_id))

        elif action == "edit":
            ctx.user_data["editing"] = job_id
            await q.message.reply_text("Reply with the new cover letter text (or /cancel).")

        elif action == "send":
            if job.status == "applied":
                await q.message.reply_text("Already applied.")
                return
            await q.edit_message_reply_markup(None)
            profile = load_profile()
            if job.recruiter_email:
                ok, msg = await send_application_email(
                    job.recruiter_email, job.title, job.company, job.cover_letter or "", profile)
            elif job.platform == "linkedin":
                ok, msg = await easy_apply(job.apply_url or "", profile)
            else:
                ok, msg = False, f"No automated apply path for {job.platform}. Apply manually: {job.apply_url}"
            job.status = "applied" if ok else "failed"
            if ok:
                job.applied_at = datetime.utcnow()
            await _log(session, job_id, "applied" if ok else "apply_failed", msg)
            await q.message.reply_text(
                f"✅ Applied to {job.company} — {job.title}\n{msg}" if ok else f"⚠️ Not applied: {msg}")


async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update):
        return
    job_id = ctx.user_data.pop("editing", None)
    if not job_id:
        return
    async with get_session() as session:
        job = await session.get(Job, job_id)
        if job:
            job.cover_letter = update.message.text
    await update.message.reply_text("Updated. Apply now?", reply_markup=send_keyboard(job_id))


async def cmd_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.pop("editing", None)
    await update.message.reply_text("Cancelled.")


def build_application(post_init=None) -> Application:
    builder = Application.builder().token(get_settings().TELEGRAM_BOT_TOKEN)
    if post_init:
        builder = builder.post_init(post_init)
    app = builder.build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("queue", cmd_queue))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(CallbackQueryHandler(on_button, pattern=r"^(approve|reject|details|send|edit)_\d+$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    return app
