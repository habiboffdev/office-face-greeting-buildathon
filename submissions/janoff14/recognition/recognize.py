"""Single-frame recognize() — pure compute kernel.

Contract:
* Input: ``frame`` is a BGR ``np.uint8`` array (OpenCV default). The worker
  in Story 2.3 should downsample to 320×240 before calling, per AR8.
* Output: matched name (``str``) or ``None``.
* HOG detection only (CPU, NFR19 — no GPU dependency).
* Multi-face tie-break by largest bounding-box area. If the *largest*
  face is unknown, the function returns ``None`` rather than falling
  through to a smaller registered face — the product rule (PRD §1) is
  that the closest visitor wins, so a known face in the background must
  not steal the greeting.
"""

from __future__ import annotations

from typing import Optional

import cv2
import face_recognition
import numpy as np

from recognition.registry import Registry


def recognize_dual(
    frame: np.ndarray,
    registry: Registry,
    tolerance: float = 0.5,
    detect_width: int = 320,
) -> Optional[str]:
    """Detect on a downsampled copy, embed on the native crop.

    Production path used by the recognition worker (Story 2.3). The
    downsample makes HOG fast; the native-resolution embedding keeps
    accuracy high for small faces in large frames. Per AR8.
    """
    if registry.encodings.shape[0] == 0:
        return None

    native_h, native_w = frame.shape[:2]
    if native_w <= 0:
        return None

    if native_w <= detect_width:
        # Frame is already small enough — fall back to single-resolution path.
        return recognize(frame, registry, tolerance)

    scale = detect_width / native_w
    small_h = max(1, int(round(native_h * scale)))
    small = cv2.resize(frame, (detect_width, small_h), interpolation=cv2.INTER_AREA)
    small_rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
    locations = face_recognition.face_locations(small_rgb, model="hog")
    if not locations:
        return None

    locations.sort(
        key=lambda box: (box[2] - box[0]) * (box[1] - box[3]),
        reverse=True,
    )
    top, right, bottom, left = locations[0]
    # Scale back to native coordinates.
    native_box = (
        int(top / scale),
        int(right / scale),
        int(bottom / scale),
        int(left / scale),
    )
    native_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    encodings = face_recognition.face_encodings(native_rgb, [native_box])
    if not encodings:
        return None

    distances = face_recognition.face_distance(registry.encodings, encodings[0])
    best_index = int(np.argmin(distances))
    if distances[best_index] <= tolerance:
        return registry.names[best_index]
    return None


def recognize(
    frame: np.ndarray,
    registry: Registry,
    tolerance: float = 0.5,
) -> Optional[str]:
    if registry.encodings.shape[0] == 0:
        return None

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    locations = face_recognition.face_locations(rgb, model="hog")
    if not locations:
        return None

    # Largest face by bounding-box area — closest to the camera.
    locations_sorted = sorted(
        locations,
        key=lambda box: (box[2] - box[0]) * (box[1] - box[3]),
        reverse=True,
    )
    largest = [locations_sorted[0]]

    encodings = face_recognition.face_encodings(rgb, largest)
    if not encodings:
        return None

    probe = encodings[0]
    distances = face_recognition.face_distance(registry.encodings, probe)
    best_index = int(np.argmin(distances))
    if distances[best_index] <= tolerance:
        return registry.names[best_index]
    return None
