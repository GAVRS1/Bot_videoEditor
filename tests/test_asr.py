from dataclasses import dataclass

from video_editor_bot.services.asr import (
    SubtitleWord,
    _build_captions,
    _format_srt_time,
    _split_words_into_captions,
)


@dataclass(frozen=True)
class FakeSegment:
    text: str
    start: float
    end: float
    words: list[SubtitleWord] | None = None


def test_format_srt_time() -> None:
    assert _format_srt_time(0) == "00:00:00,000"
    assert _format_srt_time(65.432) == "00:01:05,432"
    assert _format_srt_time(3661.9) == "01:01:01,900"


def test_split_words_into_short_dialogue_captions() -> None:
    words = [
        SubtitleWord("Привет,", 0.0, 0.2),
        SubtitleWord("как", 0.2, 0.4),
        SubtitleWord("твои", 0.4, 0.7),
        SubtitleWord("дела?", 0.7, 1.0),
        SubtitleWord("Я", 1.2, 1.4),
        SubtitleWord("скоро", 1.4, 1.7),
        SubtitleWord("вернусь.", 1.7, 2.0),
    ]

    captions = _split_words_into_captions(words)

    assert [caption.text for caption in captions] == [
        "Привет, как твои дела?",
        "Я скоро вернусь.",
    ]
    assert captions[0].start == 0.0
    assert captions[0].end == 1.0


def test_build_captions_falls_back_to_segment_timestamps_without_words() -> None:
    captions = _build_captions([FakeSegment("  обычный текст  ", 2.0, 4.0)])

    assert len(captions) == 1
    assert captions[0].text == "обычный текст"
    assert captions[0].start == 2.0
    assert captions[0].end == 4.0
