from pathlib import Path

import pytest

from video_editor_bot.services.video_processor import (
    FFmpegNotFoundError,
    VideoPreset,
    build_vertical_ffmpeg_command,
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
    assert "subs.srt" in shell


def test_ensure_ffmpeg_available_raises_for_missing_executable() -> None:
    with pytest.raises(FFmpegNotFoundError, match="FFmpeg was not found"):
        ensure_ffmpeg_available("definitely-not-ffmpeg")
