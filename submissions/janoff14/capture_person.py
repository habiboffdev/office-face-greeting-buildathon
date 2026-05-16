"""Capture a person from the USB camera and add them to people.json."""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

import yaml

from recognition.camera_capture import CameraCaptureError, capture_frame_to_file
from recognition.writer import NoFaceInImageError, add_person

CONFIG_PATH = Path("config.yaml")
EXAMPLE_CONFIG_PATH = Path("config.yaml.example")


def _load_config() -> dict:
    path = CONFIG_PATH if CONFIG_PATH.exists() else EXAMPLE_CONFIG_PATH
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Capture a camera still and register a person.")
    parser.add_argument("name", help="Person name to register")
    parser.add_argument("--language", choices=["en", "uz", "ru"], default=None)
    parser.add_argument("--birthday", default=None, help="Optional MM-DD birthday")
    parser.add_argument("--custom-message", default=None)
    parser.add_argument("--camera", type=int, default=None)
    args = parser.parse_args(argv)

    cfg = _load_config()
    camera_index = args.camera if args.camera is not None else int(cfg.get("camera_device_index", 0))
    people_db_path = Path(cfg.get("people_db_path", "people.json"))
    faces_folder = Path(cfg.get("faces_folder", "faces"))

    try:
        with tempfile.TemporaryDirectory(prefix="capture-person-") as tmp:
            frame_path = capture_frame_to_file(camera_index, Path(tmp) / "capture.jpg")
            add_person(
                args.name,
                frame_path,
                people_db_path,
                faces_folder,
                language=args.language,
                birthday=args.birthday,
                custom_message=args.custom_message,
            )
    except CameraCaptureError as exc:
        print(f"CAMERA_ERROR {exc}", file=sys.stderr)
        return 2
    except NoFaceInImageError:
        print("NO_FACE detected in captured frame", file=sys.stderr)
        return 3
    except Exception as exc:
        print(f"ADD_PERSON_ERROR {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print(f"{args.name} added from camera {camera_index}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
