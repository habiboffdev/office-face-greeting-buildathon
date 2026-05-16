"""Seed-set bootstrap helpers for demo recognition data."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from recognition.registry import EMBEDDING_DIM, Registry, load_registry
from recognition.writer import add_person

SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
DEFAULT_EXPECTED_SEED_COUNT = 5
GENERATED_DEMO_PHOTO = re.compile(r"demo_person_\d+$")


@dataclass(frozen=True)
class SeedPerson:
    name: str
    image_path: Path


def _resolve_image_path(raw_path: str, base_dir: Path) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    candidate = base_dir / path
    if candidate.exists():
        return candidate
    return Path.cwd() / path


def load_seed_manifest(path: Path) -> list[SeedPerson]:
    """Read a CSV manifest with ``name,image_path`` columns."""
    path = Path(path)
    people: list[SeedPerson] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"name", "image_path"}
        missing = required.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"seed manifest missing columns: {', '.join(sorted(missing))}")
        for line_number, row in enumerate(reader, start=2):
            name = (row.get("name") or "").strip()
            image = (row.get("image_path") or "").strip()
            if not name or not image:
                raise ValueError(f"seed manifest row {line_number} must include name and image_path")
            people.append(SeedPerson(name=name, image_path=_resolve_image_path(image, path.parent)))
    return people


def discover_seed_people(
    source_dir: Path,
    expected_count: int = DEFAULT_EXPECTED_SEED_COUNT,
) -> list[SeedPerson]:
    """Create ``Demo Person N`` seed people from sorted image files in *source_dir*."""
    source_dir = Path(source_dir)
    photos = [
        entry
        for entry in sorted(source_dir.iterdir())
        if entry.is_file() and entry.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS
        and not GENERATED_DEMO_PHOTO.fullmatch(entry.stem.lower())
    ]
    if len(photos) != expected_count:
        raise ValueError(
            f"expected exactly {expected_count} seed photos in {source_dir}, found {len(photos)}"
        )
    return [
        SeedPerson(name=f"Demo Person {index}", image_path=photo)
        for index, photo in enumerate(photos, start=1)
    ]


def validate_seed_registry(registry: Registry, expected_count: int) -> None:
    """Ensure the loaded registry matches the seed-set shape contract."""
    if len(registry.names) != expected_count:
        raise ValueError(f"expected {expected_count} people in registry, found {len(registry.names)}")
    if registry.encodings.shape != (expected_count, EMBEDDING_DIM):
        raise ValueError(
            f"expected registry shape ({expected_count}, {EMBEDDING_DIM}), "
            f"got {registry.encodings.shape}"
        )


def bootstrap_seed_set(
    people: Iterable[SeedPerson],
    people_json_path: Path,
    faces_dir: Path,
    expected_count: int = DEFAULT_EXPECTED_SEED_COUNT,
    add_person_func: Callable[[str, Path, Path, Path], None] = add_person,
) -> Registry:
    """Add seed people with the shared writer and return the validated registry."""
    people_list = list(people)
    if len(people_list) != expected_count:
        raise ValueError(f"expected exactly {expected_count} seed people, got {len(people_list)}")

    for person in people_list:
        add_person_func(person.name, person.image_path, Path(people_json_path), Path(faces_dir))

    registry = load_registry(Path(people_json_path))
    validate_seed_registry(registry, expected_count)
    return registry
