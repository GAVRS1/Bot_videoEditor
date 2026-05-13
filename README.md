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
- `config.py` — все лимиты, пути и токены через переменные окружения.

## Возможности MVP

- Принимает видео из Telegram.
- Делает вертикальный формат `1080x1920`.
- На фоне использует масштабированную и размытую копию ролика, чтобы не было чёрных полос.
- Опционально генерирует `.srt` через `faster-whisper` и прожигает субтитры через FFmpeg.
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
set TELEGRAM_BOT_TOKEN=123456:telegram-token
run_project.bat
```

`install_dependencies.bat` создаёт виртуальное окружение `.venv` и устанавливает зависимости из `requirements.txt`.
`run_project.bat` активирует окружение и запускает бота через `python -m video_editor_bot.main`.

### Linux/macOS

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN='123456:telegram-token'
python -m video_editor_bot.main
```

Для разработки можно установить дополнительные зависимости из `pyproject.toml`:

```bash
pip install -e '.[dev]'
```

С субтитрами:

```bash
pip install -e '.[asr,dev]'
export TELEGRAM_BOT_TOKEN='123456:telegram-token'
export ASR_PROVIDER='faster-whisper'
export WHISPER_MODEL='small'
video-editor-bot
```

## Настройки окружения

| Переменная | По умолчанию | Описание |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | обязательно | Токен Telegram-бота |
| `WORKDIR` | `/tmp/video-editor-bot` | Папка временных файлов |
| `MAX_VIDEO_MB` | `50` | Лимит входного файла |
| `OUTPUT_WIDTH` | `1080` | Ширина вертикального видео |
| `OUTPUT_HEIGHT` | `1920` | Высота вертикального видео |
| `ASR_PROVIDER` | `disabled` | `disabled` или `faster-whisper` |
| `WHISPER_MODEL` | `base` | Модель faster-whisper |

## Масштабирование

Для реальной нагрузки лучше вынести обработку из Telegram-процесса:

1. Bot API процесс быстро принимает файл и создаёт job.
2. Redis/RabbitMQ хранит очередь.
3. Worker с CPU/GPU запускает FFmpeg и ASR.
4. Готовый файл складывается в S3/MinIO или локальное хранилище.
5. Бот отправляет пользователю результат.

Такой подход нужен, потому что FFmpeg и Whisper могут обрабатывать даже короткие ролики десятки секунд, а Telegram webhook/polling не должен блокироваться тяжёлыми задачами.
