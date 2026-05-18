from video_editor_bot import config
from video_editor_bot.config import load_desktop_settings, load_settings


def test_load_settings_reads_config_constants(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(config, "WORKDIR", tmp_path)
    monkeypatch.setattr(config, "MAX_VIDEO_MB", 7)
    monkeypatch.setattr(config, "OUTPUT_WIDTH", 720)
    monkeypatch.setattr(config, "OUTPUT_HEIGHT", 1280)
    monkeypatch.setattr(config, "WATERMARK_IMAGE_PATH", tmp_path / "watermark.png")
    monkeypatch.setattr(config, "ASR_PROVIDER", "DISABLED")
    monkeypatch.setattr(config, "WHISPER_MODEL", "small")

    settings = load_settings()

    assert settings.workdir == tmp_path
    assert settings.max_video_mb == 7
    assert settings.max_video_bytes == 7 * 1024 * 1024
    assert settings.output_width == 720
    assert settings.output_height == 1280
    assert settings.watermark_image_path == tmp_path / "watermark.png"
    assert settings.asr_provider == "disabled"
    assert settings.whisper_model == "small"


def test_load_desktop_settings_uses_same_settings(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(config, "WORKDIR", tmp_path)
    monkeypatch.setattr(config, "MAX_VIDEO_MB", 12)

    settings = load_desktop_settings()

    assert settings.workdir == tmp_path
    assert settings.max_video_mb == 12
