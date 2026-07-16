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
