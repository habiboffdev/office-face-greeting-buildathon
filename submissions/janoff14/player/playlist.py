"""Pure-function playlist helpers — no Qt dependency, fully unit-testable."""

from __future__ import annotations

from datetime import datetime, time
from pathlib import Path
from typing import Any

from player.video_writer import SUPPORTED_VIDEO_EXTENSIONS

VIDEO_EXTENSIONS = SUPPORTED_VIDEO_EXTENSIONS


def scan_playlist(folder: Path) -> list[Path]:
    """Return the alphabetically sorted list of playable video files in *folder*.

    Only top-level files with extensions in :data:`VIDEO_EXTENSIONS` are
    included; subdirectories are skipped so the .tmp/ atomic-write staging
    folder used by later stories never produces partial entries. A missing
    folder returns an empty list rather than raising — the caller decides
    whether that's a configuration error or just an empty playlist.
    """
    if not folder.is_dir():
        return []
    matches = [
        entry
        for entry in folder.iterdir()
        if entry.is_file() and entry.suffix.lower() in VIDEO_EXTENSIONS
    ]
    matches.sort(key=lambda p: p.name.lower())
    return matches


def minutes_since_midnight(value: str | time) -> int:
    """Convert ``HH:MM`` or a ``datetime.time`` to minutes since midnight."""
    if isinstance(value, time):
        return value.hour * 60 + value.minute
    raw = str(value).strip()
    parts = raw.split(":", 1)
    if len(parts) != 2 or not all(part.isdigit() for part in parts):
        raise ValueError(f"time must be HH:MM, got {value!r}")
    hour, minute = (int(parts[0]), int(parts[1]))
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"time must be HH:MM, got {value!r}")
    return hour * 60 + minute


def _time_in_window(current: int, start: int, end: int) -> bool:
    if start == end:
        return True
    if start < end:
        return start <= current < end
    return current >= start or current < end


def active_video_folder(
    default_folder: Path,
    schedule: list[dict[str, Any]] | None,
    *,
    now: datetime | None = None,
) -> Path:
    """Return the currently active video folder for an optional schedule.

    Each schedule entry supports ``start``, ``end``, and ``folder``. Windows
    that cross midnight are supported, and the first matching entry wins.
    Invalid entries are ignored so a typo does not crash the kiosk.
    """
    default_folder = Path(default_folder)
    entries = schedule or []
    current_dt = now or datetime.now()
    current = minutes_since_midnight(current_dt.time())
    for entry in entries:
        try:
            folder = Path(str(entry["folder"]))
            start = minutes_since_midnight(entry["start"])
            end = minutes_since_midnight(entry["end"])
        except (KeyError, TypeError, ValueError):
            continue
        if _time_in_window(current, start, end):
            return folder
    return default_folder


def scan_active_playlist(
    default_folder: Path,
    schedule: list[dict[str, Any]] | None,
    *,
    now: datetime | None = None,
) -> list[Path]:
    """Scan the playlist folder selected by ``active_video_folder``."""
    return scan_playlist(active_video_folder(default_folder, schedule, now=now))


def advance(current_index: int, playlist_length: int) -> int:
    """Return the next playlist index, wrapping at the end."""
    if playlist_length <= 0:
        raise ValueError("playlist_length must be positive")
    return (current_index + 1) % playlist_length


def next_after_rescan(
    current_path: Path,
    last_index: int,
    new_playlist: list[Path],
) -> tuple[list[Path], int]:
    """Decide what to play next after rescanning ``videos/``.

    Returns ``(effective_playlist, next_index)``.

    Cases:
    * Empty ``new_playlist`` → fall back to a one-entry list of *current_path*
      so the player keeps something on screen (AC 9).
    * *current_path* still present in *new_playlist* → advance from its
      position (so the rotation order is preserved).
    * *current_path* absent (deleted while playing) → advance from
      *last_index* clamped to the new length.
    """
    if not new_playlist:
        return ([current_path], 0)

    try:
        current_index = next(
            i for i, p in enumerate(new_playlist) if p == current_path
        )
        next_index = advance(current_index, len(new_playlist))
    except StopIteration:
        clamped = max(0, min(last_index, len(new_playlist) - 1))
        next_index = advance(clamped, len(new_playlist))
    return (new_playlist, next_index)
