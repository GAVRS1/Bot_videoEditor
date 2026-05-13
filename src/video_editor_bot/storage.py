from __future__ import annotations

from pathlib import Path

from telegram import File, Message, Video


def get_video_from_message(message: Message) -> Video | None:
    if message.video is not None:
        return message.video
    if message.document is not None and message.document.mime_type and message.document.mime_type.startswith("video/"):
        return message.document  # type: ignore[return-value]
    return None


async def download_telegram_file(file: File, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    await file.download_to_drive(custom_path=destination)
    return destination
