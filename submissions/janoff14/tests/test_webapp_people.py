"""Tests for the admin web UI — people CRUD (Story 5.3)."""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import webapp
from recognition.writer import NoFaceInImageError


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
    return app, people_db, faces, videos


def _write_people_json(path: Path, entries: list[dict]) -> None:
    payload = {"people": [
        {
            "name": e["name"],
            "encoding": [0.0] * 128,
            **({"flavor": e["flavor"]} if e.get("flavor") else {}),
            **({"language": e["language"]} if e.get("language") else {}),
            **({"birthday": e["birthday"]} if e.get("birthday") else {}),
            **({"custom_message": e["custom_message"]} if e.get("custom_message") else {}),
        }
        for e in entries
    ]}
    path.write_text(json.dumps(payload), encoding="utf-8")


class WebappPeopleTests(unittest.TestCase):
    def test_index_renders_with_no_people(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app, *_ = _make_app(Path(tmp))
            client = app.test_client()
            resp = client.get("/")
            self.assertEqual(resp.status_code, 200)
            body = resp.get_data(as_text=True)
            self.assertIn("People", body)
            self.assertIn("No people registered yet.", body)

    def test_index_lists_a_registered_person(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app, people_db, faces, _ = _make_app(Path(tmp))
            _write_people_json(people_db, [{"name": "Alice"}])
            (faces / "alice.jpg").write_bytes(b"x")
            client = app.test_client()

            resp = client.get("/")

            body = resp.get_data(as_text=True)
            self.assertIn("Alice", body)
            self.assertIn("/faces/alice.jpg", body)

    def test_index_lists_greeting_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app, people_db, faces, _ = _make_app(Path(tmp))
            _write_people_json(
                people_db,
                [{"name": "Alice", "language": "uz", "birthday": "05-16", "custom_message": "demo"}],
            )
            (faces / "alice.jpg").write_bytes(b"x")
            client = app.test_client()

            resp = client.get("/")

            body = resp.get_data(as_text=True)
            self.assertIn("UZ - 05-16", body)
            self.assertIn("demo", body)

    def test_add_person_calls_writer_and_redirects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app, *_ = _make_app(Path(tmp))
            client = app.test_client()

            with mock.patch.object(webapp, "add_person") as writer:
                resp = client.post(
                    "/people/add",
                    data={
                        "name": "Alice",
                        "photo": (io.BytesIO(b"fake-jpg"), "alice.jpg"),
                    },
                    content_type="multipart/form-data",
                    follow_redirects=False,
                )

            self.assertEqual(resp.status_code, 302)
            writer.assert_called_once()
            call_args = writer.call_args.args
            self.assertEqual(call_args[0], "Alice")
            self.assertEqual(writer.call_args.kwargs["language"], None)

    def test_update_person_metadata_calls_writer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app, *_ = _make_app(Path(tmp))
            client = app.test_client()

            with mock.patch.object(webapp, "update_person_metadata", return_value=True) as writer:
                resp = client.post(
                    "/people/update",
                    data={
                        "name": "Alice",
                        "language": "ru",
                        "birthday": "05-16",
                        "custom_message": "hi",
                        "flavor": "one\ntwo",
                    },
                    follow_redirects=True,
                )

            self.assertIn("Alice updated", resp.get_data(as_text=True))
            writer.assert_called_once()
            self.assertEqual(writer.call_args.kwargs["language"], "ru")
            self.assertEqual(writer.call_args.kwargs["flavor"], ["one", "two"])

    def test_capture_person_uses_camera_then_writer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app, *_ = _make_app(Path(tmp))
            client = app.test_client()

            with mock.patch.object(webapp, "capture_frame_to_file", return_value=Path(tmp) / "capture.jpg") as capture, \
                 mock.patch.object(webapp, "add_person") as writer:
                resp = client.post(
                    "/people/capture",
                    data={"name": "Alice", "language": "uz"},
                    follow_redirects=True,
                )

            self.assertIn("captured from camera", resp.get_data(as_text=True))
            capture.assert_called_once()
            writer.assert_called_once()
            self.assertEqual(writer.call_args.args[0], "Alice")

    def test_auth_redirects_until_login(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            people_db = Path(tmp) / "people.json"
            faces = Path(tmp) / "faces"
            videos = Path(tmp) / "videos"
            faces.mkdir()
            videos.mkdir()
            app = webapp.create_app({
                "people_db_path": str(people_db),
                "faces_folder": str(faces),
                "video_folder": str(videos),
                "web_username": "admin",
                "web_password": "secret",
            })
            app.config["TESTING"] = True
            client = app.test_client()

            self.assertEqual(client.get("/").status_code, 302)
            resp = client.post("/login", data={"username": "admin", "password": "secret"})
            self.assertEqual(resp.status_code, 302)
            self.assertEqual(client.get("/").status_code, 200)

    def test_email_auth_redirects_until_allowed_email_login(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            people_db = Path(tmp) / "people.json"
            faces = Path(tmp) / "faces"
            videos = Path(tmp) / "videos"
            faces.mkdir()
            videos.mkdir()
            app = webapp.create_app({
                "people_db_path": str(people_db),
                "faces_folder": str(faces),
                "video_folder": str(videos),
                "web_allowed_emails": ["admin@example.com"],
                "web_password": "secret",
            })
            app.config["TESTING"] = True
            client = app.test_client()

            self.assertEqual(client.get("/").status_code, 302)
            bad = client.post("/login", data={"email": "other@example.com", "password": "secret"}, follow_redirects=True)
            self.assertIn("Invalid email or password", bad.get_data(as_text=True))
            good = client.post("/login", data={"email": "ADMIN@example.com", "password": "secret"})
            self.assertEqual(good.status_code, 302)
            self.assertEqual(client.get("/").status_code, 200)

    def test_add_person_missing_name_flashes_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app, *_ = _make_app(Path(tmp))
            client = app.test_client()

            with mock.patch.object(webapp, "add_person") as writer:
                resp = client.post(
                    "/people/add",
                    data={"name": "", "photo": (io.BytesIO(b"x"), "a.jpg")},
                    content_type="multipart/form-data",
                    follow_redirects=True,
                )

            writer.assert_not_called()
            self.assertIn("Name is required", resp.get_data(as_text=True))

    def test_add_person_no_face_flashes_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app, *_ = _make_app(Path(tmp))
            client = app.test_client()

            with mock.patch.object(webapp, "add_person", side_effect=NoFaceInImageError("no face")):
                resp = client.post(
                    "/people/add",
                    data={"name": "Ghost", "photo": (io.BytesIO(b"x"), "g.jpg")},
                    content_type="multipart/form-data",
                    follow_redirects=True,
                )

            self.assertIn("No face detected", resp.get_data(as_text=True))

    def test_delete_person_calls_writer_and_redirects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app, people_db, _, _ = _make_app(Path(tmp))
            _write_people_json(people_db, [{"name": "Alice"}])
            client = app.test_client()

            with mock.patch.object(webapp, "remove_person", return_value=True) as writer:
                resp = client.post(
                    "/people/delete",
                    data={"name": "Alice"},
                    follow_redirects=True,
                )

            writer.assert_called_once()
            self.assertIn("Alice removed", resp.get_data(as_text=True))

    def test_delete_unknown_person_flashes_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app, people_db, _, _ = _make_app(Path(tmp))
            _write_people_json(people_db, [{"name": "Alice"}])
            client = app.test_client()

            with mock.patch.object(webapp, "remove_person") as writer:
                resp = client.post(
                    "/people/delete",
                    data={"name": "Bob"},
                    follow_redirects=True,
                )

            writer.assert_not_called()
            self.assertIn("not registered", resp.get_data(as_text=True))

    def test_face_photo_route_serves_existing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app, _, faces, _ = _make_app(Path(tmp))
            (faces / "alice.jpg").write_bytes(b"jpeg-bytes")
            client = app.test_client()

            resp = client.get("/faces/alice.jpg")
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.get_data(), b"jpeg-bytes")

    def test_face_photo_route_404_for_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app, *_ = _make_app(Path(tmp))
            client = app.test_client()
            resp = client.get("/faces/ghost.jpg")
            self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()
