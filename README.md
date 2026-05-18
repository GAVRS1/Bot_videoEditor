# Video Editor

Desktop-приложение для Windows, которое готовит ролики под Shorts, Reels, TikTok и VK Клипы. Пользователь открывает окно, перетаскивает видеофайлы, выбирает обработку и получает готовые MP4 в выбранной папке.

## Возможности

- drag-and-drop видеофайлов в окно приложения;
- пакетная обработка нескольких роликов;
- вертикальный формат 9:16 с размытым фоном;
- настраиваемый zoom центрального видео;
- автотитры через `faster-whisper`;
- GIF/PNG/JPG-водяной знак;
- интерактивный макет для положения водяного знака и титров;
- сборка в `VideoEditor.exe`;
- сборка Windows-установщика через Inno Setup 6.

## Быстрый запуск из исходников

1. Установите Python 3.11 или новее.
2. Установите зависимости:

```bat
install_dependencies.bat
```

3. Запустите приложение:

```bat
run_app.bat
```

## Сборка EXE

```bat
build_exe.bat
```

После сборки приложение появится здесь:

```text
dist\VideoEditor\VideoEditor.exe
```

Сборка делается в формате `onedir`, потому что видеозависимости, FFmpeg и модели распознавания речи довольно тяжелые. Такой вариант обычно стабильнее одного огромного `onefile`.

## Сборка установщика

1. Соберите EXE:

```bat
build_exe.bat
```

2. Установите Inno Setup 6: https://jrsoftware.org/isinfo.php
3. Запустите:

```bat
build_installer.bat
```

Готовый установщик появится в папке:

```text
installer_output
```

## Настройки

Основные настройки лежат в `src/video_editor_bot/config.py`:

| Настройка | Описание |
| --- | --- |
| `WORKDIR` | временные файлы обработки |
| `MAX_VIDEO_MB` | максимальный размер исходного видео |
| `OUTPUT_WIDTH`, `OUTPUT_HEIGHT` | размер вертикального видео |
| `WATERMARK_IMAGE_PATH` | водяной знак по умолчанию |
| `ASR_PROVIDER` | `faster-whisper` или `disabled` |
| `WHISPER_MODEL` | модель Whisper |

## Архитектура

```text
gui.py                       desktop-окно, drag-and-drop, очередь файлов
services/video_processor.py  FFmpeg: вертикаль, титры, водяной знак
services/asr.py              faster-whisper и генерация SRT
services/jobs.py             временные пути для обработки
config.py                    общие настройки
installer/VideoEditor.iss    сценарий Inno Setup
```

## Тесты

```bat
python -m pytest
```
