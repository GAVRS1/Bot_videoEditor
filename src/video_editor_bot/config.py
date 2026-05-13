from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    workdir: Path = Path("/tmp/video-editor-bot")
    max_video_mb: int = 50
    output_width: int = 1080
    output_height: int = 1920
    asr_provider: str = "disabled"
    whisper_model: str = "base"

    @property
    def max_video_bytes(self) -> int:
        return self.max_video_mb * 1024 * 1024


def load_settings() -> Settings:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")

    return Settings(
        telegram_bot_token=token,
        workdir=Path(os.environ.get("WORKDIR", "/tmp/video-editor-bot")),
        max_video_mb=int(os.environ.get("MAX_VIDEO_MB", "50")),
        output_width=int(os.environ.get("OUTPUT_WIDTH", "1080")),
        output_height=int(os.environ.get("OUTPUT_HEIGHT", "1920")),
        asr_provider=os.environ.get("ASR_PROVIDER", "disabled").strip().lower(),
        whisper_model=os.environ.get("WHISPER_MODEL", "base").strip(),
    )
