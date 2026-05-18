from __future__ import annotations

import os
import subprocess
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QObject, QPointF, QRectF, QSize, Qt, QThread, Signal
from PySide6.QtGui import QColor, QDragEnterEvent, QDropEvent, QFont, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from video_editor_bot.config import PROJECT_ROOT, load_desktop_settings
from video_editor_bot.services.asr import build_subtitle_generator
from video_editor_bot.services.video_processor import (
    CHARACTER_HEIGHT_RATIO,
    CHARACTER_X_RATIO,
    FFmpegNotFoundError,
    FFmpegVideoProcessor,
    SUBTITLE_BOTTOM_MARGIN,
    VideoPreset,
)


VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
MIN_SUBTITLE_MARGIN = 24


@dataclass(frozen=True)
class ProcessingOptions:
    files: tuple[Path, ...]
    output_dir: Path
    vertical: bool
    subtitles: bool
    watermark: bool
    zoom: float
    watermark_path: Path | None
    watermark_x_ratio: float
    watermark_y_ratio: float
    watermark_height_ratio: float
    subtitle_bottom_margin: int

    def has_actions(self) -> bool:
        return self.vertical or self.subtitles or self.watermark


class DropZone(QLabel):
    files_dropped = Signal(list)

    def __init__(self, text: str) -> None:
        super().__init__(text)
        self.setAcceptDrops(True)
        self.setObjectName("dropZone")
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumHeight(92)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setProperty("active", True)
            self.style().unpolish(self)
            self.style().polish(self)

    def dragLeaveEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self.setProperty("active", False)
        self.style().unpolish(self)
        self.style().polish(self)
        event.accept()

    def dropEvent(self, event: QDropEvent) -> None:
        self.setProperty("active", False)
        self.style().unpolish(self)
        self.style().polish(self)
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]
        self.files_dropped.emit(paths)
        event.acceptProposedAction()


class FileListWidget(QListWidget):
    files_dropped = Signal(list)

    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)
        self.setSelectionMode(QListWidget.ExtendedSelection)
        self.setObjectName("fileList")

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        if event.mimeData().hasUrls():
            paths = [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]
            self.files_dropped.emit(paths)
            event.acceptProposedAction()
            return
        super().dropEvent(event)


class PreviewWidget(QWidget):
    def __init__(self, output_height: int) -> None:
        super().__init__()
        self.output_height = output_height
        self.watermark_enabled = False
        self.subtitles_enabled = False
        self.watermark_x_ratio = CHARACTER_X_RATIO
        self.watermark_y_ratio = 0.54
        self.watermark_height_ratio = CHARACTER_HEIGHT_RATIO
        self.subtitle_bottom_margin = SUBTITLE_BOTTOM_MARGIN
        self.drag_target: str | None = None
        self.drag_offset = QPointF(0, 0)
        self.setMinimumSize(220, 392)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setCursor(Qt.PointingHandCursor)

    def sizeHint(self) -> QSize:
        return QSize(280, 498)

    def set_watermark_enabled(self, enabled: bool) -> None:
        self.watermark_enabled = enabled
        self.update()

    def set_subtitles_enabled(self, enabled: bool) -> None:
        self.subtitles_enabled = enabled
        self.update()

    def set_watermark_scale(self, value: int) -> None:
        self.watermark_height_ratio = max(0.08, min(0.70, value / 100))
        self.update()

    def paintEvent(self, _event) -> None:  # type: ignore[no-untyped-def]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self._phone_rect().adjusted(0, 0, -1, -1)

        gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
        gradient.setColorAt(0, QColor("#111827"))
        gradient.setColorAt(0.55, QColor("#1f2937"))
        gradient.setColorAt(1, QColor("#0f172a"))
        painter.setBrush(gradient)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(rect, 22, 22)

        painter.setPen(QPen(QColor("#334155"), 1, Qt.DashLine))
        painter.drawRoundedRect(rect.adjusted(22, 22, -22, -22), 14, 14)

        painter.setPen(QColor("#94a3b8"))
        painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
        painter.drawText(rect.adjusted(0, 18, 0, 0), Qt.AlignHCenter | Qt.AlignTop, "9:16")

        if self.watermark_enabled:
            wm = self._watermark_rect()
            painter.setPen(QPen(QColor("#fed7aa"), 2))
            painter.setBrush(QColor("#f97316"))
            painter.drawRoundedRect(wm, 14, 14)
            painter.setPen(QColor("#111827"))
            painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
            painter.drawText(wm, Qt.AlignCenter, "GIF / PNG")

        if self.subtitles_enabled:
            sub = self._subtitle_rect()
            painter.setPen(QPen(QColor("#ffffff"), 1))
            painter.setBrush(QColor(0, 0, 0, 190))
            painter.drawRoundedRect(sub, 10, 10)
            painter.setPen(QColor("#ffffff"))
            painter.setFont(QFont("Segoe UI", 12, QFont.Bold))
            painter.drawText(sub, Qt.AlignCenter, "Текст титров")

        painter.end()

    def mousePressEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        position = event.position()
        if not self._phone_rect().contains(position):
            self.drag_target = None
            return
        if self.watermark_enabled and self._watermark_rect().contains(position):
            self.drag_target = "watermark"
            self.drag_offset = position - self._watermark_rect().topLeft()
            return
        if self.subtitles_enabled and self._subtitle_rect().contains(position):
            self.drag_target = "subtitles"
            self.drag_offset = position - self._subtitle_rect().topLeft()
            return
        self.drag_target = None

    def mouseMoveEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if not self.drag_target:
            return

        position = event.position()
        if self.drag_target == "watermark":
            wm = self._watermark_rect()
            phone = self._phone_rect()
            x = _clamp(position.x() - self.drag_offset.x(), phone.left(), phone.right() - wm.width())
            y = _clamp(position.y() - self.drag_offset.y(), phone.top(), phone.bottom() - wm.height())
            self.watermark_x_ratio = (x - phone.left()) / phone.width()
            self.watermark_y_ratio = (y - phone.top()) / phone.height()
            self.update()
            return

        if self.drag_target == "subtitles":
            sub = self._subtitle_rect()
            phone = self._phone_rect()
            y = _clamp(position.y() - self.drag_offset.y(), phone.top(), phone.bottom() - sub.height())
            margin = round((phone.bottom() - y - sub.height()) / phone.height() * self.output_height)
            max_margin = max(MIN_SUBTITLE_MARGIN, self.output_height - 180)
            self.subtitle_bottom_margin = int(_clamp(margin, MIN_SUBTITLE_MARGIN, max_margin))
            self.update()

    def mouseReleaseEvent(self, _event) -> None:  # type: ignore[no-untyped-def]
        self.drag_target = None

    def _watermark_rect(self):
        phone = self._phone_rect()
        height = phone.height() * self.watermark_height_ratio
        width = height * 0.78
        x = phone.left() + _clamp(phone.width() * self.watermark_x_ratio, 0, phone.width() - width)
        y = phone.top() + _clamp(phone.height() * self.watermark_y_ratio, 0, phone.height() - height)
        return QRectF(x, y, width, height)

    def _subtitle_rect(self):
        phone = self._phone_rect()
        height = max(38, phone.height() * 0.098)
        margin_px = self.subtitle_bottom_margin / self.output_height * phone.height()
        y = phone.top() + _clamp(phone.height() - margin_px - height, 0, phone.height() - height)
        return QRectF(phone.left() + 28, y, phone.width() - 56, height)

    def _phone_rect(self) -> QRectF:
        padding = 4
        available_width = max(1, self.width() - padding * 2)
        available_height = max(1, self.height() - padding * 2)
        phone_width = available_width
        phone_height = phone_width * 16 / 9
        if phone_height > available_height:
            phone_height = available_height
            phone_width = phone_height * 9 / 16
        x = (self.width() - phone_width) / 2
        y = (self.height() - phone_height) / 2
        return QRectF(x, y, phone_width, phone_height)


class ProcessingWorker(QObject):
    status = Signal(str)
    log = Signal(str)
    progress = Signal(int)
    done = Signal()
    error = Signal(str)

    def __init__(
        self,
        options: ProcessingOptions,
        workdir: Path,
        processor: FFmpegVideoProcessor,
        asr_provider: str,
        whisper_model: str,
    ) -> None:
        super().__init__()
        self.options = options
        self.workdir = workdir
        self.processor = processor
        self.asr_provider = asr_provider
        self.whisper_model = whisper_model

    def run(self) -> None:
        try:
            self.options.output_dir.mkdir(parents=True, exist_ok=True)
            subtitle_generator = (
                build_subtitle_generator(self.asr_provider, self.whisper_model)
                if self.options.subtitles
                else None
            )

            for index, source in enumerate(self.options.files, start=1):
                self.status.emit(f"Обработка {index}/{len(self.options.files)}: {source.name}")
                self.log.emit(f"Файл: {source}")
                destination = unique_output_path(self.options.output_dir, source)
                job_dir = self.workdir / uuid4().hex
                job_dir.mkdir(parents=True, exist_ok=True)
                subtitles_path = None

                if subtitle_generator is not None:
                    self.log.emit("Распознаю речь и создаю SRT...")
                    subtitles_path = subtitle_generator.generate_srt(source, job_dir / "subtitles.srt")
                    if subtitles_path is None:
                        raise RuntimeError("Распознавание речи отключено в настройках.")

                self.log.emit("Запускаю FFmpeg...")
                self.processor.render(
                    source,
                    destination,
                    subtitles=subtitles_path,
                    watermark=self.options.watermark_path,
                    vertical=self.options.vertical,
                    zoom=self.options.zoom,
                    watermark_x_ratio=self.options.watermark_x_ratio,
                    watermark_y_ratio=self.options.watermark_y_ratio,
                    watermark_height_ratio=self.options.watermark_height_ratio,
                    subtitle_bottom_margin=self.options.subtitle_bottom_margin,
                )
                self.log.emit(f"Готово: {destination}")
                self.progress.emit(index)

            self.done.emit()
        except FFmpegNotFoundError as exc:
            self.error.emit(f"FFmpeg не найден: {exc}")
        except subprocess.CalledProcessError as exc:
            self.error.emit(f"FFmpeg завершился с ошибкой. Команда: {exc.cmd}")
        except Exception as exc:  # pragma: no cover - GUI safety net
            self.error.emit(f"{exc}\n{traceback.format_exc()}")


class VideoEditorWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.settings = load_desktop_settings()
        self.workdir = _desktop_workdir(self.settings.workdir)
        self.processor = FFmpegVideoProcessor(
            VideoPreset(width=self.settings.output_width, height=self.settings.output_height)
        )
        self.files: list[Path] = []
        self.worker_thread: QThread | None = None
        self.worker: ProcessingWorker | None = None

        self.setWindowTitle("Video Editor")
        self.setMinimumSize(1120, 720)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(14)

        header = QHBoxLayout()
        title_group = QVBoxLayout()
        title = QLabel("Видеоредактор")
        title.setObjectName("title")
        subtitle = QLabel("Перетащите видео, настройте обработку и получите готовые MP4.")
        subtitle.setObjectName("subtitle")
        title_group.addWidget(title)
        title_group.addWidget(subtitle)
        header.addLayout(title_group, 1)
        brand = QLabel("by.Gavrs")
        brand.setObjectName("brand")
        brand.setAlignment(Qt.AlignCenter)
        header.addWidget(brand)
        root.addLayout(header)

        content = QHBoxLayout()
        content.setSpacing(14)
        root.addLayout(content, 1)

        files_card = self._card("Видео")
        files_layout = files_card.layout()
        self.drop_zone = DropZone("Перетащите видеофайлы сюда\nMP4, MOV, MKV, AVI, WEBM, M4V")
        self.drop_zone.files_dropped.connect(self._add_files)
        files_layout.addWidget(self.drop_zone)

        self.file_list = FileListWidget()
        self.file_list.files_dropped.connect(self._add_files)
        files_layout.addWidget(self.file_list, 1)

        file_buttons = QHBoxLayout()
        add_btn = QPushButton("Добавить")
        add_btn.clicked.connect(self._choose_files)
        remove_btn = QPushButton("Убрать")
        remove_btn.clicked.connect(self._remove_selected)
        clear_btn = QPushButton("Очистить")
        clear_btn.clicked.connect(self._clear_files)
        file_buttons.addWidget(add_btn)
        file_buttons.addWidget(remove_btn)
        file_buttons.addWidget(clear_btn)
        files_layout.addLayout(file_buttons)
        content.addWidget(files_card, 5)

        settings_card = self._card("Настройки")
        settings_layout = settings_card.layout()
        self.vertical_check = QCheckBox("Вертикальное видео 9:16 с размытым фоном")
        self.vertical_check.setChecked(True)
        settings_layout.addWidget(self.vertical_check)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(12)

        grid.addWidget(QLabel("Зум видео"), 0, 0)
        self.zoom_box = QComboBox()
        self.zoom_box.addItems(["1.00", "1.15", "1.30", "1.45"])
        self.zoom_box.setCurrentText("1.15")
        grid.addWidget(self.zoom_box, 0, 1)

        self.subtitles_check = QCheckBox("Автотитры")
        self.subtitles_check.toggled.connect(self._sync_preview)
        grid.addWidget(self.subtitles_check, 1, 0, 1, 2)

        self.watermark_check = QCheckBox("Водяной знак GIF/PNG")
        self.watermark_check.toggled.connect(self._sync_preview)
        grid.addWidget(self.watermark_check, 2, 0, 1, 2)

        grid.addWidget(QLabel("Файл знака"), 3, 0)
        self.watermark_path = QLineEdit(str(_default_watermark_path(self.settings.watermark_image_path)))
        grid.addWidget(self.watermark_path, 3, 1)
        watermark_btn = QPushButton("Обзор")
        watermark_btn.clicked.connect(self._choose_watermark)
        grid.addWidget(watermark_btn, 3, 2)

        grid.addWidget(QLabel("Размер знака"), 4, 0)
        self.watermark_scale = QSlider(Qt.Horizontal)
        self.watermark_scale.setRange(8, 70)
        self.watermark_scale.setValue(round(CHARACTER_HEIGHT_RATIO * 100))
        self.watermark_scale.valueChanged.connect(self.preview_scale_changed)
        grid.addWidget(self.watermark_scale, 4, 1, 1, 2)

        hint = QLabel("Положение знака и титров меняется перетаскиванием на макете.")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        grid.addWidget(hint, 5, 0, 1, 3)

        grid.addWidget(QLabel("Папка результата"), 6, 0)
        self.output_dir = QLineEdit(str(_default_output_dir()))
        grid.addWidget(self.output_dir, 6, 1)
        output_btn = QPushButton("Обзор")
        output_btn.clicked.connect(self._choose_output_dir)
        grid.addWidget(output_btn, 6, 2)
        settings_layout.addLayout(grid)

        self.process_btn = QPushButton("Обработать видео")
        self.process_btn.setObjectName("primaryButton")
        self.process_btn.clicked.connect(self._start_processing)
        settings_layout.addWidget(self.process_btn)

        open_output_btn = QPushButton("Открыть папку результата")
        open_output_btn.clicked.connect(self._open_output_dir)
        settings_layout.addWidget(open_output_btn)
        settings_layout.addStretch(1)
        content.addWidget(settings_card, 4)

        preview_card = self._card("Макет")
        preview_layout = preview_card.layout()
        self.preview = PreviewWidget(self.settings.output_height)
        preview_layout.addWidget(self.preview, 1)
        preview_note = QLabel("Перетащите оранжевый блок или титры в нужное место.")
        preview_note.setObjectName("hint")
        preview_note.setWordWrap(True)
        preview_layout.addWidget(preview_note)
        content.addWidget(preview_card, 3)

        bottom_card = QFrame()
        bottom_card.setObjectName("bottomCard")
        bottom_card.setMaximumHeight(150)
        bottom_layout = QVBoxLayout(bottom_card)
        bottom_layout.setContentsMargins(16, 14, 16, 16)
        bottom_layout.setSpacing(10)
        self.status_label = QLabel("Добавьте видеофайлы и выберите обработку.")
        self.status_label.setObjectName("status")
        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(82)
        self.log.setMaximumBlockCount(500)
        self.log.setPlaceholderText("Журнал обработки")
        bottom_layout.addWidget(self.status_label)
        bottom_layout.addWidget(self.progress)
        bottom_layout.addWidget(self.log, 1)
        root.addWidget(bottom_card)

        self._sync_preview()

    def _card(self, title: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName("card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        label = QLabel(title)
        label.setObjectName("cardTitle")
        layout.addWidget(label)
        return frame

    def preview_scale_changed(self, value: int) -> None:
        self.preview.set_watermark_scale(value)

    def _sync_preview(self) -> None:
        self.preview.set_watermark_enabled(self.watermark_check.isChecked())
        self.preview.set_subtitles_enabled(self.subtitles_check.isChecked())

    def _choose_files(self) -> None:
        selected, _ = QFileDialog.getOpenFileNames(
            self,
            "Выберите видео",
            "",
            "Видео (*.mp4 *.mov *.mkv *.avi *.webm *.m4v);;Все файлы (*.*)",
        )
        self._add_files([Path(path) for path in selected])

    def _choose_watermark(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите водяной знак",
            "",
            "Изображения и GIF (*.gif *.png *.jpg *.jpeg *.webp);;Все файлы (*.*)",
        )
        if selected:
            self.watermark_path.setText(selected)

    def _choose_output_dir(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "Выберите папку результата")
        if selected:
            self.output_dir.setText(selected)

    def _add_files(self, paths: list[Path]) -> None:
        added = 0
        known = {path.resolve() for path in self.files}
        for path in paths:
            if not path.is_file() or path.suffix.lower() not in VIDEO_EXTENSIONS:
                continue
            resolved = path.resolve()
            if resolved in known:
                continue
            self.files.append(resolved)
            known.add(resolved)
            item = QListWidgetItem(resolved.name)
            item.setToolTip(str(resolved))
            item.setData(Qt.UserRole, str(resolved))
            self.file_list.addItem(item)
            added += 1

        if added:
            self.status_label.setText(f"Добавлено файлов: {len(self.files)}.")
        else:
            self.status_label.setText("Поддерживаются MP4, MOV, MKV, AVI, WEBM и M4V.")

    def _remove_selected(self) -> None:
        rows = sorted((self.file_list.row(item) for item in self.file_list.selectedItems()), reverse=True)
        for row in rows:
            self.file_list.takeItem(row)
            del self.files[row]
        self.status_label.setText(f"Файлов в очереди: {len(self.files)}.")

    def _clear_files(self) -> None:
        self.files.clear()
        self.file_list.clear()
        self.status_label.setText("Очередь очищена.")

    def _read_options(self) -> ProcessingOptions:
        if not self.files:
            raise ValueError("Добавьте хотя бы один видеофайл.")

        watermark = self.watermark_check.isChecked()
        watermark_path = Path(self.watermark_path.text()).expanduser() if watermark else None
        options = ProcessingOptions(
            files=tuple(self.files),
            output_dir=Path(self.output_dir.text()).expanduser(),
            vertical=self.vertical_check.isChecked(),
            subtitles=self.subtitles_check.isChecked(),
            watermark=watermark,
            zoom=float(self.zoom_box.currentText()),
            watermark_path=watermark_path,
            watermark_x_ratio=self.preview.watermark_x_ratio,
            watermark_y_ratio=self.preview.watermark_y_ratio,
            watermark_height_ratio=self.preview.watermark_height_ratio,
            subtitle_bottom_margin=self.preview.subtitle_bottom_margin,
        )
        if not options.has_actions():
            raise ValueError("Выберите хотя бы один тип обработки.")
        if watermark and (watermark_path is None or not watermark_path.exists()):
            raise ValueError("Файл водяного знака не найден.")
        return options

    def _start_processing(self) -> None:
        if self.worker_thread and self.worker_thread.isRunning():
            return

        try:
            options = self._read_options()
        except ValueError as exc:
            QMessageBox.warning(self, "Проверьте настройки", str(exc))
            return

        self.process_btn.setEnabled(False)
        self.progress.setRange(0, len(options.files))
        self.progress.setValue(0)
        self._append_log("Старт обработки.")

        self.worker_thread = QThread()
        self.worker = ProcessingWorker(
            options,
            self.workdir,
            self.processor,
            self.settings.asr_provider,
            self.settings.whisper_model,
        )
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.status.connect(self.status_label.setText)
        self.worker.log.connect(self._append_log)
        self.worker.progress.connect(self.progress.setValue)
        self.worker.done.connect(self._processing_done)
        self.worker.error.connect(self._processing_error)
        self.worker.done.connect(self.worker_thread.quit)
        self.worker.error.connect(self.worker_thread.quit)
        self.worker_thread.finished.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)
        self.worker_thread.finished.connect(self._thread_finished)
        self.worker_thread.start()

    def _processing_done(self) -> None:
        self.status_label.setText("Готово. Результаты лежат в выбранной папке.")
        self._append_log("Обработка завершена.")
        self.process_btn.setEnabled(True)

    def _processing_error(self, text: str) -> None:
        self.status_label.setText("Ошибка обработки.")
        self._append_log(text)
        self.process_btn.setEnabled(True)
        QMessageBox.critical(self, "Ошибка обработки", text)

    def _thread_finished(self) -> None:
        self.worker_thread = None
        self.worker = None

    def _append_log(self, text: str) -> None:
        self.log.appendPlainText(text)

    def _open_output_dir(self) -> None:
        path = Path(self.output_dir.text()).expanduser()
        path.mkdir(parents=True, exist_ok=True)
        os.startfile(path)  # type: ignore[attr-defined]


def unique_output_path(output_dir: Path, source: Path) -> Path:
    base = output_dir / f"{source.stem}_edited.mp4"
    if not base.exists():
        return base

    counter = 2
    while True:
        candidate = output_dir / f"{source.stem}_edited_{counter}.mp4"
        if not candidate.exists():
            return candidate
        counter += 1


def _default_watermark_path(configured_path: Path) -> Path:
    if configured_path.exists():
        return configured_path

    bundled_root = getattr(sys, "_MEIPASS", None)
    if bundled_root:
        bundled_path = Path(bundled_root) / "assets" / "meow-zhe.gif"
        if bundled_path.exists():
            return bundled_path

    return configured_path


def _default_output_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path.home() / "Videos" / "Video Editor"
    return PROJECT_ROOT / "output"


def _desktop_workdir(configured_path: Path) -> Path:
    if getattr(sys, "frozen", False):
        local_app_data = os.getenv("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "VideoEditor" / "workdir"
        return Path.home() / "AppData" / "Local" / "VideoEditor" / "workdir"

    if configured_path.is_absolute():
        return configured_path
    return PROJECT_ROOT / configured_path


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


APP_QSS = """
QWidget {
    background: #f6f8fb;
    color: #172033;
    font-family: "Segoe UI Variable", "Inter", "Segoe UI";
    font-size: 10pt;
}
QLabel#title {
    font-size: 27px;
    font-weight: 800;
    color: #121826;
}
QLabel#subtitle, QLabel#hint {
    color: #667085;
}
QLabel#brand {
    color: #1d4ed8;
    background: #eaf1ff;
    border: 1px solid #c7d9ff;
    border-radius: 16px;
    padding: 8px 14px;
    font-weight: 800;
}
QFrame#card, QFrame#bottomCard {
    background: #ffffff;
    border: 1px solid #e0e6ef;
    border-radius: 16px;
}
QLabel#cardTitle {
    color: #121826;
    font-size: 15px;
    font-weight: 800;
    background: transparent;
}
QLabel#status {
    color: #334155;
    background: transparent;
}
QLabel#dropZone {
    background: #f9fbff;
    color: #475569;
    border: 2px dashed #c2ccda;
    border-radius: 16px;
    padding: 14px;
    font-weight: 700;
}
QLabel#dropZone[active="true"] {
    background: #eff6ff;
    border-color: #2563eb;
    color: #1d4ed8;
}
QListWidget, QPlainTextEdit, QLineEdit, QComboBox {
    background: #fbfcff;
    border: 1px solid #d7deea;
    border-radius: 10px;
    padding: 7px;
    selection-background-color: #dbeafe;
    selection-color: #0f172a;
}
QListWidget::item {
    border-radius: 9px;
    padding: 8px;
    margin: 2px;
}
QListWidget::item:selected {
    background: #dbeafe;
}
QPushButton {
    background: #ffffff;
    border: 1px solid #d0d7e2;
    border-radius: 10px;
    padding: 9px 13px;
    font-weight: 700;
}
QPushButton:hover {
    background: #f8fafc;
    border-color: #94a3b8;
}
QPushButton:pressed {
    background: #e2e8f0;
}
QPushButton#primaryButton {
    background: #2563eb;
    color: white;
    border-color: #1d4ed8;
    padding: 12px 16px;
}
QPushButton#primaryButton:hover {
    background: #1d4ed8;
}
QPushButton:disabled {
    color: #94a3b8;
    background: #f1f5f9;
}
QCheckBox {
    background: transparent;
    spacing: 9px;
    font-weight: 600;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 5px;
    border: 1px solid #aeb9c9;
    background: #ffffff;
}
QCheckBox::indicator:checked {
    border: 2px solid #2563eb;
    background: qradialgradient(cx:0.5, cy:0.5, radius:0.55, fx:0.5, fy:0.5, stop:0 #2563eb, stop:0.42 #2563eb, stop:0.46 #ffffff, stop:1 #ffffff);
}
QSlider::groove:horizontal {
    height: 8px;
    border-radius: 4px;
    background: #dbe4ef;
}
QSlider::sub-page:horizontal {
    background: #2563eb;
    border-radius: 4px;
}
QSlider::handle:horizontal {
    width: 18px;
    height: 18px;
    margin: -6px 0;
    border-radius: 9px;
    background: #ffffff;
    border: 2px solid #2563eb;
}
QProgressBar {
    background: #e8eef6;
    border: none;
    border-radius: 8px;
    height: 10px;
}
QProgressBar::chunk {
    background: #2563eb;
    border-radius: 8px;
}
"""


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_QSS)
    window = VideoEditorWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
