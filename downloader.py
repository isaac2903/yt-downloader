"""Interactive CLI for downloading YouTube videos via yt-dlp."""

import re
from pathlib import Path

import yt_dlp

YOUTUBE_URL_RE = re.compile(
    r"^https?://"
    r"(?:(?:www\.|m\.)?youtube\.com/(?:watch\?\S*v=|shorts/)|youtu\.be/)"
    r"[\w-]{6,}",
    re.IGNORECASE,
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


def _prompt_choice(prompt: str, choices: list[str]) -> int:
    """Show numbered choices; return the selected index."""
    for i, choice in enumerate(choices, 1):
        print(f"  {i}. {choice}")
    while True:
        raw = input(prompt).strip()
        if raw.isdigit() and 1 <= int(raw) <= len(choices):
            return int(raw) - 1
        print(f"  Please enter a number between 1 and {len(choices)}.")


def download(url: str) -> None:
    """Fetch info for url, ask video/audio + resolution, download."""
    print("  Fetching video info...")
    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "noplaylist": True}) as ydl:
        info = ydl.extract_info(url, download=False)
    print(f"  Title: {info.get('title', 'unknown')}")

    mode = _prompt_choice("Choose format: ", ["Video (MP4)", "Audio only (MP3)"])
    if mode == 0:
        heights = available_heights(info)
        if not heights:
            print("  No video formats found for this URL.")
            return
        pick = _prompt_choice("Choose resolution: ", [f"{h}p" for h in heights])
        opts = build_video_opts(heights[pick])
        suffix = ".mp4"
    else:
        opts = build_audio_opts()
        suffix = ".mp3"

    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])
        path = Path(ydl.prepare_filename(info)).with_suffix(suffix)
    print(f"  Saved to {path}")


def main() -> None:
    print("yt-downloader — paste a YouTube link, get the video.")
    print(f"Files are saved to {DOWNLOAD_DIR}")
    while True:
        try:
            url = input("\nYouTube URL (q to quit): ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            return
        if url.lower() in ("q", "quit", "exit"):
            return
        if not url:
            continue
        if not is_youtube_url(url):
            print("  That doesn't look like a YouTube video URL. Try again.")
            continue
        try:
            download(url)
        except yt_dlp.utils.YoutubeDLError as e:
            print(f"  Download failed: {e}")
        except KeyboardInterrupt:
            print("\n  Cancelled — back to the prompt.")
        except EOFError:
            print()
            return


if __name__ == "__main__":
    main()
