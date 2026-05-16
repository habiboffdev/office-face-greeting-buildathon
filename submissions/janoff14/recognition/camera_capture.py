"""Capture a still frame from the local camera for enrollment flows."""

from __future__ import annotations

from pathlib import Path

import cv2


class CameraCaptureError(RuntimeError):
    """Raised when a still image cannot be captured from the camera."""


def _backend_flag(backend: str | None) -> int | None:
    value = (backend or "dshow").strip().lower()
    if value in {"", "auto", "default"}:
        return None
    if value in {"dshow", "directshow"}:
        return cv2.CAP_DSHOW
    if value == "msmf":
        return cv2.CAP_MSMF
    return None


def capture_frame_to_file(
    camera_index: int,
    output_path: Path,
    *,
    backend: str | None = "dshow",
    warmup_frames: int = 8,
) -> Path:
    """Capture one frame from ``camera_index`` and write it to ``output_path``."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    backend_flag = _backend_flag(backend)
    if backend_flag is None:
        capture = cv2.VideoCapture(int(camera_index))
    else:
        capture = cv2.VideoCapture(int(camera_index), backend_flag)
    try:
        if not capture.isOpened():
            raise CameraCaptureError(f"camera {camera_index} is not available")
        frame = None
        for _ in range(max(1, warmup_frames)):
            ok, frame = capture.read()
            if not ok:
                frame = None
        if frame is None:
            raise CameraCaptureError("camera did not return a frame")
        if not cv2.imwrite(str(output_path), frame):
            raise CameraCaptureError(f"could not write captured frame to {output_path}")
    finally:
        capture.release()
    return output_path
