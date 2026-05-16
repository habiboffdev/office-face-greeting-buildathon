"""Local admin web UI for FaceTag (Stories 5.3 + 5.4).

Run::

    python webapp.py

Binds to ``127.0.0.1:8000``. Reuses the shared writer modules
(``recognition.writer``, ``player.video_writer``) so the bot, CLI, and
this UI all go through the same atomic-write code path (AR9).
"""

from __future__ import annotations

import logging
import os
import secrets
import sys
import tempfile
from pathlib import Path

from flask import (
    Flask,
    Response,
    abort,
    flash,
    get_flashed_messages,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from bot import load_config
from player.playlist import scan_playlist
from player.video_writer import (
    SUPPORTED_VIDEO_EXTENSIONS,
    UnsupportedVideoFormatError,
    add_video,
    remove_video,
)
from recognition.camera_capture import CameraCaptureError, capture_frame_to_file
from recognition.registry import load_registry
from recognition.writer import (
    NoFaceInImageError,
    _safe_name,
    add_person,
    remove_person,
    update_person_metadata,
)

HOST = "127.0.0.1"
PORT = 8000


def create_app(config: dict | None = None) -> Flask:
    cfg = config if config is not None else load_config()
    app = Flask(
        __name__,
        template_folder="webapp/templates",
        static_folder="webapp/static",
    )
    app.secret_key = secrets.token_hex(16)
    app.config["MAX_CONTENT_LENGTH"] = 512 * 1024 * 1024  # 512 MB upper bound for videos

    app.config["PEOPLE_DB_PATH"] = Path(cfg.get("people_db_path", "people.json"))
    app.config["FACES_FOLDER"] = Path(cfg.get("faces_folder", "faces"))
    app.config["VIDEO_FOLDER"] = Path(cfg.get("video_folder", "videos"))
    app.config["WEB_USERNAME"] = str(cfg.get("web_username", "") or "").strip()
    app.config["WEB_PASSWORD"] = str(cfg.get("web_password", "") or "").strip()
    app.config["WEB_ALLOWED_EMAILS"] = {
        str(email).strip().lower()
        for email in (cfg.get("web_allowed_emails") or [])
        if str(email).strip()
    }
    app.config["CAMERA_DEVICE_INDEX"] = int(cfg.get("camera_device_index", 0))
    app.config["CAMERA_BACKEND"] = str(cfg.get("camera_backend", "dshow") or "dshow")

    def auth_enabled() -> bool:
        return bool(
            app.config["WEB_PASSWORD"]
            and (app.config["WEB_ALLOWED_EMAILS"] or app.config["WEB_USERNAME"])
        )

    def is_authenticated() -> bool:
        return not auth_enabled() or bool(session.get("web_authenticated"))

    def login_identifier_allowed(identifier: str) -> bool:
        normalized = identifier.strip().lower()
        allowed_emails: set[str] = app.config["WEB_ALLOWED_EMAILS"]
        if allowed_emails:
            return normalized in allowed_emails
        return secrets.compare_digest(identifier.strip(), app.config["WEB_USERNAME"])

    @app.before_request
    def require_login():
        if request.endpoint in {"login", "static"}:
            return None
        if not is_authenticated():
            return redirect(url_for("login", next=request.path))
        return None

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if not auth_enabled():
            return redirect(url_for("index"))
        if request.method == "POST":
            identifier = (request.form.get("email") or request.form.get("username") or "").strip()
            password = request.form.get("password") or ""
            if (
                login_identifier_allowed(identifier)
                and secrets.compare_digest(password, app.config["WEB_PASSWORD"])
            ):
                session["web_authenticated"] = True
                session["web_login"] = identifier
                return redirect(request.args.get("next") or url_for("index"))
            flash("Invalid email or password.", "error")
        return render_template("login.html")

    @app.route("/logout", methods=["POST"])
    def logout():
        session.pop("web_authenticated", None)
        return redirect(url_for("login"))

    @app.route("/")
    def index():
        registry = load_registry(app.config["PEOPLE_DB_PATH"])
        faces_folder: Path = app.config["FACES_FOLDER"]
        people = []
        for idx, name in enumerate(registry.names):
            try:
                safe = _safe_name(name)
            except ValueError:
                safe = ""
            photo_path = faces_folder / f"{safe}.jpg" if safe else None
            people.append({
                "name": name,
                "safe": safe,
                "has_photo": bool(safe) and photo_path is not None and photo_path.is_file(),
                "initial": (name[:1] or "?").upper(),
                "language": registry.languages[idx] if idx < len(registry.languages) else "en",
                "birthday": registry.birthdays[idx] if idx < len(registry.birthdays) else "",
                "custom_message": registry.custom_messages[idx] if idx < len(registry.custom_messages) else "",
                "flavor": "\n".join(registry.flavors[idx]) if idx < len(registry.flavors) else "",
            })

        videos_paths = scan_playlist(app.config["VIDEO_FOLDER"])
        videos = [{"name": p.name} for p in videos_paths]
        stats = {
            "people": len(people),
            "videos": len(videos),
            "auth": auth_enabled(),
            "camera": app.config["CAMERA_DEVICE_INDEX"],
        }

        return render_template("index.html", people=people, videos=videos, stats=stats)

    @app.route("/faces/<safe_name>.jpg")
    def face_photo(safe_name: str):
        # Defensive basename to block path traversal.
        clean = Path(safe_name).name
        if not clean:
            abort(404)
        faces_folder: Path = app.config["FACES_FOLDER"]
        target = faces_folder / f"{clean}.jpg"
        try:
            target.resolve().relative_to(faces_folder.resolve())
        except (ValueError, OSError):
            abort(404)
        if not target.is_file():
            abort(404)
        data = target.read_bytes()
        return Response(data, mimetype="image/jpeg")

    @app.route("/people/add", methods=["POST"])
    def add_person_route():
        name = (request.form.get("name") or "").strip()
        photo = request.files.get("photo")
        if not name:
            flash("Name is required.", "error")
            return redirect(url_for("index"))
        if photo is None or not photo.filename:
            flash("A photo is required.", "error")
            return redirect(url_for("index"))

        with tempfile.TemporaryDirectory(prefix="webapp-add-person-") as tmp:
            tmp_path = Path(tmp) / Path(photo.filename).name
            photo.save(tmp_path)
            try:
                add_person(
                    name,
                    tmp_path,
                    app.config["PEOPLE_DB_PATH"],
                    app.config["FACES_FOLDER"],
                    language=request.form.get("language"),
                    birthday=request.form.get("birthday"),
                    custom_message=request.form.get("custom_message"),
                    flavor=[
                        line.strip()
                        for line in (request.form.get("flavor") or "").splitlines()
                        if line.strip()
                    ],
                )
            except NoFaceInImageError:
                flash(f"No face detected in that photo. Try a clearer front-facing shot.", "error")
                return redirect(url_for("index"))
            except ValueError as exc:
                flash(f"Could not add {name}: {exc}", "error")
                return redirect(url_for("index"))

        flash(f"{name} added.", "success")
        return redirect(url_for("index"))

    @app.route("/people/update", methods=["POST"])
    def update_person_route():
        name = (request.form.get("name") or "").strip()
        if not name:
            flash("Name is required.", "error")
            return redirect(url_for("index"))
        try:
            updated = update_person_metadata(
                name,
                app.config["PEOPLE_DB_PATH"],
                language=request.form.get("language"),
                birthday=request.form.get("birthday"),
                custom_message=request.form.get("custom_message"),
                flavor=[
                    line.strip()
                    for line in (request.form.get("flavor") or "").splitlines()
                    if line.strip()
                ],
            )
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("index"))
        if updated:
            flash(f"{name} updated.", "success")
        else:
            flash(f"{name} is not registered.", "error")
        return redirect(url_for("index"))

    @app.route("/people/capture", methods=["POST"])
    def capture_person_route():
        name = (request.form.get("name") or "").strip()
        if not name:
            flash("Name is required.", "error")
            return redirect(url_for("index"))
        try:
            with tempfile.TemporaryDirectory(prefix="webapp-capture-person-") as tmp:
                frame_path = capture_frame_to_file(
                    app.config["CAMERA_DEVICE_INDEX"],
                    Path(tmp) / "capture.jpg",
                    backend=app.config["CAMERA_BACKEND"],
                )
                add_person(
                    name,
                    frame_path,
                    app.config["PEOPLE_DB_PATH"],
                    app.config["FACES_FOLDER"],
                    language=request.form.get("language"),
                    birthday=request.form.get("birthday"),
                    custom_message=request.form.get("custom_message"),
                    flavor=[
                        line.strip()
                        for line in (request.form.get("flavor") or "").splitlines()
                        if line.strip()
                    ],
                )
        except CameraCaptureError as exc:
            flash(f"Camera capture failed: {exc}", "error")
            return redirect(url_for("index"))
        except NoFaceInImageError:
            flash("No face detected in the captured frame.", "error")
            return redirect(url_for("index"))
        except ValueError as exc:
            flash(f"Could not add {name}: {exc}", "error")
            return redirect(url_for("index"))

        flash(f"{name} captured from camera and added.", "success")
        return redirect(url_for("index"))

    @app.route("/people/delete", methods=["POST"])
    def delete_person():
        name = (request.form.get("name") or "").strip()
        if not name:
            flash("Name is required.", "error")
            return redirect(url_for("index"))
        registry = load_registry(app.config["PEOPLE_DB_PATH"])
        if name not in registry.names:
            flash(f"{name} is not registered.", "error")
            return redirect(url_for("index"))
        removed = remove_person(
            name,
            app.config["PEOPLE_DB_PATH"],
            app.config["FACES_FOLDER"],
        )
        if removed:
            flash(f"{name} removed.", "success")
        else:
            flash(f"{name} is not registered.", "error")
        return redirect(url_for("index"))

    @app.route("/videos/add", methods=["POST"])
    def add_video_route():
        upload = request.files.get("video")
        if upload is None or not upload.filename:
            flash("A video file is required.", "error")
            return redirect(url_for("index"))

        filename = Path(upload.filename).name
        suffix = Path(filename).suffix.lower()
        if suffix not in SUPPORTED_VIDEO_EXTENSIONS:
            flash("Unsupported video format. Use .mp4, .mov, or .webm.", "error")
            return redirect(url_for("index"))

        with tempfile.TemporaryDirectory(prefix="webapp-add-video-") as tmp:
            tmp_path = Path(tmp) / filename
            upload.save(tmp_path)
            try:
                add_video(tmp_path, app.config["VIDEO_FOLDER"])
            except UnsupportedVideoFormatError as exc:
                flash(f"Unsupported video format: {exc.extension}.", "error")
                return redirect(url_for("index"))
            except FileNotFoundError:
                flash("Upload failed before write.", "error")
                return redirect(url_for("index"))

        count = len(scan_playlist(app.config["VIDEO_FOLDER"]))
        flash(f"{filename} added. Playlist now has {count} videos.", "success")
        return redirect(url_for("index"))

    @app.route("/videos/delete", methods=["POST"])
    def delete_video_route():
        filename = (request.form.get("filename") or "").strip()
        if not filename:
            flash("Filename is required.", "error")
            return redirect(url_for("index"))
        removed = remove_video(filename, app.config["VIDEO_FOLDER"])
        if removed:
            count = len(scan_playlist(app.config["VIDEO_FOLDER"]))
            flash(f"{filename} removed. Playlist now has {count} videos.", "success")
        else:
            flash(f"{filename} is not in the playlist.", "error")
        return redirect(url_for("index"))

    return app


def main() -> int:
    config = load_config()
    app = create_app(config)
    # Quiet Werkzeug's default request logging — supervisor captures stdout.
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    print(f"WEBAPP_READY http://{HOST}:{PORT}", flush=True)
    app.run(host=HOST, port=PORT, debug=False, use_reloader=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
