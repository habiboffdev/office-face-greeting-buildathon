"""Read-only registry of registered people loaded from ``people.json``.

Schema::

    {
      "people": [
        {"name": "Alice", "encoding": [128 floats]},
        ...
      ]
    }

The writer module that produces this file lives in Story 2.2 — this
module only consumes it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

EMBEDDING_DIM = 128


@dataclass(frozen=True)
class Registry:
    """Frozen registry: parallel ``names`` list and ``(N, 128)`` encodings matrix.

    ``flavors`` is a parallel list of per-person flavor strings (Story 5.1).
    Empty list for backward compatibility with pre-5.x ``people.json`` files.
    """

    names: list[str]
    encodings: np.ndarray  # shape (N, 128), dtype float64
    flavors: list[list[str]] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    birthdays: list[str] = field(default_factory=list)
    custom_messages: list[str] = field(default_factory=list)
    telegram_chat_ids: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.encodings.ndim != 2 or self.encodings.shape[1] != EMBEDDING_DIM:
            raise ValueError(
                f"encodings must be shape (N, {EMBEDDING_DIM}); got {self.encodings.shape}"
            )
        if len(self.names) != self.encodings.shape[0]:
            raise ValueError(
                f"names ({len(self.names)}) must match encoding rows ({self.encodings.shape[0]})"
            )
        if self.flavors and len(self.flavors) != len(self.names):
            raise ValueError(
                f"flavors ({len(self.flavors)}) must match names ({len(self.names)}) if provided"
            )
        for field_name, values in (
            ("languages", self.languages),
            ("birthdays", self.birthdays),
            ("custom_messages", self.custom_messages),
            ("telegram_chat_ids", self.telegram_chat_ids),
        ):
            if values and len(values) != len(self.names):
                raise ValueError(
                    f"{field_name} ({len(values)}) must match names ({len(self.names)}) if provided"
                )


def load_registry(path: Path) -> Registry:
    """Load a :class:`Registry` from ``people.json``.

    Missing file or empty ``people`` list yields an empty registry (no
    rows). Malformed JSON raises :class:`ValueError` quoting the path.
    """
    path = Path(path)
    if not path.exists():
        return Registry(names=[], encodings=np.zeros((0, EMBEDDING_DIM)))

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"malformed JSON in {path}: {exc}") from exc

    people = payload.get("people", []) if isinstance(payload, dict) else []
    if not people:
        return Registry(
            names=[],
            encodings=np.zeros((0, EMBEDDING_DIM)),
            flavors=[],
            languages=[],
            birthdays=[],
            custom_messages=[],
            telegram_chat_ids=[],
        )

    names: list[str] = []
    rows: list[list[float]] = []
    flavors: list[list[str]] = []
    languages: list[str] = []
    birthdays: list[str] = []
    custom_messages: list[str] = []
    telegram_chat_ids: list[str] = []
    for entry in people:
        names.append(entry["name"])
        rows.append(entry["encoding"])
        flavors.append(list(entry.get("flavor", []) or []))
        languages.append(str(entry.get("language", "en") or "en"))
        birthdays.append(str(entry.get("birthday", "") or ""))
        custom_messages.append(str(entry.get("custom_message", "") or ""))
        telegram_chat_ids.append(str(entry.get("telegram_chat_id", "") or ""))
    encodings = np.asarray(rows, dtype=np.float64)
    return Registry(
        names=names,
        encodings=encodings,
        flavors=flavors,
        languages=languages,
        birthdays=birthdays,
        custom_messages=custom_messages,
        telegram_chat_ids=telegram_chat_ids,
    )
