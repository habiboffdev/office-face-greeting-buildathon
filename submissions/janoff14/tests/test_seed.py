"""Tests for the 5-person seed bootstrap helpers."""

from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from recognition.registry import Registry
from recognition.seed import (
    SeedPerson,
    bootstrap_seed_set,
    discover_seed_people,
    load_seed_manifest,
    validate_seed_registry,
)


def _touch(path: Path) -> Path:
    path.write_bytes(b"photo")
    return path


class TestSeedManifest(unittest.TestCase):
    def test_load_seed_manifest_resolves_relative_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            photo = _touch(root / "alice.jpg")
            manifest = root / "seed.csv"
            with manifest.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["name", "image_path"])
                writer.writeheader()
                writer.writerow({"name": "Alice", "image_path": photo.name})

            people = load_seed_manifest(manifest)

        self.assertEqual(people, [SeedPerson("Alice", photo)])

    def test_manifest_requires_name_and_image_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "bad.csv"
            manifest.write_text("name\nAlice\n", encoding="utf-8")

            with self.assertRaises(ValueError):
                load_seed_manifest(manifest)


class TestSeedDiscovery(unittest.TestCase):
    def test_discovers_exactly_five_supported_images_with_demo_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ["b.jpg", "a.png", "c.jpeg", "d.JPG", "e.PNG"]:
                _touch(root / name)
            _touch(root / "ignore.txt")

            people = discover_seed_people(root)

        self.assertEqual([person.name for person in people], [f"Demo Person {i}" for i in range(1, 6)])
        self.assertEqual([person.image_path.name for person in people], ["a.png", "b.jpg", "c.jpeg", "d.JPG", "e.PNG"])

    def test_discovery_ignores_generated_demo_person_copies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for index in range(1, 6):
                _touch(root / f"source-{index}.jpg")
                _touch(root / f"demo_person_{index}.jpg")

            people = discover_seed_people(root)

        self.assertEqual(len(people), 5)
        self.assertEqual([person.image_path.name for person in people], [f"source-{i}.jpg" for i in range(1, 6)])

    def test_discovery_rejects_wrong_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _touch(root / "only.jpg")

            with self.assertRaises(ValueError):
                discover_seed_people(root)


class TestSeedBootstrap(unittest.TestCase):
    def test_validate_seed_registry_accepts_five_128_dim_rows(self) -> None:
        registry = Registry(
            names=[f"Demo Person {i}" for i in range(1, 6)],
            encodings=np.zeros((5, 128)),
        )

        validate_seed_registry(registry, expected_count=5)

    def test_bootstrap_invokes_writer_for_each_person_and_validates_registry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            people_json = root / "people.json"
            faces_dir = root / "faces"
            people = [SeedPerson(f"Demo Person {i}", root / f"{i}.jpg") for i in range(1, 6)]
            calls: list[tuple[str, Path, Path, Path]] = []

            def fake_add_person(name: str, image_path: Path, json_path: Path, target_faces: Path) -> None:
                calls.append((name, image_path, json_path, target_faces))
                payload = {
                    "people": [
                        {"name": person.name, "encoding": [0.0] * 128}
                        for person in people[: len(calls)]
                    ]
                }
                import json

                people_json.write_text(json.dumps(payload), encoding="utf-8")

            registry = bootstrap_seed_set(
                people,
                people_json_path=people_json,
                faces_dir=faces_dir,
                add_person_func=fake_add_person,
            )

        self.assertEqual(len(calls), 5)
        self.assertEqual(registry.names, [f"Demo Person {i}" for i in range(1, 6)])
        self.assertEqual(registry.encodings.shape, (5, 128))


if __name__ == "__main__":
    unittest.main()
