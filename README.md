# Bot videoEditor

Да, такого Telegram-бота реально сделать: бот принимает видео, отправляет его в очередь обработки, FFmpeg собирает вертикальный ролик 9:16 с размытым фоном, а ASR-модуль может автоматически подготовить субтитры и прожечь их поверх видео.

## Архитектура

```text
Telegram Bot API
      |
      v
bot.py                    Приём видео, выбор пресета, отправка результата
      |
      v
services/jobs.py            Задание обработки и рабочая директория
      |
      v
services/video_processor.py FFmpeg: 9:16, blur background, optional subtitles
      |
      v
services/asr.py             Интерфейс ASR; сейчас faster-whisper как опция
      |
      v
storage.py                  Скачивание/выдача файлов через Telegram
```

### Почему модули разделены так

- `bot.py` — только Telegram-сценарии и UX, без FFmpeg-логики.
- `services/video_processor.py` — чистая видеообработка, которую можно тестировать отдельно.
- `services/asr.py` — распознавание речи заменяемо: можно подключить OpenAI Whisper API, локальный `faster-whisper`, Vosk или выключить субтитры.
- `services/jobs.py` — единый объект задачи, чтобы позже добавить Redis/RQ/Celery и не переписывать обработчик Telegram.
- `config.py` — единственное место настройки проекта: токен, пути, лимиты, размер видео и ASR.

## Возможности MVP

- Принимает видео из Telegram.
- Делает вертикальный формат `1080x1920`.
- На фоне использует масштабированную и размытую копию ролика, чтобы не было чёрных полос.
- Опционально генерирует `.srt` через `faster-whisper` и прожигает субтитры через FFmpeg, если это включено в `config.py`.
- Возвращает готовый MP4 пользователю.

## Требования

- Python 3.11+
- `ffmpeg` в PATH
- Telegram bot token от `@BotFather`
- Для локальных автосубтитров: `pip install -e '.[asr]'`

## Быстрый старт

### Windows

```bat
install_dependencies.bat
```

После установки откройте `src\video_editor_bot\config.py`, замените `PASTE_TELEGRAM_BOT_TOKEN_HERE` на токен от `@BotFather` и запустите:

```bat
run_project.bat
```

`install_dependencies.bat` создаёт виртуальное окружение `.venv` и устанавливает зависимости из `requirements.txt`.
`run_project.bat` активирует окружение и запускает бота через `python -m video_editor_bot.main`. Если запуск завершается ошибкой, окно консоли останется открытым и покажет причину.

### Linux/macOS

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# Затем настройте src/video_editor_bot/config.py
python -m video_editor_bot.main
```

Для разработки можно установить дополнительные зависимости из `pyproject.toml`:

```bash
pip install -e '.[dev]'
```

С субтитрами:

```bash
pip install -e '.[asr,dev]'
# В src/video_editor_bot/config.py задайте:
# ASR_PROVIDER = "faster-whisper"
# WHISPER_MODEL = "small"
video-editor-bot
```

## Настройки проекта

Все настройки проекта находятся только в `src/video_editor_bot/config.py`. Не нужно задавать переменные окружения или править `.bat`-файлы.

| Настройка | По умолчанию | Описание |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | `PASTE_TELEGRAM_BOT_TOKEN_HERE` | Токен Telegram-бота от `@BotFather`; обязательно замените перед запуском |
| `WORKDIR` | `workdir` | Папка временных файлов |
| `MAX_VIDEO_MB` | `50` | Проектный лимит входного файла |
| `TELEGRAM_DOWNLOAD_LIMIT_MB` | `20` | Лимит скачивания файла через Telegram Bot API; для облачного Bot API оставьте 20 MB, для локального Bot API server можно увеличить вместе с `MAX_VIDEO_MB` |
| `OUTPUT_WIDTH` | `1080` | Ширина вертикального видео |
| `OUTPUT_HEIGHT` | `1920` | Высота вертикального видео |
| `ASR_PROVIDER` | `disabled` | `disabled` или `faster-whisper` |
| `WHISPER_MODEL` | `base` | Модель faster-whisper |

> ⚠️ Если пользователь отправит файл больше лимита скачивания Telegram Bot API, Telegram вернёт `File is too big`. Бот теперь заранее проверяет размер, если Telegram передал `file_size`, а также аккуратно показывает пользователю понятное сообщение, если ошибка пришла уже на этапе `get_file`.


## Устранение ошибок

### `FileNotFoundError: [WinError 2]` при обработке видео

Эта ошибка означает, что Windows не нашла `ffmpeg.exe` при запуске команды обработки. Установите FFmpeg, добавьте папку с `ffmpeg.exe` в системную переменную `PATH`, затем полностью закройте и заново запустите окно терминала и бота.

Проверить установку можно командой:

```bat
where ffmpeg
ffmpeg -version
```

Если FFmpeg всё ещё не находится, повторно запустите `install_dependencies.bat`: он покажет предупреждение, когда `ffmpeg` отсутствует в `PATH`.

## Масштабирование

Для реальной нагрузки лучше вынести обработку из Telegram-процесса:

1. Bot API процесс быстро принимает файл и создаёт job.
2. Redis/RabbitMQ хранит очередь.
3. Worker с CPU/GPU запускает FFmpeg и ASR.
4. Готовый файл складывается в S3/MinIO или локальное хранилище.
5. Бот отправляет пользователю результат.

Такой подход нужен, потому что FFmpeg и Whisper могут обрабатывать даже короткие ролики десятки секунд, а Telegram webhook/polling не должен блокироваться тяжёлыми задачами.
