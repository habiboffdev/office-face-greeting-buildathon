"""Recognition event log — file-based IPC from worker to bot (Story 5.6).

The recognition worker (a ``multiprocessing.Process``) and the Telegram
bot (a ``subprocess.Popen``) don't share Python-level queues, so we use
a one-line-per-event JSONL file in ``logs/recognitions.jsonl`` as a
durable, trivially-testable IPC channel. The bot tails this file via a
polling job and pushes notifications to admin chats.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RECOGNITIONS_FILENAME = "recognitions.jsonl"


def append_recognition_event(log_dir: Path, name: str, timestamp: float) -> Path:
    """Append a one-line JSON record for *name* / *timestamp* to the log.

    Returns the final path. Creates *log_dir* if missing. Tolerates write
    errors by printing to stderr — the greeting queue is the source of
    truth, this log is for the bot notifier only.
    """
    log_dir = Path(log_dir)
    target = log_dir / RECOGNITIONS_FILENAME
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        record = json.dumps({"name": name, "timestamp": float(timestamp)})
        with target.open("a", encoding="utf-8") as handle:
            handle.write(record + "\n")
    except OSError as exc:
        print(f"RECOGNITION_LOG_ERROR {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
    return target


def read_new_events(path: Path, last_offset: int) -> tuple[list[dict], int]:
    """Read new JSON lines from *path* starting at *last_offset*.

    Returns ``(events, new_offset)``. Malformed lines are skipped silently.
    If the file doesn't exist or has shrunk below *last_offset* (truncated
    or rotated), starts from offset 0.
    """
    path = Path(path)
    if not path.is_file():
        return ([], last_offset)
    try:
        size = path.stat().st_size
    except OSError:
        return ([], last_offset)
    start = last_offset if last_offset <= size else 0
    events: list[dict] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            handle.seek(start)
            for raw in handle:
                line = raw.strip()
                if not line:
                    continue
                try:
                    parsed = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(parsed, dict) and "name" in parsed:
                    events.append(parsed)
            new_offset = handle.tell()
    except OSError:
        return ([], last_offset)
    return events, new_offset


def initial_offset(path: Path) -> int:
    """Return the current end-of-file offset, or 0 if the file is missing.

    The bot uses this on startup so a restart doesn't replay old events.
    """
    path = Path(path)
    if not path.is_file():
        return 0
    try:
        return path.stat().st_size
    except OSError:
        return 0
