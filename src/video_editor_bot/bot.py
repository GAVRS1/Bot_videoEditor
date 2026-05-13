from __future__ import annotations

import asyncio
import logging

from telegram import Update
from telegram.constants import ChatAction
from telegram.error import BadRequest
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from video_editor_bot.config import Settings
from video_editor_bot.services.asr import build_subtitle_generator
from video_editor_bot.services.jobs import create_video_job
from video_editor_bot.services.video_processor import FFmpegNotFoundError, FFmpegVideoProcessor, VideoPreset
from video_editor_bot.storage import download_telegram_file, get_video_from_message


LOGGER = logging.getLogger(__name__)

START_TEXT = """
Привет! Отправь мне видео, и я сделаю вертикальный ролик 9:16 с размытым фоном.

Если в config.py включён ASR_PROVIDER = "faster-whisper", я также добавлю автосубтитры.
""".strip()


FILE_TOO_BIG_TEXT = "file is too big"
FFMPEG_NOT_FOUND_MESSAGE = (
    "Не найден FFmpeg. Установи FFmpeg и добавь ffmpeg.exe в PATH, "
    "затем перезапусти бота."
)


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
    application.add_error_handler(handle_error)
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
    if file_size and file_size > settings.effective_max_video_bytes:
        await message.reply_text(_video_too_large_message(settings))
        return

    await message.chat.send_action(ChatAction.UPLOAD_VIDEO)
    status = await message.reply_text("Видео получил. Делаю вертикальный формат и фон…")

    extension = _guess_extension(getattr(video, "file_name", None))
    job = create_video_job(settings.workdir, source_extension=extension, with_subtitles=True)

    try:
        telegram_file = await context.bot.get_file(video.file_id)
        await download_telegram_file(telegram_file, job.source_path)
    except BadRequest as exc:
        if _is_file_too_big_error(exc):
            await status.edit_text(_video_too_large_message(settings))
            return
        raise

    subtitle_path = (
        await asyncio.to_thread(subtitles.generate_srt, job.source_path, job.subtitles_path)
        if job.with_subtitles
        else None
    )
    try:
        await asyncio.to_thread(processor.render_vertical, job.source_path, job.output_path, subtitle_path)
    except FFmpegNotFoundError:
        await status.edit_text(FFMPEG_NOT_FOUND_MESSAGE)
        return

    await status.edit_text("Готово! Загружаю результат…")
    with job.output_path.open("rb") as result:
        await message.reply_video(video=result, caption="Готовый вертикальный ролик 9:16")
    await status.delete()


async def handle_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    LOGGER.exception("Unhandled Telegram update error", exc_info=context.error)


def _guess_extension(file_name: str | None) -> str:
    if not file_name or "." not in file_name:
        return ".mp4"
    return "." + file_name.rsplit(".", 1)[1].lower()


def _is_file_too_big_error(exc: BadRequest) -> bool:
    return FILE_TOO_BIG_TEXT in str(exc).lower()


def _video_too_large_message(settings: Settings) -> str:
    limit_mb = settings.effective_max_video_mb
    if settings.telegram_download_limit_mb < settings.max_video_mb:
        return (
            f"Видео слишком большое. Лимит для скачивания через Telegram Bot API: "
            f"{limit_mb} MB. Пришли файл поменьше или запусти бота через локальный "
            "Telegram Bot API server и увеличь TELEGRAM_DOWNLOAD_LIMIT_MB в config.py."
        )
    return f"Видео слишком большое. Лимит: {limit_mb} MB."
