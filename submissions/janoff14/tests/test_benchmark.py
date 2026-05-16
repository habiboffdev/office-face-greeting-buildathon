"""Tests for benchmark.py (Story 4.3)."""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

import benchmark
from recognition.registry import Registry


class PercentileTests(unittest.TestCase):
    def test_p50_of_known_list(self) -> None:
        self.assertAlmostEqual(benchmark.percentile([0.1, 0.2, 0.3, 0.4, 0.5], 50), 0.3, places=2)

    def test_p95_of_known_list(self) -> None:
        self.assertGreater(benchmark.percentile([0.1, 0.2, 0.3, 0.4, 0.5], 95), 0.4)

    def test_empty_returns_zero(self) -> None:
        self.assertEqual(benchmark.percentile([], 50), 0.0)


class FormatReportTests(unittest.TestCase):
    def test_matches_acceptance_criteria_block(self) -> None:
        report = benchmark.format_report(
            p50_s=0.82,
            p95_s=1.64,
            tp=48,
            total_pos=50,
            fp=0,
            total_neg=50,
            tolerance=0.5,
            seed_people=5,
            attempts_per_person=10,
            strangers_count=5,
            attempts_per_stranger=10,
        )
        expected = (
            "Recognition pipeline latency p50: 0.82 s, p95: 1.64 s\n"
            "True-positive rate: 96% (48/50 attempts)\n"
            "False-positive rate: 0.0% (0/50 attempts)\n"
            "Tolerance: 0.50\n"
            "Seed set: 5 people x 10 attempts; control set: 5 strangers x 10 attempts"
        )
        self.assertEqual(report, expected)


class ComputeViolationsTests(unittest.TestCase):
    def test_clean_run_no_warnings(self) -> None:
        self.assertEqual(benchmark.compute_violations(48, 50, 0, 50), [])

    def test_low_tpr_warns(self) -> None:
        warnings = benchmark.compute_violations(40, 50, 0, 50)
        self.assertTrue(any("TPR" in w for w in warnings))

    def test_any_fp_warns(self) -> None:
        warnings = benchmark.compute_violations(50, 50, 1, 50)
        self.assertTrue(any("FPR" in w for w in warnings))


class RunAttemptsTests(unittest.TestCase):
    def _registry(self) -> Registry:
        return Registry(names=["Alice"], encodings=np.zeros((1, 128)))

    def test_cycles_through_probes_when_fewer_than_attempts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            img = np.zeros((10, 10, 3), dtype=np.uint8)
            path = Path(tmp) / "p.jpg"
            import cv2
            cv2.imwrite(str(path), img)

            calls = {"n": 0}

            def fake_recognize(frame, registry, tolerance):
                calls["n"] += 1
                return "Alice"

            matches, latencies = benchmark._run_attempts(
                [path], "Alice", self._registry(), 0.5, fake_recognize, attempts=10
            )

            self.assertEqual(calls["n"], 10)
            self.assertEqual(matches, 10)
            self.assertEqual(len(latencies), 10)

    def test_mismatched_name_counts_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            img = np.zeros((10, 10, 3), dtype=np.uint8)
            path = Path(tmp) / "p.jpg"
            import cv2
            cv2.imwrite(str(path), img)

            def fake_recognize(frame, registry, tolerance):
                return "Bob"  # wrong name

            matches, _ = benchmark._run_attempts(
                [path], "Alice", self._registry(), 0.5, fake_recognize, attempts=5
            )

            self.assertEqual(matches, 0)

    def test_stranger_any_match_is_false_positive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            img = np.zeros((10, 10, 3), dtype=np.uint8)
            path = Path(tmp) / "stranger.jpg"
            import cv2
            cv2.imwrite(str(path), img)

            def fake_recognize(frame, registry, tolerance):
                return "Alice"  # any non-None for a stranger is a FP

            matches, _ = benchmark._run_attempts(
                [path], None, self._registry(), 0.5, fake_recognize, attempts=3
            )

            self.assertEqual(matches, 3)

    def test_empty_probes_returns_zero_zero(self) -> None:
        matches, latencies = benchmark._run_attempts(
            [], "Alice", self._registry(), 0.5, lambda f, r, t: "Alice", attempts=5
        )
        self.assertEqual(matches, 0)
        self.assertEqual(latencies, [])


class GatherProbeImagesTests(unittest.TestCase):
    def test_seed_folder_preferred_over_canonical(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            faces = root / "faces"
            faces.mkdir()
            (faces / "alice.jpg").write_bytes(b"canonical")

            seed = root / "seed"
            person_dir = seed / "alice"
            person_dir.mkdir(parents=True)
            (person_dir / "a.jpg").write_bytes(b"x")
            (person_dir / "b.jpg").write_bytes(b"y")

            paths = benchmark.gather_probe_images_for("Alice", faces, seed)
            self.assertEqual([p.name for p in paths], ["a.jpg", "b.jpg"])

    def test_canonical_fallback_when_no_seed_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            faces = root / "faces"
            faces.mkdir()
            canonical = faces / "alice.jpg"
            canonical.write_bytes(b"x")

            paths = benchmark.gather_probe_images_for("Alice", faces, None)
            self.assertEqual(paths, [canonical])

    def test_returns_empty_when_nothing_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = benchmark.gather_probe_images_for("Alice", Path(tmp) / "faces")
            self.assertEqual(paths, [])

    def test_caps_at_ten(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            faces = root / "faces"
            faces.mkdir()
            seed = root / "seed"
            person_dir = seed / "alice"
            person_dir.mkdir(parents=True)
            for i in range(15):
                (person_dir / f"{i:02}.jpg").write_bytes(b"x")

            paths = benchmark.gather_probe_images_for("Alice", faces, seed)
            self.assertEqual(len(paths), 10)


class PadRegistryTests(unittest.TestCase):
    def test_pads_up_to_target(self) -> None:
        registry = Registry(names=["Alice"], encodings=np.zeros((1, 128)))
        padded = benchmark._pad_registry_for_capacity(registry, 200)
        self.assertEqual(padded.encodings.shape, (200, 128))
        self.assertEqual(padded.names[0], "Alice")

    def test_no_padding_when_already_at_or_above_target(self) -> None:
        registry = Registry(names=["A", "B"], encodings=np.zeros((2, 128)))
        padded = benchmark._pad_registry_for_capacity(registry, 2)
        self.assertIs(padded, registry)


class MainIntegrationTests(unittest.TestCase):
    def test_missing_people_json_exits_two(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stderr = io.StringIO()
            with mock.patch.object(benchmark, "load_config", return_value={
                "people_db_path": str(Path(tmp) / "people.json"),
            }), mock.patch.object(sys, "stderr", stderr):
                code = benchmark.main([])
            self.assertEqual(code, 2)
            self.assertIn("people.json not found", stderr.getvalue())

    def test_missing_strangers_exits_two(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            people_db = Path(tmp) / "people.json"
            people_db.write_text(json.dumps({"people": [{"name": "Alice", "encoding": [0.0] * 128}]}))

            stderr = io.StringIO()
            with mock.patch.object(benchmark, "load_config", return_value={
                "people_db_path": str(people_db),
                "faces_folder": str(Path(tmp) / "faces"),
                "recognition_tolerance": 0.5,
            }), mock.patch.object(sys, "stderr", stderr):
                code = benchmark.main([
                    "--seed-folder", str(Path(tmp) / "seed"),
                    "--strangers-folder", str(Path(tmp) / "strangers"),
                ])
            self.assertEqual(code, 2)
            self.assertIn("stranger", stderr.getvalue().lower())

    def test_happy_path_prints_report_and_exits_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            people_db = root / "people.json"
            people_db.write_text(json.dumps({"people": [{"name": "Alice", "encoding": [0.0] * 128}]}))

            faces = root / "faces"
            faces.mkdir()
            import cv2
            img = np.zeros((10, 10, 3), dtype=np.uint8)
            cv2.imwrite(str(faces / "alice.jpg"), img)

            strangers = root / "strangers"
            strangers.mkdir()
            cv2.imwrite(str(strangers / "ghost.jpg"), img)

            def fake_recognize(frame, registry, tolerance):
                return "Alice"  # match every time (TP for Alice, FP for ghost)

            stdout = io.StringIO()
            stderr = io.StringIO()
            with mock.patch.object(benchmark, "load_config", return_value={
                "people_db_path": str(people_db),
                "faces_folder": str(faces),
                "recognition_tolerance": 0.5,
            }), mock.patch.object(benchmark, "recognize_dual", side_effect=fake_recognize), \
                 mock.patch.object(sys, "stdout", stdout), \
                 mock.patch.object(sys, "stderr", stderr):
                code = benchmark.main([
                    "--seed-folder", str(root / "seed"),
                    "--strangers-folder", str(strangers),
                ])

            self.assertEqual(code, 0)
            out = stdout.getvalue()
            self.assertIn("Recognition pipeline latency", out)
            self.assertIn("True-positive rate: 100%", out)
            self.assertIn("False-positive rate: 100.0%", out)
            # FP > 0 → stderr warning fires.
            self.assertIn("FPR", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
