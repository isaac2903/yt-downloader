import pytest

from downloader import available_heights, is_supported_url


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://m.youtube.com/shorts/abc123DEF45",
        "https://x.com/example/status/1234567890",
        "https://mobile.twitter.com/example/status/1234567890",
        "https://rumble.com/v123abc-example.html",
        "https://WWW.X.COM/example/status/1234567890",
    ],
)
def test_accepts_supported_platform_url(url):
    assert is_supported_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "",
        "not a url",
        "ftp://x.com/example/status/123",
        "https://vimeo.com/12345",
        "https://t.co/abc123",
        "https://x.com.evil.example/status/123",
        "https://rumble.com.evil.example/v123.html",
        "https://x.com:bad-port/example/status/123",
    ],
)
def test_rejects_unsupported_or_malformed_url(url):
    assert not is_supported_url(url)


def test_extracts_unique_heights_sorted_descending():
    info = {
        "formats": [
            {"height": 360, "vcodec": "avc1"},
            {"height": 1080, "vcodec": "vp9"},
            {"height": 720, "vcodec": "avc1"},
            {"height": 1080, "vcodec": "avc1"},
        ]
    }
    assert available_heights(info) == [1080, 720, 360]


def test_ignores_audio_only_formats():
    info = {
        "formats": [
            {"height": None, "vcodec": "none", "acodec": "opus"},
            {"vcodec": "none", "acodec": "mp4a"},
            {"height": 480, "vcodec": "avc1"},
        ]
    }
    assert available_heights(info) == [480]


def test_empty_formats_returns_empty_list():
    assert available_heights({"formats": []}) == []
    assert available_heights({}) == []


from pathlib import Path

from downloader import DOWNLOAD_DIR, build_audio_opts, build_video_opts


def test_download_dir_is_downloads_folder():
    assert DOWNLOAD_DIR == Path.home() / "Downloads"


def test_video_opts_cap_resolution_and_merge_mp4():
    opts = build_video_opts(720)
    assert opts["format"] == (
        "bestvideo[vcodec^=avc1][height<=720]+bestaudio[ext=m4a]/"
        "bestvideo[height<=720]+bestaudio/best[height<=720]"
    )
    assert opts["merge_output_format"] == "mp4"
    assert opts["noplaylist"] is True
    assert opts["outtmpl"] == str(DOWNLOAD_DIR / "%(title)s.%(ext)s")


def test_audio_opts_extract_mp3():
    opts = build_audio_opts()
    assert opts["format"] == "bestaudio/best"
    assert opts["noplaylist"] is True
    assert opts["postprocessors"] == [
        {
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }
    ]
    assert opts["outtmpl"] == str(DOWNLOAD_DIR / "%(title)s.%(ext)s")


def test_video_opts_custom_outdir_and_hook():
    calls = []
    hook = calls.append
    opts = build_video_opts(1080, outdir="/tmp/somewhere", progress_hook=hook)
    assert opts["outtmpl"] == "/tmp/somewhere/%(title)s.%(ext)s"
    assert opts["progress_hooks"] == [hook]


def test_audio_opts_custom_outdir_and_hook():
    hook = lambda d: None
    opts = build_audio_opts(outdir="/tmp/elsewhere", progress_hook=hook)
    assert opts["outtmpl"] == "/tmp/elsewhere/%(title)s.%(ext)s"
    assert opts["progress_hooks"] == [hook]


def test_opts_defaults_unchanged():
    from downloader import _progress_hook
    v = build_video_opts(720)
    a = build_audio_opts()
    assert v["outtmpl"] == str(DOWNLOAD_DIR / "%(title)s.%(ext)s")
    assert a["outtmpl"] == str(DOWNLOAD_DIR / "%(title)s.%(ext)s")
    assert v["progress_hooks"] == [_progress_hook]
    assert a["progress_hooks"] == [_progress_hook]
