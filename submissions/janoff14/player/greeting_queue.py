"""Helpers for worker-to-player greeting events."""

from __future__ import annotations

import queue
from typing import Callable

MAX_GREETING_EVENTS_PER_POLL = 32


def _event_name(event: object) -> str | None:
    """Return a valid greeting name from a queue event, if present."""
    if not isinstance(event, dict):
        return None
    name = event.get("name")
    if not isinstance(name, str):
        return None
    name = name.strip()
    return name or None


def _event_flavors(event: object) -> list[str]:
    if not isinstance(event, dict):
        return []
    raw = event.get("flavors")
    if not isinstance(raw, list):
        return []
    return [str(f) for f in raw if isinstance(f, str) and f]


def _event_metadata(event: object) -> dict[str, str]:
    if not isinstance(event, dict):
        return {}
    metadata = {}
    for key in ("language", "birthday", "custom_message"):
        value = event.get(key)
        if isinstance(value, str) and value:
            metadata[key] = value
    return metadata


def drain_greeting_queue(
    greeting_queue,
    on_greeting: Callable[..., None],
    max_events: int = MAX_GREETING_EVENTS_PER_POLL,
) -> int:
    """Drain queued greeting events without blocking the Qt event loop.

    Callback contract: callback is invoked as ``on_greeting(name, flavors=[...])``.
    For backward compatibility, callbacks that take only ``name`` still work
    because ``flavors`` is passed as a keyword argument and a TypeError on
    older signatures is caught and retried with just ``name``.
    """
    if greeting_queue is None:
        return 0

    handled = 0
    for _ in range(max_events):
        try:
            event = greeting_queue.get_nowait()
        except queue.Empty:
            break
        name = _event_name(event)
        if name is None:
            continue
        flavors = _event_flavors(event)
        metadata = _event_metadata(event)
        try:
            on_greeting(name, flavors=flavors, **metadata)
        except TypeError:
            on_greeting(name)
        handled += 1
    return handled
