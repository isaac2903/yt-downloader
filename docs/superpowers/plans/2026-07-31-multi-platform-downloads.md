# Multi-Platform Downloads Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow the CLI and private Telegram bot to download public finite single-video links from YouTube, X/Twitter, and Rumble without changing delivery infrastructure.

**Architecture:** Replace the YouTube-only regular expression with exact hostname validation using `urllib.parse`, then gate extracted metadata through one shared finite-single-video predicate. Keep the existing yt-dlp format selection, disk preflight, Telegram/Drive delivery, and cleanup unchanged.

**Tech Stack:** Python 3.10+, yt-dlp, pytest, systemd, Docker-hosted local Telegram Bot API

## Global Constraints

- Implement in an isolated worktree created with `superpowers:using-git-worktrees`.
- Accept only the exact hostnames approved in the design; do not add generic yt-dlp support or `t.co`.
- Do not add dependencies, cookies, platform credentials, commands, containers, or configuration values.
- Preserve the current Video/Audio menus, resolution selection, MP4/MP3 formats, disk preflight, 1.9 GB local Telegram threshold, Drive fallback, authorization, progress updates, and cleanup.
- Do not change or restart n8n, PostgreSQL, pgAdmin, cloudflared, or the local Telegram Bot API container.
- Use mocked metadata in unit tests; live X and Rumble pages are deployment checks only.

---

### Task 1: Replace the YouTube-only URL gate with an exact platform allowlist

**Files:**

- Modify: `downloader.py:1-18`
- Modify: `downloader.py:118-133`
- Modify: `telegram_bot.py:2-5`
- Modify: `telegram_bot.py:24`
- Modify: `telegram_bot.py:386-392`
- Test: `tests/test_downloader.py:1-33`
- Test: `tests/test_telegram_bot.py`

**Interfaces:**

- Produces: `is_supported_url(url: str) -> bool`
- Consumed by: the CLI input loop and Telegram `handle_message`

- [ ] **Step 1: Replace the old URL tests with failing allowlist tests**

At the top of `tests/test_downloader.py`, import `pytest` and replace the individual `is_youtube_url` tests with:

```python
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
```

- [ ] **Step 2: Add a failing Telegram prompt test**

Append to `tests/test_telegram_bot.py`:

```python
def test_handle_message_rejects_unsupported_host(monkeypatch):
    import telegram_bot as bot

    calls = []
    monkeypatch.setattr(
        bot,
        "tg",
        lambda method, **params: calls.append((method, params)),
    )

    bot.handle_message({"chat": {"id": 42}, "text": "https://vimeo.com/123"})

    assert calls == [
        (
            "sendMessage",
            {
                "chat_id": 42,
                "text": (
                    "Send me a public YouTube, X/Twitter, or Rumble "
                    "video link 🎬"
                ),
            },
        )
    ]
```

- [ ] **Step 3: Run the focused tests and confirm they fail for the missing interface**

Run:

```bash
.venv/bin/pytest -q \
  tests/test_downloader.py::test_accepts_supported_platform_url \
  tests/test_downloader.py::test_rejects_unsupported_or_malformed_url \
  tests/test_telegram_bot.py::test_handle_message_rejects_unsupported_host
```

Expected: collection fails because `is_supported_url` does not exist yet.

- [ ] **Step 4: Implement exact hostname validation**

In `downloader.py`, remove `import re`, `YOUTUBE_URL_RE`, and `is_youtube_url`. Add:

```python
from urllib.parse import urlsplit


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


def is_supported_url(url: str) -> bool:
    """Return True for an HTTP URL on an explicitly supported hostname."""
    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname
        parsed.port  # Access validates malformed port values.
    except ValueError:
        return False
    return (
        parsed.scheme.lower() in {"http", "https"}
        and hostname is not None
        and hostname.lower() in SUPPORTED_HOSTS
    )
```

Do not add path matching. The metadata gate in Task 2 is responsible for rejecting profiles, collections, Spaces, and other non-video pages on an allowed host.

- [ ] **Step 5: Switch both interfaces to the new helper and wording**

In `telegram_bot.py`, import `is_supported_url`, call it from `handle_message`, and use this exact unsupported-input prompt:

```python
text="Send me a public YouTube, X/Twitter, or Rumble video link 🎬"
```

Update the module docstring to say the bot handles requested public video/audio rather than requested YouTube video/audio.

In `downloader.py`, use these CLI strings:

```python
print("yt-downloader — public YouTube, X/Twitter, and Rumble videos.")
url = input("\nVideo URL (q to quit): ").strip()
print("  Send a public YouTube, X/Twitter, or Rumble video URL.")
```

Call `is_supported_url(url)` in place of `is_youtube_url(url)`.

- [ ] **Step 6: Run the focused tests and commit**

Run:

```bash
.venv/bin/pytest -q \
  tests/test_downloader.py::test_accepts_supported_platform_url \
  tests/test_downloader.py::test_rejects_unsupported_or_malformed_url \
  tests/test_telegram_bot.py::test_handle_message_rejects_unsupported_host
```

Expected: all focused tests pass.

Commit only the Task 1 files:

```bash
git add -- downloader.py telegram_bot.py tests/test_downloader.py tests/test_telegram_bot.py
git commit -m "feat: allow X and Rumble URLs"
```

---

### Task 2: Reject collections, audio-only pages, and active livestreams

**Files:**

- Modify: `downloader.py` next to `is_supported_url`
- Modify: `downloader.py:92-100`
- Modify: `telegram_bot.py:24`
- Modify: `telegram_bot.py:394-404`
- Test: `tests/test_downloader.py`
- Test: `tests/test_telegram_bot.py`

**Interfaces:**

- Produces: `is_single_video_info(info: dict) -> bool`
- Consumed after metadata extraction by: `download` and `handle_message`

- [ ] **Step 1: Add failing unit tests for the metadata predicate**

Add `is_single_video_info` to the import in `tests/test_downloader.py`, then append:

```python
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
```

- [ ] **Step 2: Add failing integration tests for the CLI and Telegram handler**

Append to `tests/test_downloader.py`:

```python
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
```

Append to `tests/test_telegram_bot.py`:

```python
def test_handle_message_rejects_playlist_metadata(monkeypatch):
    import telegram_bot as bot

    class FakeYDL:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def extract_info(self, _url, download):
            assert download is False
            return {"_type": "playlist", "entries": [{"id": "1"}]}

    calls = []
    bot.pending.pop(42, None)
    monkeypatch.setattr(
        bot.yt_dlp,
        "YoutubeDL",
        lambda _opts: FakeYDL(),
    )
    monkeypatch.setattr(
        bot,
        "tg",
        lambda method, **params: calls.append((method, params)),
    )

    bot.handle_message(
        {
            "chat": {"id": 42},
            "text": "https://www.youtube.com/playlist?list=example",
        }
    )

    assert calls[-1] == (
        "sendMessage",
        {
            "chat_id": 42,
            "text": (
                "❌ Only public, finished single videos are supported—no "
                "playlists, channels, Spaces, multi-video posts, or live "
                "streams."
            ),
        },
    )
    assert 42 not in bot.pending
```

- [ ] **Step 3: Run the new tests and confirm the predicate is missing**

Run:

```bash
.venv/bin/pytest -q \
  tests/test_downloader.py::test_accepts_finite_single_video_info \
  tests/test_downloader.py::test_rejects_non_single_or_non_finite_video_info \
  tests/test_downloader.py::test_download_stops_before_menu_for_ineligible_info \
  tests/test_telegram_bot.py::test_handle_message_rejects_playlist_metadata
```

Expected: collection fails because `is_single_video_info` does not exist yet.

- [ ] **Step 4: Implement the shared metadata predicate**

Add to `downloader.py` after `is_supported_url`:

```python
def is_single_video_info(info: dict) -> bool:
    """Return True for one finished item containing a video stream."""
    if info.get("_type") in {"playlist", "multi_video"}:
        return False
    if info.get("entries") is not None:
        return False
    if info.get("is_live") or info.get("live_status") == "is_live":
        return False
    return any(
        fmt.get("vcodec") not in (None, "none")
        for fmt in info.get("formats", [])
    )
```

Do not infer eligibility from title, URL path, extractor name, or platform.

- [ ] **Step 5: Gate the CLI immediately after metadata extraction**

In `download`, insert this before printing the title or opening either menu:

```python
if not is_single_video_info(info):
    print("  Only public, finished single-video links are supported.")
    return
```

Keep `noplaylist=True` in the metadata and download options.

- [ ] **Step 6: Gate the Telegram handler immediately after extraction**

Import `is_single_video_info` from `downloader`. After the existing `YoutubeDLError` block and before title/menu state, insert:

```python
if not is_single_video_info(info):
    tg(
        "sendMessage",
        chat_id=chat_id,
        text=(
            "❌ Only public, finished single videos are supported—no "
            "playlists, channels, Spaces, multi-video posts, or live streams."
        ),
    )
    return
```

Do not change the extraction-error message; private, region-locked, paid, and login-required pages should continue to fail through that bounded error path.

- [ ] **Step 7: Run the focused tests and commit**

Run:

```bash
.venv/bin/pytest -q \
  tests/test_downloader.py::test_accepts_finite_single_video_info \
  tests/test_downloader.py::test_rejects_non_single_or_non_finite_video_info \
  tests/test_downloader.py::test_download_stops_before_menu_for_ineligible_info \
  tests/test_telegram_bot.py::test_handle_message_rejects_playlist_metadata
```

Expected: all focused tests pass.

Commit only the Task 2 files:

```bash
git add -- downloader.py telegram_bot.py tests/test_downloader.py tests/test_telegram_bot.py
git commit -m "feat: reject unsupported media collections"
```

---

### Task 3: Update documentation and run the complete local regression suite

**Files:**

- Modify: `README.md:1-39`
- Verify: `downloader.py`
- Verify: `telegram_bot.py`
- Verify: `tests/`

**Interfaces:**

- Documents: supported sources, public/single-video boundary, and unchanged delivery behavior
- Preserves: every existing deployment and local Telegram API instruction

- [ ] **Step 1: Update only the platform-specific README wording**

Change the introduction to:

```markdown
Interactive CLI for downloading public single videos from YouTube, X/Twitter,
or Rumble as MP4 (pick a resolution) or MP3. Files are saved to `~/Downloads`.
```

Change the usage paragraph to ask for a public YouTube, X/Twitter, or Rumble video link.

Change the Telegram section opening to:

```markdown
Send a public YouTube, X/Twitter, or Rumble single-video link to your private
bot; it downloads on the machine running the bot and follows the configured
Telegram or Google Drive delivery threshold.
```

Add one short boundary sentence: playlists, channels/profiles, multi-video posts, Spaces/audio-only pages, active livestreams, and login-required media are not supported.

Do not rewrite the Raspberry Pi or local Telegram Bot API instructions.

- [ ] **Step 2: Confirm no old validator references remain**

Run:

```bash
git grep -n -E 'is_youtube_url|YOUTUBE_URL_RE' -- '*.py'
```

Expected: no output. Any match is a regression and must be removed before continuing.

- [ ] **Step 3: Run syntax, whitespace, and full test checks**

Run:

```bash
.venv/bin/python -m py_compile downloader.py telegram_bot.py
.venv/bin/pytest -q
git diff --check
```

Expected: both modules compile, the complete test suite passes, and `git diff --check` prints nothing.

- [ ] **Step 4: Review scope and commit the documentation**

Run:

```bash
git status --short
git diff --stat
git diff -- README.md
```

Expected: only the four implementation/test files and `README.md` have changed across the feature commits; no dependency, environment, service, n8n, or Docker files are touched.

Commit the README change:

```bash
git add -- README.md
git commit -m "docs: document supported video platforms"
```

---

### Task 4: Review, integrate, and deploy only the downloader bot

**Files:**

- Review: complete feature diff against the implementation base
- Update on Pi: `/home/raspberrypi/yt-downloader`
- Back up on Pi: `/home/raspberrypi/backups/`

**Interfaces:**

- Produces: reviewed commits on `main`, pushed to `origin/main`, then fast-forwarded on the Pi
- Restarts: `yt-downloader-bot.service` only

- [ ] **Step 1: Request code review before integration**

Invoke `superpowers:requesting-code-review`. Review the complete diff against the approved design and classify any findings before changing code.

Required review checks:

- exact host matching cannot accept suffix attacks;
- malformed ports fail closed;
- both CLI and Telegram call the same metadata predicate;
- no menu or pending state is created for rejected metadata;
- the format, disk, delivery, retry, and cleanup paths are unchanged; and
- no secret or ignored environment file is staged.

- [ ] **Step 2: Re-run verification after review fixes**

Run:

```bash
.venv/bin/python -m py_compile downloader.py telegram_bot.py
.venv/bin/pytest -q
git diff --check
git status --short --branch
```

Expected: compilation and tests pass, whitespace is clean, and the feature worktree has no uncommitted changes.

- [ ] **Step 3: Integrate with the execution mode's required skill**

Use `superpowers:finishing-a-development-branch` to integrate the reviewed feature into local `main`. Re-run `.venv/bin/pytest -q` on `main` after integration.

Record and push the exact revision:

```bash
MULTIPLATFORM_REVISION=$(git rev-parse HEAD)
git push origin main
git show --stat --oneline "$MULTIPLATFORM_REVISION"
```

Expected: the pushed revision contains only the approved design, plan, feature/test changes, and README update.

- [ ] **Step 4: Prove the Pi is idle before touching it**

Run:

```bash
ssh -i ~/.ssh/id_ed25519_pi raspberrypi@192.168.50.26 '
  set -eu
  test -z "$(pgrep -x ffmpeg || true)"
  test -z "$(pgrep -x rclone || true)"
  test "$(find /tmp/yt-downloader-bot -mindepth 1 -maxdepth 1 -type d | wc -l)" -eq 0
  test -z "$(git -C /home/raspberrypi/yt-downloader status --short --untracked-files=no)"
'
ssh -i ~/.ssh/id_ed25519_pi raspberrypi@192.168.50.26 \
  'docker inspect -f "{{.RestartCount}}" telegram-bot-api' \
  > /tmp/yt-downloader-telegram-api-restarts-before.txt
```

Expected: exit status 0 and a numeric Telegram API restart baseline in `/tmp/yt-downloader-telegram-api-restarts-before.txt`. A populated job directory or matching process means a job may still be active; stop and wait rather than restarting it.

- [ ] **Step 5: Back up current bot files and ignored environment safely**

Run:

```bash
ssh -i ~/.ssh/id_ed25519_pi raspberrypi@192.168.50.26 '
  set -eu
  cd /home/raspberrypi/yt-downloader
  backup_dir=/home/raspberrypi/backups/yt-downloader-before-multiplatform-$(date +%Y%m%d%H%M%S)
  install -d -m 700 "$backup_dir"
  cp downloader.py telegram_bot.py "$backup_dir"/
  install -m 600 .env "$backup_dir/.env"
  echo "$backup_dir"
'
```

Expected: one private backup directory path is printed; no secret value is printed.

- [ ] **Step 6: Fast-forward, validate, and restart only the downloader bot**

Run from local `main`, preserving the `MULTIPLATFORM_REVISION` value from Step 3:

```bash
ssh -i ~/.ssh/id_ed25519_pi raspberrypi@192.168.50.26 "
  set -eu
  cd /home/raspberrypi/yt-downloader
  git pull --ff-only origin main
  test \"\$(git rev-parse HEAD)\" = \"$MULTIPLATFORM_REVISION\"
  .venv/bin/python -m py_compile downloader.py telegram_bot.py
  sudo systemctl restart yt-downloader-bot
"
```

Expected: the Pi is at the exact pushed revision and only `yt-downloader-bot` is restarted.

- [ ] **Step 7: Verify downloader and supporting services without restarting them**

Run:

```bash
TELEGRAM_API_RESTARTS_BEFORE=$(cat /tmp/yt-downloader-telegram-api-restarts-before.txt)
TELEGRAM_API_RESTARTS_AFTER=$(
  ssh -i ~/.ssh/id_ed25519_pi raspberrypi@192.168.50.26 \
    'docker inspect -f "{{.RestartCount}}" telegram-bot-api'
)
test "$TELEGRAM_API_RESTARTS_AFTER" = "$TELEGRAM_API_RESTARTS_BEFORE"

ssh -i ~/.ssh/id_ed25519_pi raspberrypi@192.168.50.26 '
  set -eu
  test "$(systemctl is-active yt-downloader-bot)" = active
  test "$(systemctl is-active cloudflared)" = active
  curl -fsS http://127.0.0.1:5678/healthz >/dev/null
  docker inspect -f "{{.State.Status}} restarts={{.RestartCount}}" telegram-bot-api
  ss -ltn | grep -F "127.0.0.1:8081" >/dev/null
  journalctl -u yt-downloader-bot -n 30 --no-pager
'
```

Expected: downloader and cloudflared are active, n8n health succeeds, the Telegram API container is running with no new restart, loopback port 8081 is listening, and recent bot logs show normal polling without a traceback.

---

### Task 5: Run live X and Rumble acceptance checks

**Files:** None

**Interfaces:**

- Consumes: one user-approved public single-video X status and one user-approved public individual Rumble page
- Produces: end-to-end proof through the real Telegram bot

- [ ] **Step 1: Test a short public X/Twitter video**

Send the approved X status URL to the private Telegram bot.

Expected sequence:

1. title and Video/Audio menu appears;
2. choosing Video shows available resolutions;
3. choosing the smallest useful resolution completes the download;
4. the file is returned directly in Telegram for a result at or below 1.9 GB; and
5. no generic unsupported-host or single-video rejection appears.

- [ ] **Step 2: Test a short public Rumble video**

Repeat the same flow with the approved individual Rumble page.

Expected: title, menus, download, processing, and Telegram delivery behave exactly like the X check.

- [ ] **Step 3: Verify cleanup and final health after both jobs**

Run:

```bash
TELEGRAM_API_RESTARTS_BEFORE=$(cat /tmp/yt-downloader-telegram-api-restarts-before.txt)
TELEGRAM_API_RESTARTS_AFTER=$(
  ssh -i ~/.ssh/id_ed25519_pi raspberrypi@192.168.50.26 \
    'docker inspect -f "{{.RestartCount}}" telegram-bot-api'
)
test "$TELEGRAM_API_RESTARTS_AFTER" = "$TELEGRAM_API_RESTARTS_BEFORE"

ssh -i ~/.ssh/id_ed25519_pi raspberrypi@192.168.50.26 '
  set -eu
  test "$(find /tmp/yt-downloader-bot -mindepth 1 -maxdepth 1 -type d | wc -l)" -eq 0
  test "$(systemctl is-active yt-downloader-bot)" = active
  test "$(systemctl is-active cloudflared)" = active
  curl -fsS http://127.0.0.1:5678/healthz >/dev/null
  docker inspect -f "{{.State.Status}} restarts={{.RestartCount}}" telegram-bot-api
  journalctl -u yt-downloader-bot -n 80 --no-pager
'
```

Expected: no job directory remains, all services are healthy, the local Telegram API was not restarted, and logs contain completed jobs without unhandled errors.

- [ ] **Step 4: Report acceptance evidence**

Report the deployed Git revision, X and Rumble outcomes, delivery route used for each result, cleanup result, and health of `yt-downloader-bot`, n8n, cloudflared, and `telegram-bot-api`. Separate any external extractor/site failure from an application regression.
