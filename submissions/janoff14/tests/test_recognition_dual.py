"""Tests for recognition.recognize.recognize_dual.

Same null-path + integration split as test_recognition_recognize.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from recognition.recognize import recognize_dual
from recognition.registry import Registry, load_registry
from tests._fixtures import (
    DEFAULT_FIXTURE_NAME,
    FIXTURE_PROBE,
    ensure_one_person_fixture,
)


def _empty_registry() -> Registry:
    return Registry(names=[], encodings=np.zeros((0, 128)))


class TestRecognizeDualDeterministic(unittest.TestCase):
    def test_empty_registry_returns_none(self) -> None:
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        self.assertIsNone(recognize_dual(frame, _empty_registry(), tolerance=0.5))

    def test_black_frame_returns_none(self) -> None:
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        reg = Registry(names=["Ghost"], encodings=np.zeros((1, 128)))
        self.assertIsNone(recognize_dual(frame, reg, tolerance=0.5))


class TestRecognizeDualIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture_path = ensure_one_person_fixture()
        if cls.fixture_path is None:
            raise unittest.SkipTest("No face photo available in faces/")

    def test_known_face_returns_registered_name(self) -> None:
        import cv2

        registry = load_registry(self.fixture_path)
        frame = cv2.imread(str(FIXTURE_PROBE))
        self.assertIsNotNone(frame, "probe failed to load")
        result = recognize_dual(frame, registry, tolerance=0.5)
        self.assertEqual(result, DEFAULT_FIXTURE_NAME)


if __name__ == "__main__":
    unittest.main()
