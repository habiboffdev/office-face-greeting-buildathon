"""Shared atomic writer for promo videos in ``videos/``.

The Telegram bot (Story 3.6) and the ``add_video.py`` CLI (Story 4.2)
both call into this module. Single code path means no drift between
admin surfaces (AR9).

Atomicity contract:
* Files are copied to ``videos/.tmp/<filename>`` first, then renamed via
  ``os.replace`` — atomic on Windows and POSIX for same-volume renames
  (NFR18).
* The player's ``scan_playlist`` only walks top-level files, so the
  ``.tmp`` directory is never visible to the playlist mid-write.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

SUPPORTED_VIDEO_EXTENSIONS = frozenset({".mp4", ".mov", ".webm"})
TMP_SUBDIR = ".tmp"


class UnsupportedVideoFormatError(ValueError):
    """Raised when add_video is given a file with an unsupported extension."""

    def __init__(self, extension: str) -> None:
        super().__init__(f"unsupported video format: {extension!r}")
        self.extension = extension


def _safe_filename(source_name: str | None, fallback_stem: str, default_ext: str) -> str:
    """Return a basename safe to drop into ``videos/``.

    Strips any path components, falls back to ``<fallback_stem><default_ext>``
    if *source_name* is empty or path-only.
    """
    if source_name:
        candidate = Path(source_name).name.strip()
        if candidate:
            return candidate
    return f"{fallback_stem}{default_ext}"


def add_video(
    source_path: Path,
    video_folder: Path,
    *,
    target_filename: str | None = None,
) -> Path:
    """Atomically place *source_path* into *video_folder*.

    Returns the final destination path. Raises
    :class:`UnsupportedVideoFormatError` for bad extensions and
    :class:`FileNotFoundError` if *source_path* doesn't exist.

    If *target_filename* is provided it is used (basename only). Otherwise
    the source's filename is used.
    """
    source_path = Path(source_path)
    video_folder = Path(video_folder)

    if not source_path.exists():
        raise FileNotFoundError(source_path)

    filename = Path(target_filename).name if target_filename else source_path.name
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_VIDEO_EXTENSIONS:
        raise UnsupportedVideoFormatError(suffix)

    video_folder.mkdir(parents=True, exist_ok=True)
    tmp_dir = video_folder / TMP_SUBDIR
    tmp_dir.mkdir(parents=True, exist_ok=True)

    tmp_path = tmp_dir / filename
    final_path = video_folder / filename

    shutil.copyfile(source_path, tmp_path)
    os.replace(tmp_path, final_path)
    return final_path


def remove_video(filename: str, video_folder: Path) -> bool:
    """Delete ``video_folder/<filename>`` if it exists. Returns True if removed.

    *filename* is reduced to its basename (no path traversal). Case-sensitive
    exact match against the on-disk name.
    """
    video_folder = Path(video_folder)
    target_name = Path(filename).name
    if not target_name:
        return False
    target = video_folder / target_name
    if not target.is_file():
        return False
    target.unlink()
    return True

