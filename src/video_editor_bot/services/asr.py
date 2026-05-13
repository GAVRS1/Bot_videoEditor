from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module, util
from pathlib import Path
from typing import Protocol


class SubtitleGenerator(Protocol):
    def generate_srt(self, video_path: Path, subtitles_path: Path) -> Path | None:
        """Generate subtitles for a video and return the SRT path, or None if disabled."""


@dataclass(frozen=True)
class DisabledSubtitleGenerator:
    def generate_srt(self, video_path: Path, subtitles_path: Path) -> Path | None:
        return None


@dataclass(frozen=True)
class FasterWhisperSubtitleGenerator:
    model_name: str = "base"

    def generate_srt(self, video_path: Path, subtitles_path: Path) -> Path | None:
        if util.find_spec("faster_whisper") is None:
            raise RuntimeError(
                "ASR_PROVIDER=faster-whisper requires optional dependency: pip install -e '.[asr]'"
            )

        faster_whisper = import_module("faster_whisper")
        model = faster_whisper.WhisperModel(self.model_name, device="cpu", compute_type="int8")
        segments, _info = model.transcribe(str(video_path), vad_filter=True)

        with subtitles_path.open("w", encoding="utf-8") as file:
            for index, segment in enumerate(segments, start=1):
                file.write(f"{index}\n")
                file.write(f"{_format_srt_time(segment.start)} --> {_format_srt_time(segment.end)}\n")
                file.write(f"{segment.text.strip()}\n\n")

        return subtitles_path


def build_subtitle_generator(provider: str, model_name: str) -> SubtitleGenerator:
    if provider == "disabled":
        return DisabledSubtitleGenerator()
    if provider == "faster-whisper":
        return FasterWhisperSubtitleGenerator(model_name=model_name)
    raise ValueError(f"Unsupported ASR_PROVIDER: {provider}")


def _format_srt_time(seconds: float) -> str:
    milliseconds = int(round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"
