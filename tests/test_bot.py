from telegram.error import BadRequest

from video_editor_bot.bot import (
    EditState,
    FFMPEG_NOT_FOUND_MESSAGE,
    _guess_extension,
    _is_file_too_big_error,
    _result_caption,
    _selection_text,
    _video_too_large_message,
)
from video_editor_bot.config import Settings


def test_guess_extension_defaults_to_mp4_without_file_name() -> None:
    assert _guess_extension(None) == ".mp4"


def test_guess_extension_normalizes_known_file_name_extension() -> None:
    assert _guess_extension("Clip.MOV") == ".mov"


def test_is_file_too_big_error_matches_telegram_bad_request_text() -> None:
    assert _is_file_too_big_error(BadRequest("File is too big"))
    assert not _is_file_too_big_error(BadRequest("chat not found"))


def test_video_too_large_message_mentions_telegram_limit_when_it_is_lower() -> None:
    settings = Settings(
        telegram_bot_token="123:token",
        max_video_mb=50,
        telegram_download_limit_mb=20,
    )

    message = _video_too_large_message(settings)

    assert "20 MB" in message
    assert "Telegram Bot API" in message
    assert "TELEGRAM_DOWNLOAD_LIMIT_MB" in message


def test_video_too_large_message_uses_project_limit_when_it_is_lower() -> None:
    settings = Settings(
        telegram_bot_token="123:token",
        max_video_mb=10,
        telegram_download_limit_mb=20,
    )

    assert _video_too_large_message(settings) == "Видео слишком большое. Лимит: 10 MB."


def test_ffmpeg_not_found_message_explains_install_and_restart() -> None:
    assert "FFmpeg" in FFMPEG_NOT_FOUND_MESSAGE
    assert "PATH" in FFMPEG_NOT_FOUND_MESSAGE
    assert "перезапусти" in FFMPEG_NOT_FOUND_MESSAGE


def test_selection_text_lists_multiple_enabled_actions() -> None:
    state = EditState(subtitles=True, vertical=True, watermark=True, zoom=1.3)

    text = _selection_text(state)

    assert "вертикальное видео, зум 1.30" in text
    assert "титры" in text
    assert "водяной знак" in text


def test_result_caption_lists_combined_actions() -> None:
    state = EditState(subtitles=True, vertical=True, watermark=True)

    assert _result_caption(state) == "Готово: вертикальное видео, титры, водяной знак"
