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
