import pytest

from downloader import available_heights, is_single_video_info, is_supported_url


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


def test_available_heights_includes_unset_vcodec_with_height():
    # Rumble HLS formats leave vcodec unset (None) but are video streams.
    info = {
        "formats": [
            {"height": 1080, "vcodec": None},
            {"height": 720, "vcodec": None},
            {"height": 192, "vcodec": "none"},
        ]
    }
    assert available_heights(info) == [1080, 720]


def test_accepts_video_info_with_unset_vcodec():
    assert is_single_video_info(
        {"formats": [{"vcodec": None, "height": 1080}]}
    )


def test_empty_formats_returns_empty_list():
    assert available_heights({"formats": []}) == []
    assert available_heights({}) == []


def test_impersonate_target_is_none_for_non_rumble_hosts():
    from downloader import impersonate_target_for
    for url in [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://x.com/example/status/1234567890",
        "https://mobile.twitter.com/example/status/1234567890",
        "https://vimeo.com/12345",
        "",
        "not a url",
    ]:
        assert impersonate_target_for(url) is None


def test_impersonate_target_for_rumble_does_not_raise():
    from downloader import impersonate_target_for
    result = impersonate_target_for("https://rumble.com/v123abc-example.html")
    assert result is None or result.client == "chrome"


def test_postprocess_rumble_info_removes_timeline_and_fixes_acodec():
    from downloader import postprocess_rumble_info
    info = {"formats": [
        {"format_id": "hls-4624", "vcodec": None, "acodec": None, "height": 1080,
         "protocol": "m3u8_native"},
        {"format_id": "timeline-180p", "vcodec": None, "acodec": "none",
         "height": 180, "format_note": "Timeline", "protocol": "https"},
        {"format_id": "audio-192p", "vcodec": "none", "acodec": "aac",
         "height": 192, "protocol": "https"},
    ]}
    postprocess_rumble_info(info, "https://rumble.com/v123abc-example.html")
    ids = [f["format_id"] for f in info["formats"]]
    assert "timeline-180p" not in ids
    assert "hls-4624" in ids
    assert "audio-192p" in ids
    # HLS video format should have acodec fixed to 'none' (video-only)
    hls = next(f for f in info["formats"] if f["format_id"] == "hls-4624")
    assert hls["acodec"] == "none"
    # Audio format should be unchanged
    audio = next(f for f in info["formats"] if f["format_id"] == "audio-192p")
    assert audio["acodec"] == "aac"


def test_postprocess_rumble_info_leaves_non_rumble_untouched():
    from downloader import postprocess_rumble_info
    info = {"formats": [{"format_id": "x", "format_note": "Timeline", "acodec": None}]}
    postprocess_rumble_info(info, "https://youtube.com/watch?v=x")
    assert len(info["formats"]) == 1
    assert info["formats"][0]["acodec"] is None


def test_available_heights_excludes_timeline():
    from downloader import available_heights
    info = {"formats": [
        {"height": 1080, "vcodec": None, "protocol": "m3u8_native"},
        {"height": 180, "vcodec": None, "format_note": "Timeline"},
    ]}
    assert available_heights(info) == [1080]


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


def test_accepts_finite_single_video_info():
    assert is_single_video_info(
        {"formats": [{"vcodec": "avc1.4d", "height": 720}]}
    )


@pytest.mark.parametrize(
    "info",
    [
        {"_type": "playlist", "entries": [{"id": "1"}]},
        {
            "_type": "multi_video",
            "entries": [{"id": "1"}, {"id": "2"}],
        },
        {"entries": [{"id": "1"}]},
        {"formats": [{"vcodec": "none", "acodec": "opus"}]},
        {"is_live": True, "formats": [{"vcodec": "avc1"}]},
        {"live_status": "is_live", "formats": [{"vcodec": "avc1"}]},
    ],
)
def test_rejects_non_single_or_non_finite_video_info(info):
    assert not is_single_video_info(info)


def test_download_stops_before_menu_for_ineligible_info(monkeypatch, capsys):
    import downloader

    class FakeYDL:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def extract_info(self, _url, download):
            assert download is False
            return {"_type": "playlist", "entries": [{"id": "1"}]}

    monkeypatch.setattr(
        downloader.yt_dlp,
        "YoutubeDL",
        lambda _opts: FakeYDL(),
    )
    monkeypatch.setattr(
        downloader,
        "_prompt_choice",
        lambda *_args, **_kwargs: pytest.fail("format menu must not open"),
    )

    downloader.download("https://www.youtube.com/playlist?list=example")

    assert "Only public, finished single-video links are supported." in (
        capsys.readouterr().out
    )


def test_download_rejects_x_video_selector_before_menu(monkeypatch, capsys):
    import downloader

    class FakeYDL:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def extract_info(self, _url, download):
            assert download is False
            if self.opts["noplaylist"]:
                return {"formats": [{"vcodec": "avc1", "height": 720}]}
            return {
                "_type": "multi_video",
                "entries": [{"id": "1"}, {"id": "2"}],
            }

    monkeypatch.setattr(downloader.yt_dlp, "YoutubeDL", FakeYDL)
    monkeypatch.setattr(
        downloader,
        "_prompt_choice",
        lambda *_args, **_kwargs: pytest.fail("format menu must not open"),
    )

    downloader.download("https://x.com/example/status/123/video/1")

    assert "Only public, finished single-video links are supported." in (
        capsys.readouterr().out
    )
