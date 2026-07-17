#!/usr/bin/env python3
"""Telegram bot front-end for yt-downloader.

Long-polls the Telegram Bot API; downloads requested YouTube video/audio
via yt-dlp and delivers small files back in the chat, large files to a
cloud remote via rclone. Designed to run 24/7 under systemd on a
Raspberry Pi.
"""

import logging
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import requests
import yt_dlp
from dotenv import load_dotenv

from downloader import available_heights, build_audio_opts, build_video_opts, is_youtube_url

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


# ---------------------------------------------------------------------------
# Telegram API
# ---------------------------------------------------------------------------

def tg(method: str, **params):
    """Call a Bot API method with JSON params; return result or None."""
    try:
        resp = requests.post(f"{API}/{method}", json=params, timeout=70)
        data = resp.json()
    except (requests.RequestException, ValueError) as e:
        log.warning("telegram %s error: %s", method, e)
        return None
    if not data.get("ok"):
        log.warning("telegram %s failed: %s", method, data.get("description"))
        return None
    return data["result"]


def tg_send_file(chat_id: int, path: Path, mode: str, title: str) -> bool:
    """Upload a finished file into the chat. mode is 'audio' or 'video'."""
    method, field = ("sendAudio", "audio") if mode == "audio" else ("sendVideo", "video")
    try:
        with open(path, "rb") as f:
            resp = requests.post(
                f"{API}/{method}",
                data={"chat_id": chat_id, "caption": title},
                files={field: (path.name, f)},
                timeout=600,
            )
        return bool(resp.json().get("ok"))
    except (requests.RequestException, ValueError, OSError) as e:
        log.warning("file upload failed: %s", e)
        return False


# ---------------------------------------------------------------------------
# Download worker
# ---------------------------------------------------------------------------

jobs: "queue.Queue[dict]" = queue.Queue()
pending: dict = {}  # chat_id -> {url, title, heights, message_id}


def make_progress_hook(chat_id: int, message_id: int):
    last_edit = [0.0]

    def hook(d: dict) -> None:
        if d["status"] == "downloading":
            now = time.time()
            if now - last_edit[0] >= EDIT_INTERVAL:
                last_edit[0] = now
                pct = d.get("_percent_str", "?").strip()
                tg("editMessageText", chat_id=chat_id, message_id=message_id,
                   text=f"⏳ Downloading… {pct}")
        elif d["status"] == "finished":
            tg("editMessageText", chat_id=chat_id, message_id=message_id,
               text="🔧 Processing (ffmpeg)…")

    return hook


def upload_rclone(chat_id: int, message_id: int, path: Path) -> None:
    tg("editMessageText", chat_id=chat_id, message_id=message_id,
       text="☁️ Uploading to Drive…")
    result = subprocess.run(
        ["rclone", "copy", str(path), RCLONE_REMOTE],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        tg("editMessageText", chat_id=chat_id, message_id=message_id,
           text=f"☁️ Uploaded to Google Drive: {path.name}")
        shutil.rmtree(path.parent, ignore_errors=True)
    else:
        log.error("rclone failed: %s", result.stderr[-500:])
        tg("editMessageText", chat_id=chat_id, message_id=message_id,
           text=f"❌ Drive upload failed — file kept at {path}")


def deliver(chat_id: int, message_id: int, path: Path, mode: str, title: str) -> None:
    if deliver_via_chat(path.stat().st_size):
        tg("editMessageText", chat_id=chat_id, message_id=message_id,
           text="📤 Sending to chat…")
        if tg_send_file(chat_id, path, mode, title):
            tg("editMessageText", chat_id=chat_id, message_id=message_id,
               text=f"✅ {title}")
            shutil.rmtree(path.parent, ignore_errors=True)
            return
        log.warning("chat upload failed, falling back to rclone")
    upload_rclone(chat_id, message_id, path)


def process_job(job: dict) -> None:
    chat_id, message_id = job["chat_id"], job["message_id"]
    outdir = TMP_DIR / f"{chat_id}-{message_id}"
    outdir.mkdir(parents=True, exist_ok=True)
    hook = make_progress_hook(chat_id, message_id)
    if job["mode"] == "audio":
        opts, suffix = build_audio_opts(outdir=outdir, progress_hook=hook), ".mp3"
    else:
        opts, suffix = build_video_opts(job["height"], outdir=outdir, progress_hook=hook), ".mp4"
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(job["url"], download=True)
            path = Path(ydl.prepare_filename(info)).with_suffix(suffix)
    except yt_dlp.utils.YoutubeDLError as e:
        reason = str(e).splitlines()[0][:200]
        tg("editMessageText", chat_id=chat_id, message_id=message_id,
           text=f"❌ Download failed: {reason}")
        shutil.rmtree(outdir, ignore_errors=True)
        return
    except Exception:
        shutil.rmtree(outdir, ignore_errors=True)
        raise
    try:
        deliver(chat_id, message_id, path, job["mode"], job["title"])
    except Exception:
        shutil.rmtree(outdir, ignore_errors=True)
        raise


def worker() -> None:
    while True:
        job = jobs.get()
        try:
            process_job(job)
        except Exception:
            log.exception("job crashed")
            tg("editMessageText", chat_id=job["chat_id"], message_id=job["message_id"],
               text="❌ Something went wrong with this download.")
        finally:
            jobs.task_done()


# ---------------------------------------------------------------------------
# Update handlers
# ---------------------------------------------------------------------------

def handle_message(msg: dict) -> None:
    chat_id = msg["chat"]["id"]
    text = (msg.get("text") or "").strip()
    if not is_youtube_url(text):
        tg("sendMessage", chat_id=chat_id,
           text="Send me a YouTube link and I'll download it 🎬")
        return
    tg("sendChatAction", chat_id=chat_id, action="typing")
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "noplaylist": True}) as ydl:
            info = ydl.extract_info(text, download=False)
    except yt_dlp.utils.YoutubeDLError as e:
        reason = str(e).splitlines()[0][:200]
        tg("sendMessage", chat_id=chat_id, text=f"❌ Couldn't fetch that video: {reason}")
        return
    title = info.get("title", "unknown")
    sent = tg("sendMessage", chat_id=chat_id, text=f"🎯 {title}\nChoose format:",
              reply_markup=format_menu_keyboard())
    if sent:
        pending[chat_id] = {
            "url": text,
            "title": title,
            "heights": available_heights(info),
            "message_id": sent["message_id"],
        }


def handle_callback(cb: dict) -> None:
    chat_id = cb["message"]["chat"]["id"]
    message_id = cb["message"]["message_id"]
    tg("answerCallbackQuery", callback_query_id=cb["id"])
    state = pending.get(chat_id)
    if not state or state["message_id"] != message_id:
        tg("editMessageText", chat_id=chat_id, message_id=message_id,
           text="This menu expired — send the link again.")
        return
    try:
        mode, height = parse_callback(cb.get("data", ""))
    except ValueError:
        return
    if mode == "menu":
        if not state["heights"]:
            pending.pop(chat_id, None)
            tg("editMessageText", chat_id=chat_id, message_id=message_id,
               text="❌ No video formats available for this one.")
            return
        tg("editMessageReplyMarkup", chat_id=chat_id, message_id=message_id,
           reply_markup=resolution_keyboard(state["heights"]))
        return
    pending.pop(chat_id, None)
    tg("editMessageText", chat_id=chat_id, message_id=message_id,
       text=f"⏳ Queued: {state['title']}")
    jobs.put({
        "chat_id": chat_id,
        "message_id": message_id,
        "url": state["url"],
        "title": state["title"],
        "mode": mode,
        "height": height,
    })


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main() -> None:
    if not BOT_TOKEN or not ALLOWED_USER_ID:
        sys.exit("Set TELEGRAM_BOT_TOKEN and ALLOWED_USER_ID in .env")
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    threading.Thread(target=worker, daemon=True).start()
    log.info("bot started, polling for updates")
    offset = 0
    while True:
        try:
            resp = requests.post(f"{API}/getUpdates",
                                 json={"timeout": 60, "offset": offset}, timeout=70)
            data = resp.json()
        except (requests.RequestException, ValueError) as e:
            log.warning("poll error: %s", e)
            time.sleep(5)
            continue
        if not data.get("ok"):
            log.warning("getUpdates failed: %s", data.get("description"))
            time.sleep(5)
            continue
        updates = data.get("result", [])
        for update in updates:
            offset = update["update_id"] + 1
            try:
                source = update.get("message") or update.get("callback_query") or {}
                if not is_authorized(source.get("from", {}).get("id"), ALLOWED_USER_ID):
                    continue  # silently ignore anyone else
                if "message" in update:
                    handle_message(update["message"])
                elif "callback_query" in update:
                    handle_callback(update["callback_query"])
            except Exception:
                log.exception("update handling failed")


if __name__ == "__main__":
    main()
