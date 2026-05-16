from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

warnings.filterwarnings(
    "ignore",
    message="pkg_resources is deprecated as an API.*",
    category=UserWarning,
)

import cv2
import dlib  # noqa: F401 - importing proves dlib-bin exposes the expected module.
import face_recognition
import face_recognition_models


def fail(message: str) -> int:
    print(f"ERROR: {message}", file=sys.stderr)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify dlib/face_recognition can detect a face and produce a 128D embedding."
    )
    parser.add_argument(
        "image",
        help="Path to a local face image (clear front-facing).",
    )
    args = parser.parse_args()

    image_path = Path(args.image)
    if not image_path.exists():
        return fail(f"image file not found: {image_path}")

    image = cv2.imread(str(image_path))
    if image is None:
        return fail(f"image file unreadable: {image_path}")

    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    locations = face_recognition.face_locations(rgb)
    if not locations:
        return fail(f"no face detected in {image_path}. Use a clearer front-facing face image.")

    encodings = face_recognition.face_encodings(rgb, locations)
    if not encodings:
        return fail(f"no face encodings produced for {image_path}")

    embedding_dim = len(encodings[0])
    if embedding_dim != 128:
        return fail(f"unexpected embedding dimension: {embedding_dim}; expected 128")

    face_recognition_models.face_recognition_model_location()
    print(f"OK: faces={len(locations)} embedding_dim={embedding_dim}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
