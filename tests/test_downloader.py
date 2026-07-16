from downloader import is_youtube_url, available_heights


def test_accepts_standard_watch_url():
    assert is_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")


def test_accepts_short_url():
    assert is_youtube_url("https://youtu.be/dQw4w9WgXcQ")


def test_accepts_shorts_url():
    assert is_youtube_url("https://www.youtube.com/shorts/abc123DEF45")


def test_accepts_mobile_url():
    assert is_youtube_url("https://m.youtube.com/watch?v=dQw4w9WgXcQ")


def test_rejects_non_youtube_url():
    assert not is_youtube_url("https://vimeo.com/12345")


def test_rejects_garbage():
    assert not is_youtube_url("not a url at all")


def test_rejects_empty_string():
    assert not is_youtube_url("")


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
    assert opts["format"] == "bestvideo[height<=720]+bestaudio/best[height<=720]"
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
