"""Interactive CLI for downloading YouTube videos via yt-dlp."""

import re
from pathlib import Path

YOUTUBE_URL_RE = re.compile(
    r"^https?://"
    r"(?:(?:www\.|m\.)?youtube\.com/(?:watch\?\S*v=|shorts/)|youtu\.be/)"
    r"[\w-]{6,}"
)


def is_youtube_url(url: str) -> bool:
    """Return True if url looks like a YouTube single-video URL."""
    return bool(YOUTUBE_URL_RE.match(url))


def available_heights(info: dict) -> list[int]:
    """Return unique video heights in info's formats, highest first."""
    heights = {
        f["height"]
        for f in info.get("formats", [])
        if f.get("height") and f.get("vcodec") not in (None, "none")
    }
    return sorted(heights, reverse=True)


DOWNLOAD_DIR = Path.home() / "Downloads"

OUTPUT_TEMPLATE = str(DOWNLOAD_DIR / "%(title)s.%(ext)s")


def _progress_hook(d: dict) -> None:
    if d["status"] == "downloading":
        percent = d.get("_percent_str", "?").strip()
        speed = d.get("_speed_str", "?").strip()
        print(f"\r  Downloading... {percent} at {speed}   ", end="", flush=True)
    elif d["status"] == "finished":
        print(f"\r  Download complete, processing...          ")


def _base_opts() -> dict:
    return {
        "outtmpl": OUTPUT_TEMPLATE,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [_progress_hook],
    }


def build_video_opts(height: int) -> dict:
    """yt-dlp options for an MP4 download capped at the given height."""
    return _base_opts() | {
        "format": f"bestvideo[height<={height}]+bestaudio/best[height<={height}]",
        "merge_output_format": "mp4",
    }


def build_audio_opts() -> dict:
    """yt-dlp options for a best-audio download converted to 192kbps MP3."""
    return _base_opts() | {
        "format": "bestaudio/best",
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
    }
