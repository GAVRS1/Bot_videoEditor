from __future__ import annotations

import asyncio
import logging
import subprocess
from dataclasses import dataclass

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.error import BadRequest
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from video_editor_bot.config import Settings
from video_editor_bot.services.asr import build_subtitle_generator
from video_editor_bot.services.jobs import VideoJob, create_video_job
from video_editor_bot.services.video_processor import FFmpegNotFoundError, FFmpegVideoProcessor, VideoPreset
from video_editor_bot.storage import download_telegram_file, get_video_from_message


LOGGER = logging.getLogger(__name__)
PENDING_JOBS_KEY = "pending_video_jobs"
EDIT_STATES_KEY = "video_edit_states"

START_TEXT = """
Привет! Пришли мне видео, а я предложу выбрать обработку:

- титры;
- вертикальный формат 9:16;
- водяной знак.

Можно выбрать сразу несколько вариантов и обработать видео один раз.
""".strip()


FILE_TOO_BIG_TEXT = "file is too big"
FFMPEG_NOT_FOUND_MESSAGE = (
    "Не найден FFmpeg. Установи FFmpeg и добавь ffmpeg.exe в PATH, "
    "затем перезапусти бота."
)


@dataclass
class EditState:
    subtitles: bool = False
    vertical: bool = False
    watermark: bool = False
    zoom: float = 1.15

    def has_actions(self) -> bool:
        return self.subtitles or self.vertical or self.watermark


def build_application(settings: Settings) -> Application:
    processor = FFmpegVideoProcessor(
        VideoPreset(width=settings.output_width, height=settings.output_height)
    )
    subtitles = build_subtitle_generator(settings.asr_provider, settings.whisper_model)

    application = Application.builder().token(settings.telegram_bot_token).build()
    application.bot_data["settings"] = settings
    application.bot_data["processor"] = processor
    application.bot_data["subtitles"] = subtitles
    application.bot_data[PENDING_JOBS_KEY] = {}
    application.bot_data[EDIT_STATES_KEY] = {}

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", start))
    application.add_handler(CallbackQueryHandler(handle_action))
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

    file_size = getattr(video, "file_size", None)
    if file_size and file_size > settings.effective_max_video_bytes:
        await message.reply_text(_video_too_large_message(settings))
        return

    await message.chat.send_action(ChatAction.UPLOAD_VIDEO)
    status = await message.reply_text("Видео получил. Скачиваю файл...")

    extension = _guess_extension(getattr(video, "file_name", None))
    job = create_video_job(settings.workdir, source_extension=extension, with_subtitles=False)

    try:
        telegram_file = await context.bot.get_file(video.file_id)
        await download_telegram_file(telegram_file, job.source_path)
    except BadRequest as exc:
        if _is_file_too_big_error(exc):
            await status.edit_text(_video_too_large_message(settings))
            return
        raise

    _pending_jobs(context)[job.job_id] = job
    _edit_states(context)[job.job_id] = EditState()
    await status.edit_text(_selection_text(_edit_states(context)[job.job_id]), reply_markup=_edit_keyboard(job.job_id, _edit_states(context)[job.job_id]))


async def handle_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None or query.message is None or query.data is None:
        return

    await query.answer()
    parts = query.data.split(":")
    if len(parts) < 2:
        return

    command = parts[0]
    job_id = parts[-1]
    job = _pending_jobs(context).get(job_id)
    state = _edit_states(context).get(job_id)
    if job is None or state is None:
        await query.edit_message_text("Видео уже обработано или бот был перезапущен. Пришлите файл заново.")
        return

    if command == "toggle" and len(parts) == 3:
        _toggle_state(state, parts[1])
        await query.edit_message_text(_selection_text(state), reply_markup=_edit_keyboard(job_id, state))
        return

    if command == "zoom" and len(parts) == 3:
        state.vertical = True
        state.zoom = float(parts[1])
        await query.edit_message_text(_selection_text(state), reply_markup=_edit_keyboard(job_id, state))
        return

    if command == "process":
        await _process_job(query, context, job, state)


async def _process_job(query, context: ContextTypes.DEFAULT_TYPE, job: VideoJob, state: EditState) -> None:
    if not state.has_actions():
        await query.edit_message_text(_selection_text(state, warning="Выберите хотя бы один вариант."), reply_markup=_edit_keyboard(job.job_id, state))
        return

    settings: Settings = context.application.bot_data["settings"]
    processor: FFmpegVideoProcessor = context.application.bot_data["processor"]
    subtitles = context.application.bot_data["subtitles"]

    await query.edit_message_text(_processing_text(state))
    await query.message.chat.send_action(ChatAction.UPLOAD_VIDEO)

    subtitle_path = None
    watermark_path = None
    try:
        if state.subtitles:
            subtitle_path = await asyncio.to_thread(subtitles.generate_srt, job.source_path, job.subtitles_path)
            if subtitle_path is None:
                await query.edit_message_text(
                    'Титры не добавлены: в config.py включите ASR_PROVIDER = "faster-whisper".'
                )
                return

        if state.watermark:
            if not settings.watermark_image_path.exists():
                await query.edit_message_text(f"Не найден файл водяного знака: {settings.watermark_image_path}")
                return
            watermark_path = settings.watermark_image_path

        await asyncio.to_thread(
            processor.render,
            job.source_path,
            job.output_path,
            subtitles=subtitle_path,
            watermark=watermark_path,
            vertical=state.vertical,
            zoom=state.zoom,
        )
    except FFmpegNotFoundError:
        await query.edit_message_text(FFMPEG_NOT_FOUND_MESSAGE)
        return
    except subprocess.CalledProcessError:
        LOGGER.exception("FFmpeg failed while processing video job %s", job.job_id)
        await query.edit_message_text("FFmpeg не смог обработать видео. Ошибка записана в лог.")
        return

    _pending_jobs(context).pop(job.job_id, None)
    _edit_states(context).pop(job.job_id, None)
    await query.edit_message_text("Готово! Загружаю результат...")
    with job.output_path.open("rb") as result:
        await query.message.reply_video(video=result, caption=_result_caption(state))
    await query.message.delete()


async def handle_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    LOGGER.exception("Unhandled Telegram update error", exc_info=context.error)


def _edit_keyboard(job_id: str, state: EditState) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(_check_label("Вертикальное видео 9:16", state.vertical), callback_data=f"toggle:vertical:{job_id}")],
            [
                InlineKeyboardButton(_zoom_label("Зум 1.00", state.zoom, 1.00), callback_data=f"zoom:1.00:{job_id}"),
                InlineKeyboardButton(_zoom_label("1.15", state.zoom, 1.15), callback_data=f"zoom:1.15:{job_id}"),
                InlineKeyboardButton(_zoom_label("1.30", state.zoom, 1.30), callback_data=f"zoom:1.30:{job_id}"),
                InlineKeyboardButton(_zoom_label("1.45", state.zoom, 1.45), callback_data=f"zoom:1.45:{job_id}"),
            ],
            [InlineKeyboardButton(_check_label("Титры", state.subtitles), callback_data=f"toggle:subtitles:{job_id}")],
            [InlineKeyboardButton(_check_label("Водяной знак", state.watermark), callback_data=f"toggle:watermark:{job_id}")],
            [InlineKeyboardButton("Обработать видео", callback_data=f"process:{job_id}")],
        ]
    )


def _pending_jobs(context: ContextTypes.DEFAULT_TYPE) -> dict[str, VideoJob]:
    return context.application.bot_data.setdefault(PENDING_JOBS_KEY, {})


def _edit_states(context: ContextTypes.DEFAULT_TYPE) -> dict[str, EditState]:
    return context.application.bot_data.setdefault(EDIT_STATES_KEY, {})


def _toggle_state(state: EditState, action: str) -> None:
    if action == "subtitles":
        state.subtitles = not state.subtitles
    elif action == "vertical":
        state.vertical = not state.vertical
    elif action == "watermark":
        state.watermark = not state.watermark


def _check_label(text: str, enabled: bool) -> str:
    return f"{'✓' if enabled else '☐'} {text}"


def _zoom_label(text: str, current: float, value: float) -> str:
    return f"{'✓ ' if abs(current - value) < 0.001 else ''}{text}"


def _selection_text(state: EditState, warning: str | None = None) -> str:
    selected = []
    if state.vertical:
        selected.append(f"вертикальное видео, зум {state.zoom:.2f}")
    if state.subtitles:
        selected.append("титры")
    if state.watermark:
        selected.append("водяной знак")

    text = "Выберите один или несколько вариантов и нажмите «Обработать видео»."
    if selected:
        text += "\n\nСейчас выбрано: " + ", ".join(selected) + "."
    if warning:
        text += f"\n\n{warning}"
    return text


def _processing_text(state: EditState) -> str:
    parts = []
    if state.vertical:
        parts.append("вертикальный формат")
    if state.subtitles:
        parts.append("титры")
    if state.watermark:
        parts.append("водяной знак")
    return "Обрабатываю видео: " + ", ".join(parts) + "..."


def _result_caption(state: EditState) -> str:
    parts = []
    if state.vertical:
        parts.append("вертикальное видео")
    if state.subtitles:
        parts.append("титры")
    if state.watermark:
        parts.append("водяной знак")
    return "Готово: " + ", ".join(parts)


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
            f"{limit_mb} MB. Пришлите файл поменьше или запустите бота через локальный "
            "Telegram Bot API server и увеличьте TELEGRAM_DOWNLOAD_LIMIT_MB в config.py."
        )
    return f"Видео слишком большое. Лимит: {limit_mb} MB."
