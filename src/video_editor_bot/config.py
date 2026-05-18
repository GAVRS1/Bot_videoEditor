from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Project settings
# ---------------------------------------------------------------------------
# Edit values in this file only. Batch files and application modules read the
# settings through load_settings() and should not contain project-specific
# configuration.

# Temporary files are stored here while videos are being processed.
WORKDIR = Path("workdir")

# Maximum source video size accepted by the app, in megabytes.
MAX_VIDEO_MB = 50

# Output video size. 1080x1920 is a vertical 9:16 format.
OUTPUT_WIDTH = 1080
OUTPUT_HEIGHT = 1920

# Image or GIF that is placed over the video in the watermark mode.
WATERMARK_IMAGE_PATH = PROJECT_ROOT / "assets" / "meow-zhe.gif"

# Subtitles: use "disabled" or "faster-whisper".
ASR_PROVIDER = "faster-whisper"
WHISPER_MODEL = "large-v3-turbo"

@dataclass(frozen=True)
class Settings:
    workdir: Path = WORKDIR
    max_video_mb: int = MAX_VIDEO_MB
    output_width: int = OUTPUT_WIDTH
    output_height: int = OUTPUT_HEIGHT
    watermark_image_path: Path = WATERMARK_IMAGE_PATH
    asr_provider: str = ASR_PROVIDER
    whisper_model: str = WHISPER_MODEL

    @property
    def max_video_bytes(self) -> int:
        return self.max_video_mb * 1024 * 1024


def load_settings() -> Settings:
    return Settings(
        workdir=Path(WORKDIR),
        max_video_mb=int(MAX_VIDEO_MB),
        output_width=int(OUTPUT_WIDTH),
        output_height=int(OUTPUT_HEIGHT),
        watermark_image_path=Path(WATERMARK_IMAGE_PATH),
        asr_provider=ASR_PROVIDER.strip().lower(),
        whisper_model=WHISPER_MODEL.strip(),
    )


def load_desktop_settings() -> Settings:
    """Load settings for the desktop app."""

    return load_settings()
