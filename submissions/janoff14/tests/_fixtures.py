"""Lazy fixture builder for recognition tests.

Real face photos live in ``faces/`` which is gitignored (privacy). On
machines where a face is present we build a one-person ``people.json``
fixture on the fly; on clean clones (CI, fresh installs) we return None
so individual tests can skip cleanly with ``unittest.SkipTest``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures"
FIXTURE_DIR.mkdir(exist_ok=True)

FIXTURE_PEOPLE = FIXTURE_DIR / "people.json"
FIXTURE_PROBE = FIXTURE_DIR / "probe.jpg"

DEFAULT_FIXTURE_NAME = "Operator"


def _first_face_photo() -> Optional[Path]:
    faces_dir = REPO_ROOT / "faces"
    if not faces_dir.is_dir():
        return None
    for entry in sorted(faces_dir.iterdir()):
        if entry.is_file() and entry.suffix.lower() in {".jpg", ".jpeg", ".png"}:
            return entry
    return None


def ensure_one_person_fixture(name: str = DEFAULT_FIXTURE_NAME) -> Optional[Path]:
    """Build ``tests/fixtures/people.json`` from a local face photo.

    Returns the fixture path if successful, ``None`` if no face photo
    exists or the photo doesn't yield a detectable face — caller should
    skip the integration test in either case.
    """
    if FIXTURE_PEOPLE.exists() and FIXTURE_PROBE.exists():
        return FIXTURE_PEOPLE

    source = _first_face_photo()
    if source is None:
        return None

    # Lazy import — the registry tests don't need face_recognition.
    import cv2
    import face_recognition

    image = cv2.imread(str(source))
    if image is None:
        return None
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    locations = face_recognition.face_locations(rgb, model="hog")
    if not locations:
        return None
    encodings = face_recognition.face_encodings(rgb, locations)
    if not encodings:
        return None

    payload = {"people": [{"name": name, "encoding": encodings[0].tolist()}]}
    FIXTURE_PEOPLE.write_text(json.dumps(payload), encoding="utf-8")
    # Copy the source photo so the probe test has a face guaranteed to match.
    FIXTURE_PROBE.write_bytes(source.read_bytes())
    return FIXTURE_PEOPLE
