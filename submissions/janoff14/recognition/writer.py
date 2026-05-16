"""Shared atomic writer for ``people.json``.

The Telegram bot (Story 3.2), the ``add_person.py`` CLI (Story 4.1), and
any future writer all call into this module. Single code path means no
schema drift between admin surfaces (AR9).

Atomicity contract:
* Writes go to ``people.json.tmp`` first, ``fsync``-ed, then renamed via
  ``os.replace`` — atomic on Windows and POSIX for same-volume renames.
* All add/remove operations hold ``people.json.lock`` (via ``filelock``)
  so concurrent writers serialize. A watcher reader (Story 3.5) will
  only ever see the post-replace state.

Public API:
* :func:`add_person` — embed an image, upsert the entry, copy photo.
* :func:`remove_person` — drop the entry, delete the canonical photo.
* :class:`NoFaceInImageError` — raised when ``add_person`` is given an
  image with no detectable face.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path

import cv2
import face_recognition
from filelock import FileLock

from recognition.registry import load_registry

DEFAULT_PEOPLE_PATH = Path("people.json")
DEFAULT_FACES_DIR = Path("faces")
SUPPORTED_LANGUAGES = frozenset({"en", "uz", "ru"})

_UNSAFE_CHARS = re.compile(r"[^a-z0-9._-]+")


class NoFaceInImageError(ValueError):
    """Raised when add_person can't find a face in the source image."""


def _safe_name(name: str) -> str:
    """Return a filesystem-safe version of *name* for ``faces/<safe>.jpg``."""
    cleaned = _UNSAFE_CHARS.sub("_", name.strip().lower()).strip("_")
    if not cleaned:
        raise ValueError(f"name reduces to empty after sanitization: {name!r}")
    return cleaned


def _atomic_write_json(path: Path, payload: dict) -> None:
    """Write *payload* to *path* via temp + fsync + rename."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(tmp, path)


def _normalize_language(language: str | None) -> str:
    value = (language or "en").strip().lower()
    return value if value in SUPPORTED_LANGUAGES else "en"


def _normalize_birthday(birthday: str | None) -> str:
    value = (birthday or "").strip()
    if not value:
        return ""
    if len(value) == 5 and value[2] == "-":
        mm, dd = value.split("-", 1)
        if mm.isdigit() and dd.isdigit() and 1 <= int(mm) <= 12 and 1 <= int(dd) <= 31:
            return value
    raise ValueError("birthday must be empty or MM-DD")


def _entry_from_registry(registry, idx: int) -> dict:
    entry = {
        "name": registry.names[idx],
        "encoding": registry.encodings[idx].tolist(),
    }
    if idx < len(registry.flavors) and registry.flavors[idx]:
        entry["flavor"] = list(registry.flavors[idx])
    if idx < len(registry.languages) and registry.languages[idx] and registry.languages[idx] != "en":
        entry["language"] = registry.languages[idx]
    if idx < len(registry.birthdays) and registry.birthdays[idx]:
        entry["birthday"] = registry.birthdays[idx]
    if idx < len(registry.custom_messages) and registry.custom_messages[idx]:
        entry["custom_message"] = registry.custom_messages[idx]
    if idx < len(registry.telegram_chat_ids) and registry.telegram_chat_ids[idx]:
        entry["telegram_chat_id"] = registry.telegram_chat_ids[idx]
    return entry


def _compute_largest_face_encoding(image_path: Path) -> "list[float]":
    """Load *image_path*, return the largest face's 128-D embedding as a list."""
    if not image_path.exists():
        raise ValueError(f"image not found: {image_path}")
    image = cv2.imread(str(image_path))
    if image is None:
        raise ValueError(f"could not decode image: {image_path}")
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    locations = face_recognition.face_locations(rgb, model="hog")
    if not locations:
        raise NoFaceInImageError(f"no face detected in {image_path}")
    locations.sort(
        key=lambda box: (box[2] - box[0]) * (box[1] - box[3]),
        reverse=True,
    )
    encodings = face_recognition.face_encodings(rgb, [locations[0]])
    if not encodings:
        raise NoFaceInImageError(f"no encoding produced for {image_path}")
    return encodings[0].tolist()


def add_person(
    name: str,
    image_path: Path,
    people_json_path: Path = DEFAULT_PEOPLE_PATH,
    faces_dir: Path = DEFAULT_FACES_DIR,
    flavor: list[str] | None = None,
    language: str | None = None,
    birthday: str | None = None,
    custom_message: str | None = None,
    telegram_chat_id: int | str | None = None,
) -> None:
    """Upsert *name* into *people_json_path* with the embedding from *image_path*.

    Raises :class:`NoFaceInImageError` when the source image has no face,
    :class:`ValueError` when the image cannot be decoded, and
    :class:`ValueError` when *name* sanitizes to empty.

    *flavor* is an optional list of personality lines (Story 5.1). If
    omitted on an upsert, the existing entry's flavor is preserved.
    """
    image_path = Path(image_path)
    people_json_path = Path(people_json_path)
    faces_dir = Path(faces_dir)
    safe = _safe_name(name)  # validates name eagerly
    new_language = _normalize_language(language)
    new_birthday = _normalize_birthday(birthday)
    new_custom_message = (custom_message or "").strip()
    new_telegram_chat_id = str(telegram_chat_id).strip() if telegram_chat_id is not None else ""

    encoding = _compute_largest_face_encoding(image_path)

    lock = FileLock(str(people_json_path) + ".lock")
    with lock:
        registry = load_registry(people_json_path)
        existing_flavor: list[str] = []
        existing_language = "en"
        existing_birthday = ""
        existing_custom_message = ""
        existing_telegram_chat_id = ""
        for idx, existing in enumerate(registry.names):
            if existing.lower() == name.lower():
                if idx < len(registry.flavors):
                    existing_flavor = list(registry.flavors[idx])
                if idx < len(registry.languages):
                    existing_language = registry.languages[idx]
                if idx < len(registry.birthdays):
                    existing_birthday = registry.birthdays[idx]
                if idx < len(registry.custom_messages):
                    existing_custom_message = registry.custom_messages[idx]
                if idx < len(registry.telegram_chat_ids):
                    existing_telegram_chat_id = registry.telegram_chat_ids[idx]
                break
        kept = []
        for idx, existing in enumerate(registry.names):
            if existing.lower() == name.lower():
                continue
            kept.append(_entry_from_registry(registry, idx))
        new_flavor = list(flavor) if flavor is not None else existing_flavor
        if language is None:
            new_language = existing_language
        if birthday is None:
            new_birthday = existing_birthday
        if custom_message is None:
            new_custom_message = existing_custom_message
        if telegram_chat_id is None:
            new_telegram_chat_id = existing_telegram_chat_id
        new_entry = {"name": name, "encoding": encoding}
        if new_flavor:
            new_entry["flavor"] = new_flavor
        if new_language and new_language != "en":
            new_entry["language"] = new_language
        if new_birthday:
            new_entry["birthday"] = new_birthday
        if new_custom_message:
            new_entry["custom_message"] = new_custom_message
        if new_telegram_chat_id:
            new_entry["telegram_chat_id"] = new_telegram_chat_id
        kept.append(new_entry)
        _atomic_write_json(people_json_path, {"people": kept})

    faces_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(image_path, faces_dir / f"{safe}.jpg")


def remove_person(
    name: str,
    people_json_path: Path = DEFAULT_PEOPLE_PATH,
    faces_dir: Path = DEFAULT_FACES_DIR,
) -> bool:
    """Drop *name* from *people_json_path*. Returns True if it existed.

    Also deletes ``faces/<safe>.jpg`` if present. Missing photo is fine.
    """
    people_json_path = Path(people_json_path)
    faces_dir = Path(faces_dir)

    lock = FileLock(str(people_json_path) + ".lock")
    with lock:
        registry = load_registry(people_json_path)
        survivors = []
        for idx, existing in enumerate(registry.names):
            if existing.lower() == name.lower():
                continue
            survivors.append(_entry_from_registry(registry, idx))
        if len(survivors) == len(registry.names):
            return False
        _atomic_write_json(people_json_path, {"people": survivors})

    try:
        safe = _safe_name(name)
    except ValueError:
        return True  # entry removed; can't have had a photo
    (faces_dir / f"{safe}.jpg").unlink(missing_ok=True)
    return True


def update_person_metadata(
    name: str,
    people_json_path: Path = DEFAULT_PEOPLE_PATH,
    *,
    language: str | None = None,
    birthday: str | None = None,
    custom_message: str | None = None,
    flavor: list[str] | None = None,
    telegram_chat_id: int | str | None = None,
) -> bool:
    """Update non-biometric metadata for an existing person."""
    people_json_path = Path(people_json_path)
    lock = FileLock(str(people_json_path) + ".lock")
    with lock:
        registry = load_registry(people_json_path)
        updated = []
        found = False
        for idx, existing in enumerate(registry.names):
            entry = _entry_from_registry(registry, idx)
            if existing == name:
                found = True
                if language is not None:
                    normalized = _normalize_language(language)
                    if normalized == "en":
                        entry.pop("language", None)
                    else:
                        entry["language"] = normalized
                if birthday is not None:
                    normalized_birthday = _normalize_birthday(birthday)
                    if normalized_birthday:
                        entry["birthday"] = normalized_birthday
                    else:
                        entry.pop("birthday", None)
                if custom_message is not None:
                    value = custom_message.strip()
                    if value:
                        entry["custom_message"] = value
                    else:
                        entry.pop("custom_message", None)
                if flavor is not None:
                    cleaned = [item.strip() for item in flavor if item.strip()]
                    if cleaned:
                        entry["flavor"] = cleaned
                    else:
                        entry.pop("flavor", None)
                if telegram_chat_id is not None:
                    value = str(telegram_chat_id).strip()
                    if value:
                        entry["telegram_chat_id"] = value
                    else:
                        entry.pop("telegram_chat_id", None)
            updated.append(entry)
        if not found:
            return False
        _atomic_write_json(people_json_path, {"people": updated})
    return True
