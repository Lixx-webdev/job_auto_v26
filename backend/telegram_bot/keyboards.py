from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def job_card_keyboard(job_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"approve_{job_id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"reject_{job_id}"),
                InlineKeyboardButton("📄 Details", callback_data=f"details_{job_id}"),
            ]
        ]
    )


def send_keyboard(job_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Send 🚀", callback_data=f"send_{job_id}"),
                InlineKeyboardButton("Edit ✏️", callback_data=f"edit_{job_id}"),
                InlineKeyboardButton("Cancel", callback_data=f"reject_{job_id}"),
            ]
        ]
    )
