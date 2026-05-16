"""File-watcher hot-reload for ``people.json``.

Story 3.5: when the bot, CLI, or a manual edit changes ``people.json``,
the recognition worker reloads its in-memory registry within 5 seconds
without restart (FR18, FR19, NFR4).

The reloader watches the parent directory (watchdog observes
directories, not single files), filters events to the target basename,
and sets a ``threading.Event`` flag. The worker's main loop polls the
flag and performs the actual ``load_registry`` call — single-writer for
the registry pointer, no locks needed.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer


class PeopleRegistryReloader:
    """Watch ``people.json`` and flag the worker when it changes."""

    def __init__(self, people_db_path: Path) -> None:
        self.people_db_path = Path(people_db_path)
        self._flag = threading.Event()
        self._observer: Any = None

    def start(self) -> None:
        if self._observer is not None:
            return
        watch_dir = self.people_db_path.parent
        if not watch_dir.exists():
            watch_dir.mkdir(parents=True, exist_ok=True)
        target_name = self.people_db_path.name
        flag = self._flag

        class _Handler(FileSystemEventHandler):
            def _is_target(self, event) -> bool:
                src = Path(getattr(event, "src_path", "") or "").name
                dest = Path(getattr(event, "dest_path", "") or "").name
                return src == target_name or dest == target_name

            def on_modified(self, event) -> None:
                if not event.is_directory and self._is_target(event):
                    flag.set()

            def on_created(self, event) -> None:
                if not event.is_directory and self._is_target(event):
                    flag.set()

            def on_moved(self, event) -> None:
                if not event.is_directory and self._is_target(event):
                    flag.set()

        observer = Observer()
        observer.schedule(_Handler(), str(watch_dir), recursive=False)
        observer.start()
        self._observer = observer

    def stop(self) -> None:
        if self._observer is None:
            return
        observer = self._observer
        self._observer = None
        observer.stop()
        observer.join(timeout=2.0)

    @property
    def reload_pending(self) -> bool:
        return self._flag.is_set()

    def clear_pending(self) -> None:
        self._flag.clear()

    def request_reload(self) -> None:
        """Test hook: synthesize a reload request without touching the FS."""
        self._flag.set()
