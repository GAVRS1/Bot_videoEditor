from __future__ import annotations

import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VideoPreset:
    width: int = 1080
    height: int = 1920
    crf: int = 23
    audio_bitrate: str = "128k"


class FFmpegNotFoundError(RuntimeError):
    """Raised when the ffmpeg executable is not available."""


@dataclass(frozen=True)
class FFmpegVideoProcessor:
    preset: VideoPreset

    def render(
        self,
        source: Path,
        destination: Path,
        *,
        subtitles: Path | None = None,
        watermark: Path | None = None,
        vertical: bool = False,
        zoom: float = 1.0,
    ) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        command = build_edit_ffmpeg_command(
            source,
            destination,
            self.preset,
            subtitles=subtitles,
            watermark=watermark,
            vertical=vertical,
            zoom=zoom,
        )
        command[0] = ensure_ffmpeg_available(command[0])
        subprocess.run(command, check=True)
        return destination

    def render_vertical(
        self,
        source: Path,
        destination: Path,
        subtitles: Path | None = None,
        zoom: float = 1.0,
    ) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        command = build_vertical_ffmpeg_command(source, destination, self.preset, subtitles, zoom)
        command[0] = ensure_ffmpeg_available(command[0])
        subprocess.run(command, check=True)
        return destination

    def render_subtitles(self, source: Path, destination: Path, subtitles: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        command = build_subtitle_ffmpeg_command(source, destination, subtitles, self.preset)
        command[0] = ensure_ffmpeg_available(command[0])
        subprocess.run(command, check=True)
        return destination

    def render_watermark(self, source: Path, destination: Path, watermark: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        command = build_watermark_ffmpeg_command(source, destination, watermark, self.preset)
        command[0] = ensure_ffmpeg_available(command[0])
        subprocess.run(command, check=True)
        return destination


def build_vertical_ffmpeg_command(
    source: Path,
    destination: Path,
    preset: VideoPreset,
    subtitles: Path | None = None,
    zoom: float = 1.0,
) -> list[str]:
    zoom = max(1.0, zoom)
    base_video = (
        f"[0:v]scale={preset.width}:{preset.height}:force_original_aspect_ratio=increase,"
        f"crop={preset.width}:{preset.height},boxblur=24:2[bg];"
        f"[0:v]scale={preset.width}:{preset.height}:force_original_aspect_ratio=decrease,"
        f"scale=trunc(iw*{zoom:.2f}/2)*2:trunc(ih*{zoom:.2f}/2)*2[fg];"
        f"[bg][fg]overlay=(W-w)/2:(H-h)/2"
    )

    if subtitles is not None:
        escaped_subtitles = _escape_filter_path(subtitles)
        video_filter = f"{base_video},{_subtitle_filter(escaped_subtitles)}[v]"
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
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        preset.audio_bitrate,
        "-movflags",
        "+faststart",
        str(destination),
    ]


def build_edit_ffmpeg_command(
    source: Path,
    destination: Path,
    preset: VideoPreset,
    *,
    subtitles: Path | None = None,
    watermark: Path | None = None,
    vertical: bool = False,
    zoom: float = 1.0,
) -> list[str]:
    inputs = ["-i", str(source)]
    if watermark is not None:
        inputs.extend(["-loop", "1", "-i", str(watermark)])

    filters: list[str] = []
    current_label = "base"

    if vertical:
        zoom = max(1.0, zoom)
        filters.append(
            f"[0:v]scale={preset.width}:{preset.height}:force_original_aspect_ratio=increase,"
            f"crop={preset.width}:{preset.height},boxblur=24:2[bg];"
            f"[0:v]scale={preset.width}:{preset.height}:force_original_aspect_ratio=decrease,"
            f"scale=trunc(iw*{zoom:.2f}/2)*2:trunc(ih*{zoom:.2f}/2)*2[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2[{current_label}]"
        )
    else:
        filters.append(f"[0:v]null[{current_label}]")

    if watermark is not None:
        filters.append(
            f"[1:v][{current_label}]scale2ref=w=main_w*0.24:h=ow/mdar[wm][wm_base];"
            "[wm_base][wm]overlay=W-w-48:H-h-48:format=auto:shortest=1[with_wm]"
        )
        current_label = "with_wm"

    if subtitles is not None:
        escaped_subtitles = _escape_filter_path(subtitles)
        filters.append(f"[{current_label}]{_subtitle_filter(escaped_subtitles)}[v]")
    else:
        filters.append(f"[{current_label}]null[v]")

    return [
        "ffmpeg",
        "-y",
        *inputs,
        "-filter_complex",
        ";".join(filters),
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
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        preset.audio_bitrate,
        "-movflags",
        "+faststart",
        str(destination),
    ]


def build_subtitle_ffmpeg_command(
    source: Path,
    destination: Path,
    subtitles: Path,
    preset: VideoPreset,
) -> list[str]:
    escaped_subtitles = _escape_filter_path(subtitles)
    return _build_output_command(
        source,
        destination,
        ["-filter_complex", f"[0:v]{_subtitle_filter(escaped_subtitles)}[v]"],
        preset,
    )


def build_watermark_ffmpeg_command(
    source: Path,
    destination: Path,
    watermark: Path,
    preset: VideoPreset,
) -> list[str]:
    video_filter = (
        "[1:v][0:v]scale2ref=w=main_w*0.24:h=ow/mdar[wm][base];"
        "[base][wm]overlay=W-w-48:H-h-48:format=auto:shortest=1[v]"
    )
    return [
        "ffmpeg",
        "-y",
        "-i",
        str(source),
        "-loop",
        "1",
        "-i",
        str(watermark),
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
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        preset.audio_bitrate,
        "-movflags",
        "+faststart",
        str(destination),
    ]


def _build_output_command(
    source: Path,
    destination: Path,
    filter_args: list[str],
    preset: VideoPreset,
) -> list[str]:
    return [
        "ffmpeg",
        "-y",
        "-i",
        str(source),
        *filter_args,
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
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        preset.audio_bitrate,
        "-movflags",
        "+faststart",
        str(destination),
    ]


def ensure_ffmpeg_available(executable: str = "ffmpeg") -> str:
    system_executable = shutil.which(executable)
    if system_executable is not None:
        return system_executable

    if executable == "ffmpeg":
        try:
            import imageio_ffmpeg
        except ImportError:
            pass
        else:
            return imageio_ffmpeg.get_ffmpeg_exe()

    raise FFmpegNotFoundError(
        "FFmpeg was not found. Install FFmpeg and add the ffmpeg executable to PATH."
    )


def command_to_shell(command: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def _escape_filter_path(path: Path) -> str:
    return str(path).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def _subtitle_filter(escaped_subtitles: str) -> str:
    force_style = (
        "FontName=Arial,"
        "FontSize=14,"
        "Alignment=2,"
        "MarginV=120,"
        "PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00000000,"
        "BorderStyle=1,"
        "Outline=2,"
        "Shadow=1"
    )
    return f"subtitles='{escaped_subtitles}':force_style='{force_style}'"
