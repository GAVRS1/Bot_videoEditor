from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VideoPreset:
    width: int = 1080
    height: int = 1920
    crf: int = 23
    audio_bitrate: str = "128k"


@dataclass(frozen=True)
class FFmpegVideoProcessor:
    preset: VideoPreset

    def render_vertical(self, source: Path, destination: Path, subtitles: Path | None = None) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        command = build_vertical_ffmpeg_command(source, destination, self.preset, subtitles)
        subprocess.run(command, check=True)
        return destination


def build_vertical_ffmpeg_command(
    source: Path,
    destination: Path,
    preset: VideoPreset,
    subtitles: Path | None = None,
) -> list[str]:
    base_video = (
        f"[0:v]scale={preset.width}:{preset.height}:force_original_aspect_ratio=increase,"
        f"crop={preset.width}:{preset.height},boxblur=24:2[bg];"
        f"[0:v]scale={preset.width}:{preset.height}:force_original_aspect_ratio=decrease[fg];"
        f"[bg][fg]overlay=(W-w)/2:(H-h)/2"
    )

    if subtitles is not None:
        escaped_subtitles = _escape_filter_path(subtitles)
        video_filter = f"{base_video},subtitles='{escaped_subtitles}'[v]"
    else:
        video_filter = f"{base_video}[v]"

    return [
        "ffmpeg",
        "-y",
        "-i",
        str(source),
        "-filter_complex",
        video_filter,
        "-map",
        "[v]",
        "-map",
        "0:a?",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        str(preset.crf),
        "-c:a",
        "aac",
        "-b:a",
        preset.audio_bitrate,
        "-movflags",
        "+faststart",
        str(destination),
    ]


def command_to_shell(command: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def _escape_filter_path(path: Path) -> str:
    return str(path).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
