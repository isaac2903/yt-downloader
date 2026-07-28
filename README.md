# yt-downloader

Interactive CLI for downloading YouTube videos as MP4 (pick a resolution) or
MP3. Files are saved to `~/Downloads`.

## Requirements

- Python 3.10+
- ffmpeg (`brew install ffmpeg`)

## Setup (once)

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Usage

```sh
./ytdl
```

Paste a YouTube link when prompted, choose Video (MP4) or Audio only (MP3),
pick a resolution for video, and the file lands in `~/Downloads`. Enter `q`
to quit.

## Development

```sh
.venv/bin/pip install pytest
.venv/bin/pytest
```

## Telegram bot

Send a YouTube link to your private bot; it downloads on the machine
running the bot and sends the file back in the chat (≤49 MB) or uploads
it to Google Drive via rclone (larger).

### Setup

1. Create a bot with [@BotFather](https://t.me/BotFather) (`/newbot`) and
   copy the token.
2. Get your numeric Telegram user ID (message
   [@userinfobot](https://t.me/userinfobot)).
3. `cp .env.example .env` and fill in both values. The bot answers ONLY
   this user ID.
4. Install and configure rclone for large files: `rclone config`
   (create a remote, e.g. `gdrive`, then set `RCLONE_REMOTE=gdrive:YouTube`).
5. Run: `.venv/bin/python telegram_bot.py`

### Raspberry Pi deployment

```sh
# one-time system deps
sudo apt install ffmpeg rclone python3-venv
curl -fsSL https://deno.land/install.sh | sh   # JS runtime for yt-dlp
sudo cp ~/.deno/bin/deno /usr/local/bin/   # make deno visible to the systemd service

git clone https://github.com/isaac2903/yt-downloader.git
cd yt-downloader
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env   # fill in token + user id
rclone config          # one-time Google Drive OAuth

sudo cp yt-downloader-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now yt-downloader-bot
journalctl -u yt-downloader-bot -f   # watch logs
```

### Optional local Telegram Bot API

Telegram's hosted Bot API accepts uploads up to 50 MB. This project uses a
49 MiB (`51,380,224` byte) safety threshold by default and sends larger files
to Drive. Telegram's official local Bot API server raises the upload limit to
2,000 MB and accepts local file paths, so a private Pi deployment can return
most completed downloads directly in Telegram.

The bot has four non-secret settings for this mode:

```dotenv
TELEGRAM_API_BASE=http://127.0.0.1:8081
TELEGRAM_LOCAL_MODE=true
MAX_CHAT_BYTES=1900000000
TELEGRAM_UPLOAD_TIMEOUT_SECONDS=3600
```

The included `telegram-bot-api.service` runs the official server only on
`127.0.0.1:8081`; do not expose that port through a router or public tunnel.
Its Telegram API credentials belong in `/etc/telegram-bot-api.env`, owned by
root with mode `0600`, as `TELEGRAM_API_ID` and `TELEGRAM_API_HASH`. Keep the
bot token in the project's ignored `.env` file. The optional
`yt-downloader-bot-local-api.conf` drop-in makes the downloader wait for the
local API service.

Build the server from Telegram's
[official source](https://github.com/tdlib/telegram-bot-api) and read its
[local-mode documentation](https://github.com/tdlib/telegram-bot-api#usage).
Before the first local login, the bot must be deregistered from the hosted API
with [`logOut`](https://core.telegram.org/bots/api#logout). A successful logout
can move to the local server immediately, but returning to the hosted API may
require waiting ten minutes.

On the Pi this deployment uses `MAX_CHAT_BYTES=1900000000`: files at or below
1.9 GB are attempted through Telegram, while larger files go directly to
Drive. Any failed Telegram upload also falls back to Drive.
