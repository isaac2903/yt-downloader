"""Interactive CLI for downloading YouTube videos via yt-dlp."""

import re

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
