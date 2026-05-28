"""Telegram notifications for staking alerts."""
from __future__ import annotations

import html
import requests

from config import CONFIG


def _enabled() -> bool:
    return bool(CONFIG.telegram_enabled and CONFIG.telegram_bot_token and CONFIG.telegram_chat_id)


def send(text: str) -> bool:
    """Send message via Telegram Bot API. Never raises."""
    if not _enabled():
        return False
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{CONFIG.telegram_bot_token}/sendMessage",
            json={
                "chat_id": CONFIG.telegram_chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=10,
        )
        return resp.status_code == 200
    except Exception:
        return False


def send_alert(emoji: str, title: str, message: str, action: str) -> bool:
    """Format and send a staking alert."""
    text = (
        f"{emoji} <b>{html.escape(title)}</b>\n\n"
        f"{html.escape(message)}\n\n"
        f"👉 <b>{html.escape(action)}</b>"
    )
    return send(text)
