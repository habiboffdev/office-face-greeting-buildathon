"""Tests for recognition.recognize.

Splits into:
* deterministic tests that don't need a real face (empty frame, empty registry)
* integration tests gated on a local face photo being available

Run with: python -m unittest tests.test_recognition_recognize
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from recognition.recognize import recognize
from recognition.registry import Registry, load_registry
from tests._fixtures import (
    DEFAULT_FIXTURE_NAME,
    FIXTURE_PEOPLE,
    FIXTURE_PROBE,
    ensure_one_person_fixture,
)


def _empty_registry() -> Registry:
    return Registry(names=[], encodings=np.zeros((0, 128)))


class TestRecognizeDeterministic(unittest.TestCase):
    """No face_recognition fixtures needed — pure null-path checks."""

    def test_empty_registry_returns_none(self) -> None:
        frame = np.zeros((200, 200, 3), dtype=np.uint8)
        self.assertIsNone(recognize(frame, _empty_registry(), tolerance=0.5))

    def test_black_frame_returns_none(self) -> None:
        frame = np.zeros((200, 200, 3), dtype=np.uint8)
        # Even with a non-empty registry, no detectable face → None
        fake = Registry(names=["Ghost"], encodings=np.zeros((1, 128)))
        self.assertIsNone(recognize(frame, fake, tolerance=0.5))


class TestRecognizeIntegration(unittest.TestCase):
    """Gated on the presence of a face photo in faces/."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture_path = ensure_one_person_fixture()
        if cls.fixture_path is None:
            raise unittest.SkipTest("No face photo available in faces/")

    def test_known_face_returns_registered_name(self) -> None:
        import cv2

        registry = load_registry(self.fixture_path)
        frame = cv2.imread(str(FIXTURE_PROBE))
        self.assertIsNotNone(frame, "Probe image failed to load")
        result = recognize(frame, registry, tolerance=0.5)
        self.assertEqual(result, DEFAULT_FIXTURE_NAME)

    def test_unknown_face_returns_none(self) -> None:
        import cv2

        # Build a registry whose embedding is far from anyone's real face.
        # All zeros is well outside the realistic embedding manifold.
        far_registry = Registry(
            names=["NobodyReal"],
            encodings=np.zeros((1, 128), dtype=np.float64),
        )
        frame = cv2.imread(str(FIXTURE_PROBE))
        self.assertIsNotNone(frame)
        # Real face won't match the zero embedding under tolerance 0.5.
        result = recognize(frame, far_registry, tolerance=0.5)
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
