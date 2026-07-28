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

Run the local API server from the pinned ARM64
[`aiogram/telegram-bot-api`](https://github.com/aiogram/telegram-bot-api)
container. Keep it bound to `127.0.0.1:8081`; do not expose that port through
a router or public tunnel. Store the Telegram API credentials in the separate
root-owned `0600` files shown below, not in Docker environment values:

```sh
sudo install -d -m 700 /etc/telegram-bot-api /var/lib/telegram-bot-api
sudo install -d -m 755 -o raspberrypi -g raspberrypi /tmp/yt-downloader-bot
sudo install -m 600 /dev/null /etc/telegram-bot-api/api-id
sudo install -m 600 /dev/null /etc/telegram-bot-api/api-hash
# Write api_id to api-id and api_hash to api-hash without printing them.

docker run -d \
  --name telegram-bot-api \
  --restart unless-stopped \
  --security-opt no-new-privileges:true \
  --log-opt max-size=10m \
  --log-opt max-file=3 \
  -p 127.0.0.1:8081:8081 \
  -e TELEGRAM_API_ID_FILE=/run/secrets/telegram_api_id \
  -e TELEGRAM_API_HASH_FILE=/run/secrets/telegram_api_hash \
  -e TELEGRAM_LOCAL=1 \
  -v /etc/telegram-bot-api/api-id:/run/secrets/telegram_api_id:ro \
  -v /etc/telegram-bot-api/api-hash:/run/secrets/telegram_api_hash:ro \
  -v /var/lib/telegram-bot-api:/var/lib/telegram-bot-api \
  -v /tmp/yt-downloader-bot:/tmp/yt-downloader-bot:ro \
  aiogram/telegram-bot-api:9.6-linuxarm64@sha256:7c37b90c8e17c42d16ffb7c7ca0bd8db5275e63045436462e752376567b04972
```

The container packages Telegram's official server; see its
[local-mode documentation](https://github.com/tdlib/telegram-bot-api#usage).
Before the first local login, the bot must be deregistered from the hosted API
with [`logOut`](https://core.telegram.org/bots/api#logout). A successful logout
can move to the local server immediately, but returning to the hosted API may
require waiting ten minutes.

On the Pi this deployment uses `MAX_CHAT_BYTES=1900000000`: files at or below
1.9 GB are attempted through Telegram, while larger files go directly to
Drive. Any failed Telegram upload also falls back to Drive.
