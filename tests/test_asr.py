from video_editor_bot.services.asr import _format_srt_time


def test_format_srt_time() -> None:
    assert _format_srt_time(0) == "00:00:00,000"
    assert _format_srt_time(65.432) == "00:01:05,432"
    assert _format_srt_time(3661.9) == "01:01:01,900"
