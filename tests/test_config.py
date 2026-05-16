import pytest

from video_editor_bot import config
from video_editor_bot.config import load_settings


def test_load_settings_rejects_placeholder_token(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "PASTE_TELEGRAM_BOT_TOKEN_HERE")
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)

    with pytest.raises(RuntimeError, match="config.py"):
        load_settings()


def test_load_settings_reads_config_constants(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "123456:telegram-token")
    monkeypatch.setattr(config, "WORKDIR", tmp_path)
    monkeypatch.setattr(config, "MAX_VIDEO_MB", 7)
    monkeypatch.setattr(config, "TELEGRAM_DOWNLOAD_LIMIT_MB", 5)
    monkeypatch.setattr(config, "OUTPUT_WIDTH", 720)
    monkeypatch.setattr(config, "OUTPUT_HEIGHT", 1280)
    monkeypatch.setattr(config, "WATERMARK_IMAGE_PATH", tmp_path / "watermark.png")
    monkeypatch.setattr(config, "ASR_PROVIDER", "DISABLED")
    monkeypatch.setattr(config, "WHISPER_MODEL", "small")

    settings = load_settings()

    assert settings.telegram_bot_token == "123456:telegram-token"
    assert settings.workdir == tmp_path
    assert settings.max_video_mb == 7
    assert settings.max_video_bytes == 7 * 1024 * 1024
    assert settings.telegram_download_limit_mb == 5
    assert settings.telegram_download_limit_bytes == 5 * 1024 * 1024
    assert settings.effective_max_video_mb == 5
    assert settings.effective_max_video_bytes == 5 * 1024 * 1024
    assert settings.output_width == 720
    assert settings.output_height == 1280
    assert settings.watermark_image_path == tmp_path / "watermark.png"
    assert settings.asr_provider == "disabled"
    assert settings.whisper_model == "small"


def test_load_settings_prefers_environment_token(monkeypatch) -> None:
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "PASTE_TELEGRAM_BOT_TOKEN_HERE")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:env-token")

    settings = load_settings()

    assert settings.telegram_bot_token == "123456:env-token"


def test_load_settings_reads_dotenv_token(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "PASTE_TELEGRAM_BOT_TOKEN_HERE")
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    (tmp_path / ".env").write_text('TELEGRAM_BOT_TOKEN="123456:dotenv-token"\n', encoding="utf-8")

    settings = load_settings()

    assert settings.telegram_bot_token == "123456:dotenv-token"
