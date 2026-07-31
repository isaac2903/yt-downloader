# Public YouTube, X, and Rumble Downloads

Date: 2026-07-31

## Goal

Allow the existing CLI and private Telegram bot to download public,
single-video links from YouTube, X/Twitter, and Rumble through the installed
yt-dlp extractors.

Preserve the current format menu, resolution selection, MP3 conversion,
disk-space preflight, local Telegram delivery up to 1.9 GB, Google Drive
fallback, authorization, progress messages, and temporary-file cleanup.

## Scope

Supported inputs:

- individual YouTube watch, Shorts, and `youtu.be` links already accepted;
- public X/Twitter status links containing one video or animated GIF; and
- public individual Rumble video pages.

Explicitly out of scope:

- playlists, channels, profiles, and search/result pages;
- X/Twitter posts containing multiple videos;
- X Spaces and other audio-only pages;
- active livestreams;
- private, paid, age-gated, region-locked, or login-required media;
- browser cookies or social-account credentials; and
- arbitrary sites handled by yt-dlp's generic extractor.

The first version will not add per-platform settings, new commands, new
dependencies, or new services.

## Current State

- Both the CLI and Telegram bot use yt-dlp for metadata extraction and media
  download.
- The Pi's deployed yt-dlp version is `2026.07.04`, which includes YouTube,
  Twitter, and Rumble extractors.
- `downloader.py` currently rejects every non-YouTube URL before yt-dlp sees
  it through `is_youtube_url`.
- `telegram_bot.py` imports that validator and otherwise uses platform-neutral
  yt-dlp metadata, format, disk, and delivery functions.
- The local Telegram Bot API and Drive fallback operate on the completed file
  and do not depend on the source platform.

## Chosen Approach

Use a two-stage gate:

1. Parse the submitted URL and allow only exact, known hostnames for YouTube,
   X/Twitter, and Rumble.
2. Ask yt-dlp for metadata and accept it only when it represents one finite
   item with at least one video format.

This is preferred over strict per-platform path regular expressions because
those become stale when a site changes its URL layout. It is preferred over
accepting every URL because yt-dlp's generic extractor can make arbitrary
network requests and produces less predictable behavior.

## URL Validation

Replace `is_youtube_url` with the shared `is_supported_url` helper. Parse with
Python's standard URL parser rather than a broad regular expression.

Requirements:

- permit only `http` and `https` schemes;
- normalize the parsed hostname to lowercase;
- accept only these hosts:
  - `youtube.com`, `www.youtube.com`, `m.youtube.com`, and `youtu.be`;
  - `x.com`, `www.x.com`, `mobile.x.com`, `twitter.com`,
    `www.twitter.com`, and `mobile.twitter.com`;
  - `rumble.com` and `www.rumble.com`;
- reject empty, malformed, relative, and non-HTTP URLs; and
- reject hostname suffix tricks such as `x.com.evil.example`.

Do not add `t.co` or arbitrary subdomains in the first version. Normal copied
X links already use `x.com`, and an explicit list keeps the trust boundary
clear.

## Media Eligibility

Add one shared metadata predicate in `downloader.py` for both interfaces. An
extracted item is eligible only when:

- it is not a playlist, collection, channel, profile, or multi-video result;
- it has no `entries` collection;
- it is not marked as an active live broadcast; and
- at least one format has a video codec.

An X animated GIF qualifies when yt-dlp exposes it as a video format. An
audio-only X Space does not qualify.

Keep `noplaylist=True` as defense in depth, but do not rely on it as the only
collection check. If yt-dlp returns collection metadata, reject it instead of
silently choosing the first entry.

## User Flow

1. The user submits a link through the CLI or Telegram.
2. The shared URL validator rejects unsupported hosts before any extraction.
3. yt-dlp extracts metadata without downloading.
4. The shared eligibility check rejects collections, multiple media, audio-only
   pages, and active livestreams.
5. The existing Video/Audio menu and available resolution list are shown.
6. The existing disk-space preflight runs before the job is queued.
7. yt-dlp downloads and ffmpeg processes the selected output as today.
8. The completed file follows the existing Telegram/Drive delivery rules.

No source-platform-specific downloader class or delivery branch is needed.

## Format Behavior

Retain the current video selection expression:

- prefer H.264 video plus M4A audio when separate streams are available;
- fall back to the best available video/audio combination; and
- fall back to a combined format at or below the selected height.

Retain MP4 merge output for video and 192 kbps MP3 conversion for audio.
Twitter and Rumble commonly expose combined formats, which use the existing
final fallback without a special case.

## Error Handling and Wording

Update the generic prompt to request a public YouTube, X/Twitter, or Rumble
video link.

Use separate messages for:

- unsupported or malformed hosts;
- supported hosts whose result is a playlist, channel, profile, multi-video
  post, Space, audio-only page, or active livestream; and
- yt-dlp extraction failures, retaining the existing bounded error detail.

Do not claim that a login-required item is downloadable. The first release
will fail safely without storing cookies or account credentials.

## Security and Resource Impact

- The bot remains restricted to the configured Telegram user ID.
- Exact host matching prevents disguised third-party domains from reaching
  yt-dlp through this feature.
- No cookies, tokens, or platform credentials are added.
- No new daemon, container, worker, or dependency is added.
- Idle CPU and memory usage should remain unchanged; only active downloads
  consume the existing yt-dlp, ffmpeg, disk, and network resources.
- The existing `DISK_HEADROOM = 2.2` preflight remains mandatory for every
  source platform.

## Tests

Add focused unit tests that do not depend on live websites:

- accept representative YouTube, X/Twitter, and Rumble URLs;
- accept uppercase hostnames after normalization;
- reject unsupported hosts, malformed URLs, non-HTTP schemes, and hostname
  suffix attacks;
- accept a single finite video metadata object;
- reject playlist/entries, multi-video, audio-only, and active-live metadata;
- verify the Telegram prompt names all three platforms; and
- keep every existing format, disk, Telegram, cleanup, and Drive fallback test
  passing.

Live website checks are deployment verification, not unit tests, because
external pages and extractor behavior change independently of this repository.

## Deployment and Verification

Implement and test in an isolated worktree. Before changing the Pi:

1. run the complete local test suite;
2. review the focused diff for platform-specific assumptions and secret
   exposure;
3. verify the live downloader has no active yt-dlp, ffmpeg, or rclone job; and
4. back up the current bot source and ignored environment file.

Then fast-forward the clean Pi checkout and restart only
`yt-downloader-bot.service`. Do not restart or modify n8n, PostgreSQL,
pgAdmin, cloudflared, or the local Telegram Bot API container.

After deployment:

- verify the bot is active and polling through `127.0.0.1:8081`;
- verify n8n and cloudflared remain healthy;
- test one public single-video X status and one public individual Rumble video;
- confirm the usual format/resolution menu appears;
- complete at least one small real download from each platform; and
- confirm the job-specific temporary directory is removed after delivery.

## Acceptance Criteria

- Existing YouTube links continue to behave as before.
- A public, single-video X/Twitter status can be downloaded through the normal
  Telegram flow.
- A public, individual Rumble video can be downloaded through the normal
  Telegram flow.
- Unsupported hosts and disguised hostnames are rejected before extraction.
- Collections, multiple-media results, Spaces, audio-only pages, and active
  livestreams are rejected rather than partially downloaded.
- No cookies, credentials, services, or dependencies are added.
- Disk preflight, local Telegram delivery, Drive fallback, and cleanup remain
  unchanged and covered by the passing test suite.
- The Pi deployment restarts only the downloader bot and leaves n8n and the
  supporting infrastructure healthy.
