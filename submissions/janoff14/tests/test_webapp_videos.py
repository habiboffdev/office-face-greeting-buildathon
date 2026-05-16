"""Tests for the admin web UI — videos CRUD (Story 5.4)."""

from __future__ import annotations

import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import webapp


def _make_app(tmp: Path):
    people_db = tmp / "people.json"
    faces = tmp / "faces"
    faces.mkdir()
    videos = tmp / "videos"
    videos.mkdir()
    app = webapp.create_app({
        "people_db_path": str(people_db),
        "faces_folder": str(faces),
        "video_folder": str(videos),
    })
    app.config["TESTING"] = True
    return app, videos


class WebappVideosTests(unittest.TestCase):
    def test_index_renders_videos_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app, videos = _make_app(Path(tmp))
            (videos / "promo.mp4").write_bytes(b"x")
            client = app.test_client()
            resp = client.get("/")
            body = resp.get_data(as_text=True)
            self.assertIn("promo.mp4", body)
            self.assertIn("Videos", body)

    def test_add_video_calls_writer_and_redirects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app, _ = _make_app(Path(tmp))
            client = app.test_client()

            with mock.patch.object(webapp, "add_video") as writer:
                resp = client.post(
                    "/videos/add",
                    data={"video": (io.BytesIO(b"mp4-bytes"), "clip.mp4")},
                    content_type="multipart/form-data",
                    follow_redirects=True,
                )

            writer.assert_called_once()
            self.assertIn("clip.mp4 added", resp.get_data(as_text=True))

    def test_add_video_unsupported_extension_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app, _ = _make_app(Path(tmp))
            client = app.test_client()

            with mock.patch.object(webapp, "add_video") as writer:
                resp = client.post(
                    "/videos/add",
                    data={"video": (io.BytesIO(b"x"), "bad.avi")},
                    content_type="multipart/form-data",
                    follow_redirects=True,
                )

            writer.assert_not_called()
            self.assertIn("Unsupported video format", resp.get_data(as_text=True))

    def test_add_video_missing_file_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app, _ = _make_app(Path(tmp))
            client = app.test_client()
            with mock.patch.object(webapp, "add_video") as writer:
                resp = client.post(
                    "/videos/add",
                    data={},
                    content_type="multipart/form-data",
                    follow_redirects=True,
                )
            writer.assert_not_called()
            self.assertIn("video file is required", resp.get_data(as_text=True))

    def test_delete_video_calls_writer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app, videos = _make_app(Path(tmp))
            (videos / "promo.mp4").write_bytes(b"x")
            client = app.test_client()

            with mock.patch.object(webapp, "remove_video", return_value=True) as writer:
                resp = client.post(
                    "/videos/delete",
                    data={"filename": "promo.mp4"},
                    follow_redirects=True,
                )

            writer.assert_called_once()
            self.assertIn("promo.mp4 removed", resp.get_data(as_text=True))

    def test_delete_unknown_video_flashes_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app, _ = _make_app(Path(tmp))
            client = app.test_client()

            with mock.patch.object(webapp, "remove_video", return_value=False):
                resp = client.post(
                    "/videos/delete",
                    data={"filename": "ghost.mp4"},
                    follow_redirects=True,
                )

            self.assertIn("not in the playlist", resp.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
