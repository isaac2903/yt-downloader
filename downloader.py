"""Interactive CLI for downloading public videos via yt-dlp."""

from pathlib import Path
from urllib.parse import urlsplit

import yt_dlp

try:
    from yt_dlp.networking.impersonate import ImpersonateTarget
except ImportError:
    ImpersonateTarget = None

SUPPORTED_HOSTS = frozenset(
    {
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "youtu.be",
        "x.com",
        "www.x.com",
        "mobile.x.com",
        "twitter.com",
        "www.twitter.com",
        "mobile.twitter.com",
        "rumble.com",
        "www.rumble.com",
    }
)

_RUMBLE_HOSTS = frozenset({"rumble.com", "www.rumble.com"})
_impersonate_target = False


def impersonate_target_for(url: str):
    """ImpersonateTarget for Rumble's Cloudflare front, or None when unavailable."""
    if ImpersonateTarget is None:
        return None
    if (urlsplit(url).hostname or "").lower() not in _RUMBLE_HOSTS:
        return None
    global _impersonate_target
    if _impersonate_target is False:
        target = ImpersonateTarget.from_str("chrome-136")
        try:
            with yt_dlp.YoutubeDL({"quiet": True, "impersonate": target}):
                pass
        except yt_dlp.utils.YoutubeDLError:
            target = None
        _impersonate_target = target
    return _impersonate_target


def is_supported_url(url: str) -> bool:
    """Return True for an HTTP URL on an explicitly supported hostname."""
    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname
        parsed.port
    except ValueError:
        return False
    return (
        parsed.scheme.lower() in {"http", "https"}
        and hostname is not None
        and hostname.lower() in SUPPORTED_HOSTS
    )


def is_single_video_info(info: dict) -> bool:
    """Return True for one finished item containing a video stream."""
    if info.get("_type") in {"playlist", "multi_video"}:
        return False
    if info.get("entries") is not None:
        return False
    if info.get("is_live") or info.get("live_status") == "is_live":
        return False
    # Rumble HLS/timeline formats leave vcodec unset (None) because the
    # m3u8 doesn't declare codecs; only vcodec=="none" is explicitly audio.
    return any(
        fmt.get("vcodec") != "none"
        for fmt in info.get("formats", [])
    )


def available_heights(info: dict) -> list[int]:
    """Return unique video heights in info's formats, highest first."""
    heights = {
        f["height"]
        for f in info.get("formats", [])
        if f.get("height") and f.get("vcodec") != "none"
        and f.get("format_note") != "Timeline"
    }
    return sorted(heights, reverse=True)


def postprocess_rumble_info(info: dict, url: str) -> None:
    """Fix Rumble format metadata in-place for correct format selection.

    Two issues:
    1. The 'timeline' format is a storyboard slideshow (not a real video);
       left in, bestvideo grabs it because it's the only acodec='none' format.
    2. HLS video formats have acodec=None (the m3u8 doesn't declare codecs),
       so yt-dlp's bestvideo+bestaudio can't pair them with the separate
       audio stream — it thinks they already contain audio and skips the merge.
    """
    if (urlsplit(url).hostname or "").lower() not in _RUMBLE_HOSTS:
        return
    info["formats"] = [
        f for f in info.get("formats", [])
        if f.get("format_note") != "Timeline"
    ]
    for f in info["formats"]:
        if f.get("vcodec") != "none" and f.get("acodec") is None:
            f["acodec"] = "none"


DOWNLOAD_DIR = Path.home() / "Downloads"


def _progress_hook(d: dict) -> None:
    if d["status"] == "downloading":
        percent = d.get("_percent_str", "?").strip()
        speed = d.get("_speed_str", "?").strip()
        print(f"\r  Downloading... {percent} at {speed}   ", end="", flush=True)
    elif d["status"] == "finished":
        print(f"\r  Download complete, processing...          ")


def _base_opts(outdir=DOWNLOAD_DIR, progress_hook=None) -> dict:
    return {
        "outtmpl": str(Path(outdir) / "%(title)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [progress_hook or _progress_hook],
        "concurrent_fragment_downloads": 4,
    }


def build_video_opts(height: int, outdir=DOWNLOAD_DIR, progress_hook=None) -> dict:
    """yt-dlp options for an MP4 download capped at the given height."""
    return _base_opts(outdir, progress_hook) | {
        # H.264 + AAC so the MP4 plays everywhere (Telegram/iPhone can't
        # decode the AV1 streams yt-dlp prefers by default); falls back to
        # any codec when no H.264 variant exists.
        "format": (
            f"bestvideo[vcodec^=avc1][height<={height}]+bestaudio[ext=m4a]/"
            f"bestvideo[height<={height}]+bestaudio/best[height<={height}]"
        ),
        "merge_output_format": "mp4",
    }


def build_audio_opts(outdir=DOWNLOAD_DIR, progress_hook=None) -> dict:
    """yt-dlp options for a best-audio download converted to 192kbps MP3."""
    return _base_opts(outdir, progress_hook) | {
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
    probe_opts = {"quiet": True, "no_warnings": True, "noplaylist": False}
    imp = impersonate_target_for(url)
    if imp is not None:
        probe_opts["impersonate"] = imp
    with yt_dlp.YoutubeDL(probe_opts) as ydl:
        info = ydl.extract_info(url, download=False)
    postprocess_rumble_info(info, url)
    if not is_single_video_info(info):
        print("  Only public, finished single-video links are supported.")
        return
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
    if imp is not None:
        opts["impersonate"] = imp

    # Extract and download in the SAME YoutubeDL instance so the download
    # shares the extraction session's cookiejar / request context.
    # postprocess_rumble_info runs between the two to fix Rumble format
    # metadata (timeline removal + acodec=None fix) before format selection.
    with yt_dlp.YoutubeDL(opts) as ydl:
        fresh = ydl.extract_info(url, download=False)
        postprocess_rumble_info(fresh, url)
        ydl.process_video_result(fresh, download=True)
        path = Path(ydl.prepare_filename(fresh)).with_suffix(suffix)
    print(f"  Saved to {path}")


def main() -> None:
    print("yt-downloader — public YouTube, X/Twitter, and Rumble videos.")
    print(f"Files are saved to {DOWNLOAD_DIR}")
    while True:
        try:
            url = input("\nVideo URL (q to quit): ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            return
        if url.lower() in ("q", "quit", "exit"):
            return
        if not url:
            continue
        if not is_supported_url(url):
            print("  Send a public YouTube, X/Twitter, or Rumble video URL.")
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
