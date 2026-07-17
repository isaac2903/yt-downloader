import pytest

from telegram_bot import (
    MAX_CHAT_BYTES,
    _parse_user_id,
    deliver_via_chat,
    format_menu_keyboard,
    is_authorized,
    parse_callback,
    resolution_keyboard,
)


def test_parse_callback_audio():
    assert parse_callback("a") == ("audio", None)


def test_parse_callback_menu():
    assert parse_callback("v") == ("menu", None)


def test_parse_callback_video_height():
    assert parse_callback("v:720") == ("video", 720)


@pytest.mark.parametrize("bad", ["", "x", "v:", "v:abc", "a:1", "v:12.5"])
def test_parse_callback_rejects_garbage(bad):
    with pytest.raises(ValueError):
        parse_callback(bad)


def test_deliver_via_chat_threshold():
    assert MAX_CHAT_BYTES == 49 * 1024 * 1024
    assert deliver_via_chat(MAX_CHAT_BYTES)
    assert not deliver_via_chat(MAX_CHAT_BYTES + 1)


def test_is_authorized():
    assert is_authorized(42, 42)
    assert not is_authorized(41, 42)
    assert not is_authorized(None, 42)


def test_menu_keyboard_shape():
    kb = format_menu_keyboard()
    row = kb["inline_keyboard"][0]
    assert [b["callback_data"] for b in row] == ["v", "a"]
    assert row[0]["text"] == "🎬 Video"
    assert row[1]["text"] == "🎵 Audio (MP3)"


def test_resolution_keyboard_rows_of_three():
    kb = resolution_keyboard([2160, 1440, 1080, 720, 480])
    rows = kb["inline_keyboard"]
    assert len(rows) == 2 and len(rows[0]) == 3 and len(rows[1]) == 2
    assert rows[0][0] == {"text": "2160p", "callback_data": "v:2160"}
    assert rows[1][1] == {"text": "480p", "callback_data": "v:480"}


def test_parse_user_id():
    assert _parse_user_id("123456789") == 123456789
    assert _parse_user_id("") == 0
    assert _parse_user_id("not-a-number") == 0
    assert _parse_user_id("12.5") == 0


def test_video_attributes_extracts_dimensions():
    from telegram_bot import video_attributes
    info = {"width": 1920, "height": 1080, "duration": 858}
    assert video_attributes(info) == {
        "width": 1920,
        "height": 1080,
        "duration": 858,
        "supports_streaming": True,
    }


def test_video_attributes_skips_missing_values():
    from telegram_bot import video_attributes
    assert video_attributes({}) == {"supports_streaming": True}
    assert video_attributes({"width": None, "duration": 42}) == {
        "duration": 42,
        "supports_streaming": True,
    }
