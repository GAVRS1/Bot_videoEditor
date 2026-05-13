from __future__ import annotations

import asyncio

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from video_editor_bot.config import Settings
from video_editor_bot.services.asr import build_subtitle_generator
from video_editor_bot.services.jobs import create_video_job
from video_editor_bot.services.video_processor import FFmpegVideoProcessor, VideoPreset
from video_editor_bot.storage import download_telegram_file, get_video_from_message


START_TEXT = """
Привет! Отправь мне видео, и я сделаю вертикальный ролик 9:16 с размытым фоном.

Если на сервере включён ASR_PROVIDER=faster-whisper, я также добавлю автосубтитры.
""".strip()


def build_application(settings: Settings) -> Application:
    processor = FFmpegVideoProcessor(
        VideoPreset(width=settings.output_width, height=settings.output_height)
    )
    subtitles = build_subtitle_generator(settings.asr_provider, settings.whisper_model)

    application = Application.builder().token(settings.telegram_bot_token).build()
    application.bot_data["settings"] = settings
    application.bot_data["processor"] = processor
    application.bot_data["subtitles"] = subtitles

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", start))
    application.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video))
    return application


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message is None:
        return
    await update.effective_message.reply_text(START_TEXT)


async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return

    video = get_video_from_message(message)
    if video is None:
        await message.reply_text("Пришли видеофайл, пожалуйста.")
        return

    settings: Settings = context.application.bot_data["settings"]
    processor: FFmpegVideoProcessor = context.application.bot_data["processor"]
    subtitles = context.application.bot_data["subtitles"]

    file_size = getattr(video, "file_size", None)
    if file_size and file_size > settings.max_video_bytes:
        await message.reply_text(f"Видео слишком большое. Лимит: {settings.max_video_mb} MB.")
        return

    await message.chat.send_action(ChatAction.UPLOAD_VIDEO)
    status = await message.reply_text("Видео получил. Делаю вертикальный формат и фон…")

    extension = _guess_extension(getattr(video, "file_name", None))
    job = create_video_job(settings.workdir, source_extension=extension, with_subtitles=True)

    telegram_file = await context.bot.get_file(video.file_id)
    await download_telegram_file(telegram_file, job.source_path)

    subtitle_path = (
        await asyncio.to_thread(subtitles.generate_srt, job.source_path, job.subtitles_path)
        if job.with_subtitles
        else None
    )
    await asyncio.to_thread(processor.render_vertical, job.source_path, job.output_path, subtitle_path)

    await status.edit_text("Готово! Загружаю результат…")
    with job.output_path.open("rb") as result:
        await message.reply_video(video=result, caption="Готовый вертикальный ролик 9:16")
    await status.delete()


def _guess_extension(file_name: str | None) -> str:
    if not file_name or "." not in file_name:
        return ".mp4"
    return "." + file_name.rsplit(".", 1)[1].lower()
