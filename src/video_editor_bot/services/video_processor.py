from __future__ import annotations

import shlex
import shutil
import subprocess
import re
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


CHARACTER_HEIGHT_RATIO = 0.45
CHARACTER_X_RATIO = 0.10
CHARACTER_BOTTOM_MARGIN = 24
SUBTITLE_BOTTOM_MARGIN = 120


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
        watermark_x_ratio: float = CHARACTER_X_RATIO,
        watermark_y_ratio: float | None = None,
        watermark_height_ratio: float = CHARACTER_HEIGHT_RATIO,
        subtitle_bottom_margin: int = SUBTITLE_BOTTOM_MARGIN,
    ) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if subtitles is not None:
            subtitles = build_styled_ass_subtitles(
                subtitles,
                subtitles.with_suffix(".ass"),
                bottom_margin=subtitle_bottom_margin,
            )
        command = build_edit_ffmpeg_command(
            source,
            destination,
            self.preset,
            subtitles=subtitles,
            watermark=watermark,
            vertical=vertical,
            zoom=zoom,
            watermark_x_ratio=watermark_x_ratio,
            watermark_y_ratio=watermark_y_ratio,
            watermark_height_ratio=watermark_height_ratio,
            subtitle_bottom_margin=subtitle_bottom_margin,
        )
        command[0] = ensure_ffmpeg_available(command[0])
        _run_ffmpeg(command)
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
        _run_ffmpeg(command)
        return destination

    def render_subtitles(self, source: Path, destination: Path, subtitles: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        command = build_subtitle_ffmpeg_command(source, destination, subtitles, self.preset)
        command[0] = ensure_ffmpeg_available(command[0])
        _run_ffmpeg(command)
        return destination

    def render_watermark(self, source: Path, destination: Path, watermark: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        command = build_watermark_ffmpeg_command(source, destination, watermark, self.preset)
        command[0] = ensure_ffmpeg_available(command[0])
        _run_ffmpeg(command)
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
    watermark_x_ratio: float = CHARACTER_X_RATIO,
    watermark_y_ratio: float | None = None,
    watermark_height_ratio: float = CHARACTER_HEIGHT_RATIO,
    subtitle_bottom_margin: int = SUBTITLE_BOTTOM_MARGIN,
) -> list[str]:
    inputs = ["-i", str(source)]
    input_index = 1
    watermark_index = None
    if watermark is not None:
        inputs.extend(["-stream_loop", "-1", "-i", str(watermark)])
        watermark_index = input_index
        input_index += 1

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
        watermark_x_ratio = _clamp(watermark_x_ratio, 0.0, 1.0)
        watermark_height_ratio = _clamp(watermark_height_ratio, 0.05, 1.0)
        overlay_y = (
            f"H*{_clamp(watermark_y_ratio, 0.0, 1.0):.4f}"
            if watermark_y_ratio is not None
            else f"H-h-{CHARACTER_BOTTOM_MARGIN}"
        )
        filters.append(
            f"[{watermark_index}:v][{current_label}]"
            f"scale2ref=h=ref_h*{watermark_height_ratio:.4f}:w=oh*mdar[wm][wm_base];"
            f"[wm_base][wm]overlay=W*{watermark_x_ratio:.4f}:{overlay_y}:"
            "format=auto:shortest=1[with_wm]"
        )
        current_label = "with_wm"

    if subtitles is not None:
        escaped_subtitles = _escape_filter_path(subtitles)
        filters.append(f"[{current_label}]{_subtitle_filter(escaped_subtitles, subtitle_bottom_margin)}[v]")
    else:
        filters.append(f"[{current_label}]null[v]")

    command = [
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
    ]
    command.append(str(destination))
    return command


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
        f"[1:v][0:v]scale2ref=h=ref_h*{CHARACTER_HEIGHT_RATIO:.2f}:w=oh*mdar[wm][base];"
        f"[base][wm]overlay=W*{CHARACTER_X_RATIO:.2f}:H-h-{CHARACTER_BOTTOM_MARGIN}:"
        "format=auto:shortest=1[v]"
    )
    return [
        "ffmpeg",
        "-y",
        "-i",
        str(source),
        "-stream_loop",
        "-1",
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


def build_styled_ass_subtitles(source: Path, destination: Path, *, bottom_margin: int = SUBTITLE_BOTTOM_MARGIN) -> Path:
    if source.suffix.lower() == ".ass":
        return source

    bottom_margin = max(24, int(bottom_margin))
    content = source.read_text(encoding="utf-8-sig")
    events = _parse_srt_events(content)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as file:
        file.write("[Script Info]\n")
        file.write("ScriptType: v4.00+\n")
        file.write("PlayResX: 1080\n")
        file.write("PlayResY: 1920\n")
        file.write("WrapStyle: 0\n\n")
        file.write("[V4+ Styles]\n")
        file.write(
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
            "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
            "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        )
        file.write(
            "Style: Default,Arial,54,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,"
            f"1,0,0,0,100,100,0,0,1,4,1,2,80,80,{bottom_margin},1\n\n"
        )
        file.write("[Events]\n")
        file.write("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
        for start, end, text in events:
            file.write(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{_escape_ass_text(text)}\n")
    return destination


def _parse_srt_events(content: str) -> list[tuple[str, str, str]]:
    events: list[tuple[str, str, str]] = []
    blocks = re.split(r"\n\s*\n", content.replace("\r\n", "\n").replace("\r", "\n").strip())
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) < 2:
            continue
        time_index = 1 if lines[0].isdigit() else 0
        if time_index >= len(lines) or "-->" not in lines[time_index]:
            continue
        start_raw, end_raw = [part.strip() for part in lines[time_index].split("-->", 1)]
        text = "\\N".join(lines[time_index + 1 :])
        if text:
            events.append((_srt_to_ass_time(start_raw), _srt_to_ass_time(end_raw), text))
    return events


def _srt_to_ass_time(value: str) -> str:
    cleaned = value.split()[0].replace(",", ".")
    hours, minutes, seconds = cleaned.split(":")
    seconds_value = float(seconds)
    return f"{int(hours)}:{int(minutes):02}:{seconds_value:05.2f}"


def _escape_ass_text(text: str) -> str:
    return text.replace("{", r"\{").replace("}", r"\}")


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


def _run_ffmpeg(command: list[str]) -> None:
    kwargs = {}
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    subprocess.run(command, check=True, **kwargs)


def command_to_shell(command: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def _escape_filter_path(path: Path) -> str:
    return str(path).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _subtitle_filter(escaped_subtitles: str, bottom_margin: int = SUBTITLE_BOTTOM_MARGIN) -> str:
    if escaped_subtitles.lower().endswith(".ass"):
        return f"ass='{escaped_subtitles}'"

    bottom_margin = max(0, int(bottom_margin))
    force_style = (
        "FontName=Arial,"
        "FontSize=14,"
        "Alignment=2,"
        f"MarginV={bottom_margin},"
        "PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00000000,"
        "BorderStyle=1,"
        "Outline=2,"
        "Shadow=1"
    )
    return f"subtitles='{escaped_subtitles}':force_style='{force_style}'"
