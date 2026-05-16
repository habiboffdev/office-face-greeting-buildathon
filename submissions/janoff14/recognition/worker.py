"""Recognition worker — runs in its own OS process.

Story 2.3 scope opened the camera and matched frames. Story 2.4 added the
greeting queue. Story 2.5 adds per-person greeting cooldown. Hot-reload
(Story 3.5) and supervisor restart policy (Story 3.1) are still out of
scope here.

Spawn pattern (Story 3.1 will do this; Story 2.4 already accepts the queue
arg)::

    stop_event = multiprocessing.Event()
    greeting_queue = multiprocessing.Queue(maxsize=8)
    proc = multiprocessing.Process(
        target=recognition.worker.run,
        args=(config_dict, stop_event, greeting_queue),
    )
    proc.start()
    ...
    stop_event.set()
    proc.join(timeout=5)
"""

from __future__ import annotations

import queue
import sys
import time
import multiprocessing
from pathlib import Path
from typing import Optional

import cv2
import face_recognition
import numpy as np

from recognition.hot_reload import PeopleRegistryReloader
from recognition.notifications import append_recognition_event
from recognition.recognize import recognize_dual
from recognition.registry import load_registry

LOOP_SLEEP_ON_EMPTY_S = 0.01
MAX_DRAIN_GRABS = 5
DEFAULT_COOLDOWN_SECONDS = 60.0
DEBUG_FRAME_INTERVAL_S = 0.2
DEBUG_FRAME_WIDTH = 320
CAMERA_REOPEN_AFTER_EMPTY_FRAMES = 120
CAMERA_OPEN_MAX_ATTEMPTS = 20
CAMERA_OPEN_BACKOFF_S = 0.5


def _camera_backend_flag(config: dict) -> int | None:
    """Return an optional cv2 VideoCapture backend flag."""
    backend = str(config.get("camera_backend", "dshow")).strip().lower()
    if backend in {"", "auto", "default"}:
        return None
    if backend in {"dshow", "directshow"}:
        return cv2.CAP_DSHOW
    if backend == "msmf":
        return cv2.CAP_MSMF
    return None


def _open_camera(camera_index: int, config: dict):
    backend = _camera_backend_flag(config)
    if backend is None:
        cap = cv2.VideoCapture(camera_index)
    else:
        cap = cv2.VideoCapture(camera_index, backend)
    try:
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    except Exception:
        pass
    return cap


def _open_camera_with_retry(
    camera_index: int,
    config: dict,
    stop_event=None,
    max_attempts: int = CAMERA_OPEN_MAX_ATTEMPTS,
    backoff_seconds: float = CAMERA_OPEN_BACKOFF_S,
):
    """Open the camera, retrying briefly if the device is still busy.

    A previous worker run that died abruptly may have left the USB camera
    held by the OS for a moment. Retrying with backoff gives Windows time
    to free the handle without the user having to unplug the camera.
    """
    last_cap = None
    for attempt in range(1, max_attempts + 1):
        if stop_event is not None and stop_event.is_set():
            if last_cap is not None:
                last_cap.release()
            return None
        cap = _open_camera(camera_index, config)
        if cap.isOpened():
            if attempt > 1:
                print(
                    f"CAMERA_OPENED on attempt {attempt} after retries",
                    flush=True,
                )
            return cap
        cap.release()
        last_cap = None
        print(
            f"CAMERA_BUSY attempt {attempt}/{max_attempts}; retrying in {backoff_seconds:.1f}s",
            file=sys.stderr,
            flush=True,
        )
        time.sleep(backoff_seconds)
    return None


def _read_latest_frame(cap) -> Optional[np.ndarray]:
    """Drain stale frames via grab(), then decode the freshest one."""
    last_grab_ok = False
    for _ in range(MAX_DRAIN_GRABS):
        if not cap.grab():
            break
        last_grab_ok = True
    if not last_grab_ok:
        return None
    ok, frame = cap.retrieve()
    if not ok or frame is None:
        return None
    return frame


def _should_emit_greeting(
    name: str,
    now: float,
    cooldown_seconds: float,
    last_greeted_at: dict[str, float],
) -> bool:
    """Return True when a greeting event should be emitted for *name*."""
    last_seen = last_greeted_at.get(name)
    if cooldown_seconds > 0 and last_seen is not None and now - last_seen < cooldown_seconds:
        return False
    last_greeted_at[name] = now
    return True


def _encode_debug_frame(frame: np.ndarray) -> bytes | None:
    """Encode a small JPEG preview for the temporary player debug overlay."""
    native_h, native_w = frame.shape[:2]
    if native_w <= 0 or native_h <= 0:
        return None
    scale = min(1.0, DEBUG_FRAME_WIDTH / native_w)
    preview = frame
    if scale < 1.0:
        preview = cv2.resize(
            frame,
            (DEBUG_FRAME_WIDTH, max(1, int(native_h * scale))),
            interpolation=cv2.INTER_AREA,
        )
    ok, encoded = cv2.imencode(".jpg", preview, [int(cv2.IMWRITE_JPEG_QUALITY), 72])
    if not ok:
        return None
    return encoded.tobytes()


def _try_put_debug_event(debug_camera_queue, frame: np.ndarray, lines: list[str]) -> None:
    if debug_camera_queue is None:
        return
    jpeg = _encode_debug_frame(frame)
    if jpeg is None:
        return
    try:
        debug_camera_queue.put_nowait(
            {
                "jpeg": jpeg,
                "lines": lines,
                "timestamp": time.time(),
            }
        )
    except queue.Full:
        pass


def _try_put_greeting_event(greeting_queue, event: dict) -> bool:
    """Queue the newest greeting, dropping one stale event if needed."""
    if greeting_queue is None:
        return False
    try:
        greeting_queue.put_nowait(event)
        return True
    except queue.Full:
        try:
            greeting_queue.get_nowait()
        except queue.Empty:
            return False
        try:
            greeting_queue.put_nowait(event)
            return True
        except queue.Full:
            return False


def _debug_recognition_lines(frame: np.ndarray, registry, tolerance: float) -> list[str]:
    """Return lightweight match diagnostics for the temporary camera overlay."""
    if registry.encodings.shape[0] == 0:
        return ["faces: ?", "best: registry empty"]

    native_h, native_w = frame.shape[:2]
    if native_w <= 0 or native_h <= 0:
        return ["faces: 0", "best: invalid frame"]

    scale = min(1.0, DEBUG_FRAME_WIDTH / native_w)
    probe = frame
    if scale < 1.0:
        probe = cv2.resize(
            frame,
            (DEBUG_FRAME_WIDTH, max(1, int(native_h * scale))),
            interpolation=cv2.INTER_AREA,
        )
    rgb = cv2.cvtColor(probe, cv2.COLOR_BGR2RGB)
    locations = face_recognition.face_locations(rgb, model="hog")
    if not locations:
        return ["faces: 0", "best: none"]

    locations.sort(
        key=lambda box: (box[2] - box[0]) * (box[1] - box[3]),
        reverse=True,
    )
    encodings = face_recognition.face_encodings(rgb, [locations[0]])
    if not encodings:
        return [f"faces: {len(locations)}", "best: no encoding"]

    distances = face_recognition.face_distance(registry.encodings, encodings[0])
    best_index = int(np.argmin(distances))
    best_distance = float(distances[best_index])
    best_name = registry.names[best_index]
    return [
        f"faces: {len(locations)}",
        f"best: {best_name} d={best_distance:.3f} match={best_distance <= tolerance}",
    ]


def run(
    config: dict,
    stop_event=None,
    greeting_queue=None,
    debug_camera_queue=None,
) -> int:
    """Run the recognition loop. Returns the exit code."""
    camera_index = int(config.get("camera_device_index", 0))
    tolerance = float(config.get("recognition_tolerance", 0.5))
    cooldown_seconds = float(config.get("cooldown_seconds", DEFAULT_COOLDOWN_SECONDS))
    people_db_path = Path(config.get("people_db_path", "people.json"))
    parent_process = multiprocessing.parent_process()

    cap = _open_camera_with_retry(camera_index, config, stop_event=stop_event)
    if cap is None or not cap.isOpened():
        print(
            f"ERROR: cannot open camera index {camera_index} after "
            f"{CAMERA_OPEN_MAX_ATTEMPTS} attempts (device still busy?)",
            file=sys.stderr,
        )
        if cap is not None:
            cap.release()
        return 1

    registry = load_registry(people_db_path)
    if registry.encodings.shape[0] == 0:
        print(
            f"WARNING: registry at {people_db_path} is empty; worker will match nothing "
            "until people are added",
            file=sys.stderr,
        )

    last_greeted_at: dict[str, float] = {}
    last_debug_frame_at = 0.0
    empty_frame_count = 0

    reloader = PeopleRegistryReloader(people_db_path)
    reloader.start()

    try:
        while True:
            if parent_process is not None and not parent_process.is_alive():
                return 0
            if stop_event is not None and stop_event.is_set():
                return 0
            if reloader.reload_pending:
                reloader.clear_pending()
                try:
                    registry = load_registry(people_db_path)
                    print(f"REGISTRY_RELOADED count={len(registry.names)}", flush=True)
                except (ValueError, OSError) as exc:
                    print(
                        f"REGISTRY_RELOAD_FAILED {type(exc).__name__}: {exc}",
                        file=sys.stderr,
                        flush=True,
                    )
            frame = _read_latest_frame(cap)
            if frame is None:
                empty_frame_count += 1
                if empty_frame_count >= CAMERA_REOPEN_AFTER_EMPTY_FRAMES:
                    print("CAMERA_REOPEN after repeated empty frames", file=sys.stderr, flush=True)
                    cap.release()
                    time.sleep(0.25)
                    reopened = _open_camera_with_retry(
                        camera_index, config, stop_event=stop_event
                    )
                    cap = reopened if reopened is not None else _open_camera(camera_index, config)
                    empty_frame_count = 0
                time.sleep(LOOP_SLEEP_ON_EMPTY_S)
                continue
            empty_frame_count = 0
            name = recognize_dual(frame, registry, tolerance)
            now = time.time()
            lines = [
                f"camera {camera_index} | tol {tolerance:.2f} | cooldown {cooldown_seconds:.0f}s",
                f"registry {len(registry.names)} people",
            ]
            should_send_debug = now - last_debug_frame_at >= DEBUG_FRAME_INTERVAL_S
            if debug_camera_queue is not None and should_send_debug:
                lines.extend(_debug_recognition_lines(frame, registry, tolerance))
            if name is None:
                lines.append("match: none")
                if should_send_debug:
                    _try_put_debug_event(debug_camera_queue, frame, lines)
                    last_debug_frame_at = now
                continue
            print(f"MATCH: {name}", flush=True)
            lines.append(f"match: {name}")
            if not _should_emit_greeting(name, now, cooldown_seconds, last_greeted_at):
                lines.append("greeting: suppressed by cooldown")
                if should_send_debug:
                    _try_put_debug_event(debug_camera_queue, frame, lines)
                    last_debug_frame_at = now
                continue

            log_dir = Path(config.get("log_directory", "logs"))
            append_recognition_event(log_dir, name, now)
            lines.append("notification: emitted")

            if greeting_queue is not None:
                try:
                    flavors: list[str] = []
                    language = "en"
                    birthday = ""
                    custom_message = ""
                    try:
                        idx = registry.names.index(name)
                        if idx < len(registry.flavors):
                            flavors = list(registry.flavors[idx])
                        if idx < len(registry.languages):
                            language = registry.languages[idx]
                        if idx < len(registry.birthdays):
                            birthday = registry.birthdays[idx]
                        if idx < len(registry.custom_messages):
                            custom_message = registry.custom_messages[idx]
                    except (ValueError, AttributeError):
                        flavors = []
                    event = {
                        "name": name,
                        "timestamp": now,
                        "flavors": flavors,
                        "language": language,
                        "birthday": birthday,
                        "custom_message": custom_message,
                    }
                    if _try_put_greeting_event(greeting_queue, event):
                        lines.append("greeting: emitted")
                    else:
                        lines.append("greeting: dropped; queue full")
                except Exception as exc:
                    lines.append(f"greeting: failed {type(exc).__name__}")
            else:
                lines.append("greeting: no queue")
            if should_send_debug:
                _try_put_debug_event(debug_camera_queue, frame, lines)
                last_debug_frame_at = now
    finally:
        reloader.stop()
        cap.release()


def _load_config_from_disk() -> dict:
    """Load config.yaml or fall back to the example template."""
    import yaml

    repo_root = Path(__file__).resolve().parent.parent
    config_path = repo_root / "config.yaml"
    example_path = repo_root / "config.yaml.example"
    path = config_path if config_path.exists() else example_path
    if path is example_path:
        print(
            f"WARNING: {config_path.name} not found; using {example_path.name} defaults",
            file=sys.stderr,
        )
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


if __name__ == "__main__":
    raise SystemExit(run(_load_config_from_disk()))
