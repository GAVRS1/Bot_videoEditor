from __future__ import annotations

from video_editor_bot.bot import build_application
from video_editor_bot.config import load_settings


def main() -> None:
    settings = load_settings()
    settings.workdir.mkdir(parents=True, exist_ok=True)
    application = build_application(settings)
    application.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
