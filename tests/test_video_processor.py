from pathlib import Path

import pytest

from video_editor_bot.services.video_processor import (
    FFmpegNotFoundError,
    VideoPreset,
    build_edit_ffmpeg_command,
    build_subtitle_ffmpeg_command,
    build_vertical_ffmpeg_command,
    build_watermark_ffmpeg_command,
    command_to_shell,
    ensure_ffmpeg_available,
)


def test_build_vertical_ffmpeg_command_without_subtitles() -> None:
    command = build_vertical_ffmpeg_command(
        Path("input.mp4"),
        Path("output.mp4"),
        VideoPreset(width=1080, height=1920),
    )

    assert command[:4] == ["ffmpeg", "-y", "-i", "input.mp4"]
    shell = command_to_shell(command)
    assert "scale=1080:1920:force_original_aspect_ratio=increase" in shell
    assert "boxblur=24:2" in shell
    assert "subtitles=" not in shell
    assert command[-1] == "output.mp4"


def test_build_vertical_ffmpeg_command_with_subtitles() -> None:
    command = build_vertical_ffmpeg_command(
        Path("input.mp4"),
        Path("output.mp4"),
        VideoPreset(width=720, height=1280),
        Path("subs.srt"),
    )

    shell = command_to_shell(command)
    assert "scale=720:1280" in shell
    assert "subtitles=" in shell
    assert "force_style=" in shell
    assert "subs.srt" in shell


def test_build_vertical_ffmpeg_command_accepts_zoom() -> None:
    command = build_vertical_ffmpeg_command(
        Path("input.mp4"),
        Path("output.mp4"),
        VideoPreset(width=1080, height=1920),
        zoom=1.3,
    )

    shell = command_to_shell(command)

    assert "trunc(iw*1.30/2)*2" in shell
    assert "overlay=(W-w)/2:(H-h)/2" in shell


def test_build_subtitle_ffmpeg_command_preserves_audio() -> None:
    command = build_subtitle_ffmpeg_command(
        Path("input.mp4"),
        Path("output.mp4"),
        Path("subs.srt"),
        VideoPreset(),
    )

    shell = command_to_shell(command)

    assert "subtitles=" in shell
    assert "-map '0:a?'" in shell


def test_build_watermark_ffmpeg_command_uses_second_input_and_bottom_corner() -> None:
    command = build_watermark_ffmpeg_command(
        Path("input.mp4"),
        Path("output.mp4"),
        Path("watermark.png"),
        VideoPreset(),
    )

    shell = command_to_shell(command)

    assert "-loop 1" in shell
    assert "-i watermark.png" in shell
    assert "main_w*0.24" in shell
    assert "overlay=W-w-48:H-h-48" in shell


def test_build_edit_ffmpeg_command_combines_vertical_subtitles_and_watermark() -> None:
    command = build_edit_ffmpeg_command(
        Path("input.mp4"),
        Path("output.mp4"),
        VideoPreset(width=1080, height=1920),
        subtitles=Path("subs.srt"),
        watermark=Path("watermark.png"),
        vertical=True,
        zoom=1.3,
    )

    shell = command_to_shell(command)

    assert "-loop 1" in shell
    assert "-i watermark.png" in shell
    assert "scale=1080:1920" in shell
    assert "trunc(iw*1.30/2)*2" in shell
    assert "overlay=W-w-48:H-h-48:format=auto:shortest=1" in shell
    assert "subtitles=" in shell
    assert command[-1] == "output.mp4"


def test_ensure_ffmpeg_available_raises_for_missing_executable() -> None:
    with pytest.raises(FFmpegNotFoundError, match="FFmpeg was not found"):
        ensure_ffmpeg_available("definitely-not-ffmpeg")
