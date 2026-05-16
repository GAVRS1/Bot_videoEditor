from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


# ---------------------------------------------------------------------------
# Project settings
# ---------------------------------------------------------------------------
# Edit values in this file only. Batch files and application modules read the
# settings through load_settings() and should not contain project-specific
# configuration.

# 1) Create a Telegram bot with @BotFather.
# 2) Set TELEGRAM_BOT_TOKEN in .env, as an environment variable, or replace
#    the placeholder below with the token from @BotFather.
TELEGRAM_BOT_TOKEN = "PASTE_TELEGRAM_BOT_TOKEN_HERE"

# Temporary files are stored here while videos are being processed.
WORKDIR = Path("workdir")

# Maximum source video size accepted by the bot, in megabytes.
MAX_VIDEO_MB = 50

# Telegram cloud Bot API only lets bots download files up to 20 MB.
# If you run your own local Bot API server, increase this value together with
# MAX_VIDEO_MB. The bot uses the smaller of these two limits.
TELEGRAM_DOWNLOAD_LIMIT_MB = 20

# Output video size. 1080x1920 is a vertical 9:16 format.
OUTPUT_WIDTH = 1080
OUTPUT_HEIGHT = 1920

# Image that is placed over the video in the watermark mode.
WATERMARK_IMAGE_PATH = Path(r"D:/gavrs/иконка.png")

# Subtitles: use "disabled" or "faster-whisper".
ASR_PROVIDER = "faster-whisper"
WHISPER_MODEL = "large-v3-turbo"


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    workdir: Path = WORKDIR
    max_video_mb: int = MAX_VIDEO_MB
    telegram_download_limit_mb: int = TELEGRAM_DOWNLOAD_LIMIT_MB
    output_width: int = OUTPUT_WIDTH
    output_height: int = OUTPUT_HEIGHT
    watermark_image_path: Path = WATERMARK_IMAGE_PATH
    asr_provider: str = ASR_PROVIDER
    whisper_model: str = WHISPER_MODEL

    @property
    def max_video_bytes(self) -> int:
        return self.max_video_mb * 1024 * 1024

    @property
    def telegram_download_limit_bytes(self) -> int:
        return self.telegram_download_limit_mb * 1024 * 1024

    @property
    def effective_max_video_mb(self) -> int:
        return min(self.max_video_mb, self.telegram_download_limit_mb)

    @property
    def effective_max_video_bytes(self) -> int:
        return self.effective_max_video_mb * 1024 * 1024


def load_settings() -> Settings:
    token = _read_token().strip()
    if not token or token == "PASTE_TELEGRAM_BOT_TOKEN_HERE":
        raise RuntimeError(
            "Telegram bot token is not configured. Set TELEGRAM_BOT_TOKEN in .env, "
            "as an environment variable, or in src/video_editor_bot/config.py."
        )

    return Settings(
        telegram_bot_token=token,
        workdir=Path(WORKDIR),
        max_video_mb=int(MAX_VIDEO_MB),
        telegram_download_limit_mb=int(TELEGRAM_DOWNLOAD_LIMIT_MB),
        output_width=int(OUTPUT_WIDTH),
        output_height=int(OUTPUT_HEIGHT),
        watermark_image_path=Path(WATERMARK_IMAGE_PATH),
        asr_provider=ASR_PROVIDER.strip().lower(),
        whisper_model=WHISPER_MODEL.strip(),
    )


def _read_token() -> str:
    return (
        os.getenv("TELEGRAM_BOT_TOKEN")
        or _read_dotenv_value(PROJECT_ROOT / ".env", "TELEGRAM_BOT_TOKEN")
        or TELEGRAM_BOT_TOKEN
    )


def _read_dotenv_value(path: Path, key: str) -> str | None:
    if not path.exists():
        return None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        name, value = line.split("=", 1)
        if name.strip() == key:
            return value.strip().strip('"').strip("'")

    return None
