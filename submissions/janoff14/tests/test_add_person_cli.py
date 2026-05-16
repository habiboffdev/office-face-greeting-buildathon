"""Tests for the add_person.py CLI fallback (Story 4.1)."""

from __future__ import annotations

import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import add_person as cli
from recognition.writer import NoFaceInImageError


class AddPersonCliTests(unittest.TestCase):
    def test_success_prints_added_and_exits_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "photo.jpg"
            image.write_bytes(b"fake-jpeg")

            stdout = io.StringIO()
            with mock.patch.object(cli, "add_person") as writer, \
                 mock.patch.object(cli, "load_config", return_value={"people_db_path": "people.json", "faces_folder": "faces"}), \
                 mock.patch.object(sys, "stdout", stdout):
                code = cli.main(["Judge Karimov", str(image)])

            self.assertEqual(code, 0)
            self.assertIn("Added: Judge Karimov", stdout.getvalue())
            writer.assert_called_once()
            args = writer.call_args.args
            self.assertEqual(args[0], "Judge Karimov")
            self.assertEqual(args[1], image)

    def test_missing_args_prints_usage_and_exits_one(self) -> None:
        stderr = io.StringIO()
        with mock.patch.object(sys, "stderr", stderr):
            code = cli.main([])
        self.assertEqual(code, 1)
        self.assertIn("Usage:", stderr.getvalue())

    def test_too_few_args_prints_usage_and_exits_one(self) -> None:
        stderr = io.StringIO()
        with mock.patch.object(sys, "stderr", stderr):
            code = cli.main(["only-name"])
        self.assertEqual(code, 1)
        self.assertIn("Usage:", stderr.getvalue())

    def test_image_path_missing_exits_two_with_message(self) -> None:
        stderr = io.StringIO()
        with mock.patch.object(cli, "add_person") as writer, \
             mock.patch.object(sys, "stderr", stderr):
            code = cli.main(["Alice", "no/such/file.jpg"])
        self.assertEqual(code, 2)
        self.assertIn("image file not found", stderr.getvalue())
        writer.assert_not_called()

    def test_no_face_in_image_exits_two_with_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "photo.jpg"
            image.write_bytes(b"fake")

            stderr = io.StringIO()
            with mock.patch.object(cli, "add_person", side_effect=NoFaceInImageError("no face")), \
                 mock.patch.object(cli, "load_config", return_value={}), \
                 mock.patch.object(sys, "stderr", stderr):
                code = cli.main(["Alice", str(image)])

            self.assertEqual(code, 2)
            self.assertIn("no face detected", stderr.getvalue())

    def test_value_error_from_writer_exits_two(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "photo.jpg"
            image.write_bytes(b"fake")

            stderr = io.StringIO()
            with mock.patch.object(cli, "add_person", side_effect=ValueError("could not decode image")), \
                 mock.patch.object(cli, "load_config", return_value={}), \
                 mock.patch.object(sys, "stderr", stderr):
                code = cli.main(["Alice", str(image)])

            self.assertEqual(code, 2)
            self.assertIn("could not decode image", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
