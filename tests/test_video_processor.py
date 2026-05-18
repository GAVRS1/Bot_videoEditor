from pathlib import Path

import pytest

from video_editor_bot.services.video_processor import (
    FFmpegNotFoundError,
    VideoPreset,
    build_edit_ffmpeg_command,
    build_styled_ass_subtitles,
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


def test_build_watermark_ffmpeg_command_uses_second_input_and_large_centered_character() -> None:
    command = build_watermark_ffmpeg_command(
        Path("input.mp4"),
        Path("output.mp4"),
        Path("watermark.png"),
        VideoPreset(),
    )

    shell = command_to_shell(command)

    assert "-stream_loop -1" in shell
    assert "-i watermark.png" in shell
    assert "ref_h*0.45" in shell
    assert "overlay=W*0.10:H-h-24" in shell


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

    assert "-stream_loop -1" in shell
    assert "-i watermark.png" in shell
    assert "scale=1080:1920" in shell
    assert "trunc(iw*1.30/2)*2" in shell
    assert "overlay=W*0.1000:H-h-24:format=auto:shortest=1" in shell
    assert "subtitles=" in shell
    assert command[-1] == "output.mp4"


def test_build_edit_ffmpeg_command_accepts_custom_watermark_and_subtitle_position() -> None:
    command = build_edit_ffmpeg_command(
        Path("input.mp4"),
        Path("output.mp4"),
        VideoPreset(width=1080, height=1920),
        subtitles=Path("subs.srt"),
        watermark=Path("watermark.png"),
        watermark_x_ratio=0.25,
        watermark_y_ratio=0.35,
        watermark_height_ratio=0.20,
        subtitle_bottom_margin=64,
    )

    shell = command_to_shell(command)

    assert "scale2ref=h=ref_h*0.2000" in shell
    assert "overlay=W*0.2500:H*0.3500" in shell
    assert "MarginV=64" in shell


def test_build_styled_ass_subtitles_writes_positioned_ass_file(tmp_path) -> None:
    source = tmp_path / "subtitles.srt"
    destination = tmp_path / "subtitles.ass"
    source.write_text(
        "1\n00:00:01,000 --> 00:00:02,500\nПривет\n\n"
        "2\n00:00:03,000 --> 00:00:04,000\nВторая строка\n",
        encoding="utf-8",
    )

    result = build_styled_ass_subtitles(source, destination, bottom_margin=72)
    content = result.read_text(encoding="utf-8")

    assert result == destination
    assert "Style: Default,Arial,54" in content
    assert ",72,1" in content
    assert "Dialogue: 0,0:00:01.00,0:00:02.50" in content
    assert "Привет" in content


def test_ensure_ffmpeg_available_raises_for_missing_executable() -> None:
    with pytest.raises(FFmpegNotFoundError, match="FFmpeg was not found"):
        ensure_ffmpeg_available("definitely-not-ffmpeg")
