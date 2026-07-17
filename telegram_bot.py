#!/usr/bin/env python3
"""Telegram bot front-end for yt-downloader.

Long-polls the Telegram Bot API; downloads requested YouTube video/audio
via yt-dlp and delivers small files back in the chat, large files to a
cloud remote via rclone. Designed to run 24/7 under systemd on a
Raspberry Pi.
"""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")


def _parse_user_id(raw: str) -> int:
	"""Best-effort numeric user id; malformed values behave like unset."""
	return int(raw) if raw.isdigit() else 0


BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
ALLOWED_USER_ID = _parse_user_id(os.environ.get("ALLOWED_USER_ID", ""))
RCLONE_REMOTE = os.environ.get("RCLONE_REMOTE", "gdrive:YouTube")

API = f"https://api.telegram.org/bot{BOT_TOKEN}"
TMP_DIR = Path("/tmp/yt-downloader-bot")
MAX_CHAT_BYTES = 49 * 1024 * 1024  # Telegram's bot upload cap is 50 MB
EDIT_INTERVAL = 5.0  # min seconds between progress-message edits

log = logging.getLogger("yt-downloader-bot")


def parse_callback(data: str) -> tuple:
    """Decode a callback_data string.

    "a" -> ("audio", None); "v" -> ("menu", None); "v:720" -> ("video", 720).
    Raises ValueError for anything else.
    """
    if data == "a":
        return ("audio", None)
    if data == "v":
        return ("menu", None)
    if data.startswith("v:") and data[2:].isdigit():
        return ("video", int(data[2:]))
    raise ValueError(f"bad callback data: {data!r}")


def deliver_via_chat(size_bytes: int) -> bool:
    """True if a file this size can be sent directly in the chat."""
    return size_bytes <= MAX_CHAT_BYTES


def is_authorized(user_id, allowed_id) -> bool:
    return user_id is not None and user_id == allowed_id


def format_menu_keyboard() -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "🎬 Video", "callback_data": "v"},
                {"text": "🎵 Audio (MP3)", "callback_data": "a"},
            ]
        ]
    }


def resolution_keyboard(heights: list) -> dict:
    rows, row = [], []
    for h in heights:
        row.append({"text": f"{h}p", "callback_data": f"v:{h}"})
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return {"inline_keyboard": rows}
