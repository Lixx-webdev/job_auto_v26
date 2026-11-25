"""Direct recruiter email application via Gmail SMTP (App Password)."""
from __future__ import annotations

import asyncio
import smtplib
from email.message import EmailMessage
from pathlib import Path

from backend.config import get_settings


def _send_sync(to: str, subject: str, body: str, resume_path: str | None) -> None:
    s = get_settings()
    if not (s.GMAIL_ADDRESS and s.GMAIL_APP_PASSWORD):
        raise RuntimeError("GMAIL_ADDRESS / GMAIL_APP_PASSWORD not configured")
    msg = EmailMessage()
    msg["From"] = s.GMAIL_ADDRESS
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    if resume_path and Path(resume_path).is_file():
        p = Path(resume_path)
        msg.add_attachment(p.read_bytes(), maintype="application", subtype="pdf", filename=p.name)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
        smtp.login(s.GMAIL_ADDRESS, s.GMAIL_APP_PASSWORD)
        smtp.send_message(msg)


async def send_application_email(
    to: str, job_title: str, company: str, cover_letter: str, profile: dict
) -> tuple[bool, str]:
    subject = f"Application: {job_title} — {profile.get('name', '')}".strip(" —")
    try:
        await asyncio.to_thread(_send_sync, to, subject, cover_letter, profile.get("resume_path"))
        return True, f"Emailed {to}"
    except Exception as exc:  # noqa: BLE001
        return False, f"Email failed: {exc}"
