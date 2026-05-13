import asyncio

from video_editor_bot.main import ensure_event_loop


def test_ensure_event_loop_creates_loop_when_missing(monkeypatch) -> None:
    created_loop = object()
    calls = []

    def raise_no_current_loop():
        raise RuntimeError("There is no current event loop in thread 'MainThread'.")

    monkeypatch.setattr(asyncio, "get_event_loop", raise_no_current_loop)
    monkeypatch.setattr(asyncio, "new_event_loop", lambda: created_loop)
    monkeypatch.setattr(asyncio, "set_event_loop", calls.append)

    ensure_event_loop()

    assert calls == [created_loop]


def test_ensure_event_loop_replaces_closed_loop(monkeypatch) -> None:
    existing_loop = asyncio.new_event_loop()
    replacement_loop = object()
    calls = []

    existing_loop.close()
    monkeypatch.setattr(asyncio, "get_event_loop", lambda: existing_loop)
    monkeypatch.setattr(asyncio, "new_event_loop", lambda: replacement_loop)
    monkeypatch.setattr(asyncio, "set_event_loop", calls.append)

    ensure_event_loop()

    assert calls == [replacement_loop]


def test_ensure_event_loop_keeps_open_loop(monkeypatch) -> None:
    existing_loop = asyncio.new_event_loop()
    calls = []

    monkeypatch.setattr(asyncio, "get_event_loop", lambda: existing_loop)
    monkeypatch.setattr(asyncio, "set_event_loop", calls.append)

    try:
        ensure_event_loop()
    finally:
        existing_loop.close()

    assert calls == []
