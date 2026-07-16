from downloader import is_youtube_url


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
