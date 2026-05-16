from __future__ import annotations

import asyncio

from video_editor_bot.bot import build_application
from video_editor_bot.config import load_settings


def ensure_event_loop() -> None:
    """Ensure libraries that call asyncio.get_event_loop() have a usable loop.

    Python 3.14 no longer creates a main-thread event loop implicitly.  The
    python-telegram-bot run_polling() helper still asks asyncio for the current
    loop, so create one explicitly when the interpreter has none.
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())
        return

    if loop.is_closed():
        asyncio.set_event_loop(asyncio.new_event_loop())


def main() -> None:
    settings = load_settings()
    settings.workdir.mkdir(parents=True, exist_ok=True)
    ensure_event_loop()
    application = build_application(settings)
    application.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
