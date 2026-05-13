from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


# ---------------------------------------------------------------------------
# Project settings
# ---------------------------------------------------------------------------
# Edit values in this file only. Batch files and application modules read the
# settings through load_settings() and should not contain project-specific
# configuration.

# 1) Create a Telegram bot with @BotFather.
# 2) Replace the placeholder below with the token from @BotFather.
TELEGRAM_BOT_TOKEN = "PASTE_TELEGRAM_BOT_TOKEN_HERE"

# Temporary files are stored here while videos are being processed.
WORKDIR = Path("workdir")

# Maximum source video size accepted by the bot, in megabytes.
MAX_VIDEO_MB = 50

# Output video size. 1080x1920 is a vertical 9:16 format.
OUTPUT_WIDTH = 1080
OUTPUT_HEIGHT = 1920

# Subtitles: use "disabled" or "faster-whisper".
ASR_PROVIDER = "disabled"
WHISPER_MODEL = "base"


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    workdir: Path = WORKDIR
    max_video_mb: int = MAX_VIDEO_MB
    output_width: int = OUTPUT_WIDTH
    output_height: int = OUTPUT_HEIGHT
    asr_provider: str = ASR_PROVIDER
    whisper_model: str = WHISPER_MODEL

    @property
    def max_video_bytes(self) -> int:
        return self.max_video_mb * 1024 * 1024


def load_settings() -> Settings:
    token = TELEGRAM_BOT_TOKEN.strip()
    if not token or token == "PASTE_TELEGRAM_BOT_TOKEN_HERE":
        raise RuntimeError(
            "Telegram bot token is not configured. Open src/video_editor_bot/config.py "
            "and set TELEGRAM_BOT_TOKEN."
        )

    return Settings(
        telegram_bot_token=token,
        workdir=Path(WORKDIR),
        max_video_mb=int(MAX_VIDEO_MB),
        output_width=int(OUTPUT_WIDTH),
        output_height=int(OUTPUT_HEIGHT),
        asr_provider=ASR_PROVIDER.strip().lower(),
        whisper_model=WHISPER_MODEL.strip(),
    )
