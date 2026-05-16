from __future__ import annotations

import re
from dataclasses import dataclass
from importlib import import_module, util
from pathlib import Path
from typing import Protocol


MAX_CAPTION_WORDS = 6
MAX_CAPTION_CHARS = 42
MAX_CAPTION_SECONDS = 3.2
MIN_CAPTION_SECONDS = 0.6


class SubtitleGenerator(Protocol):
    def generate_srt(self, video_path: Path, subtitles_path: Path) -> Path | None:
        """Generate subtitles for a video and return the SRT path, or None if disabled."""


@dataclass(frozen=True)
class DisabledSubtitleGenerator:
    def generate_srt(self, video_path: Path, subtitles_path: Path) -> Path | None:
        return None


@dataclass(frozen=True)
class FasterWhisperSubtitleGenerator:
    model_name: str = "base"
    language: str = "ru"

    def generate_srt(self, video_path: Path, subtitles_path: Path) -> Path | None:
        if util.find_spec("faster_whisper") is None:
            raise RuntimeError(
                "ASR_PROVIDER=faster-whisper requires optional dependency: pip install -e '.[asr]'"
            )

        faster_whisper = import_module("faster_whisper")
        model = faster_whisper.WhisperModel(self.model_name, device="cpu", compute_type="int8")
        segments, _info = model.transcribe(
            str(video_path),
            language=self.language,
            task="transcribe",
            vad_filter=True,
            word_timestamps=True,
            beam_size=5,
            condition_on_previous_text=False,
        )

        with subtitles_path.open("w", encoding="utf-8") as file:
            captions = _build_captions(segments)
            for index, caption in enumerate(captions, start=1):
                file.write(f"{index}\n")
                file.write(f"{_format_srt_time(caption.start)} --> {_format_srt_time(caption.end)}\n")
                file.write(f"{caption.text}\n\n")

        return subtitles_path


def build_subtitle_generator(provider: str, model_name: str) -> SubtitleGenerator:
    if provider == "disabled":
        return DisabledSubtitleGenerator()
    if provider == "faster-whisper":
        return FasterWhisperSubtitleGenerator(model_name=model_name)
    raise ValueError(f"Unsupported ASR_PROVIDER: {provider}")


@dataclass(frozen=True)
class SubtitleWord:
    text: str
    start: float
    end: float


@dataclass(frozen=True)
class SubtitleCaption:
    text: str
    start: float
    end: float


def _build_captions(segments) -> list[SubtitleCaption]:
    captions: list[SubtitleCaption] = []
    for segment in segments:
        words = _segment_words(segment)
        if not words:
            text = _clean_text(getattr(segment, "text", ""))
            if text:
                captions.append(SubtitleCaption(text, segment.start, segment.end))
            continue

        captions.extend(_split_words_into_captions(words))
    return captions


def _segment_words(segment) -> list[SubtitleWord]:
    raw_words = getattr(segment, "words", None) or []
    words: list[SubtitleWord] = []
    for raw_word in raw_words:
        text = _clean_text(getattr(raw_word, "word", ""))
        start = getattr(raw_word, "start", None)
        end = getattr(raw_word, "end", None)
        if not text or start is None or end is None:
            continue
        words.append(SubtitleWord(text=text, start=float(start), end=float(end)))
    return words


def _split_words_into_captions(words: list[SubtitleWord]) -> list[SubtitleCaption]:
    captions: list[SubtitleCaption] = []
    current: list[SubtitleWord] = []

    for word in words:
        candidate = [*current, word]
        if current and _should_flush_caption(candidate):
            captions.append(_caption_from_words(current))
            current = [word]
        else:
            current = candidate

        if _ends_sentence(word.text):
            captions.append(_caption_from_words(current))
            current = []

    if current:
        captions.append(_caption_from_words(current))
    return captions


def _should_flush_caption(words: list[SubtitleWord]) -> bool:
    text = _join_words(words)
    duration = words[-1].end - words[0].start
    return (
        len(words) > MAX_CAPTION_WORDS
        or len(text) > MAX_CAPTION_CHARS
        or duration > MAX_CAPTION_SECONDS
    )


def _caption_from_words(words: list[SubtitleWord]) -> SubtitleCaption:
    start = words[0].start
    end = max(words[-1].end, start + MIN_CAPTION_SECONDS)
    return SubtitleCaption(_join_words(words), start, end)


def _join_words(words: list[SubtitleWord]) -> str:
    return _clean_text(" ".join(word.text for word in words))


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _ends_sentence(text: str) -> bool:
    return text.endswith((".", "!", "?", "…"))


def _format_srt_time(seconds: float) -> str:
    milliseconds = int(round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"
