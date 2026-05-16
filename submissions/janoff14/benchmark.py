"""benchmark.py — recognition accuracy + latency self-test (Story 4.3).

Run::

    python benchmark.py

Reads ``people.json`` (the seed registry), runs each registered person's
probe photo through ``recognition.recognize.recognize_dual`` 10 times to
build the latency distribution, then runs the stranger control set 10
times each. Reports TPR / FPR / p50 / p95 in a fixed format ready for
direct README inclusion.

No camera, no player, no supervisor required. Works offline.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Callable, Iterable

import cv2
import numpy as np

from bot import load_config
from recognition.recognize import recognize_dual
from recognition.registry import EMBEDDING_DIM, Registry, load_registry
from recognition.writer import _safe_name

ATTEMPTS_PER_PERSON = 10
ATTEMPTS_PER_STRANGER = 10
CAPACITY_TARGET = 200
CAPACITY_SAMPLE_CALLS = 5

DEFAULT_SEED_FOLDER = Path("tests/seed")
DEFAULT_STRANGERS_FOLDER = Path("tests/strangers")

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png")


# ---------- pure helpers (testable without face_recognition) ----------


def percentile(values_s: list[float], p: float) -> float:
    if not values_s:
        return 0.0
    return float(np.percentile(values_s, p))


def format_report(
    *,
    p50_s: float,
    p95_s: float,
    tp: int,
    total_pos: int,
    fp: int,
    total_neg: int,
    tolerance: float,
    seed_people: int,
    attempts_per_person: int,
    strangers_count: int,
    attempts_per_stranger: int,
) -> str:
    tpr_pct = round((tp / total_pos * 100) if total_pos else 0.0)
    fpr_pct = (fp / total_neg * 100) if total_neg else 0.0
    return (
        f"Recognition pipeline latency p50: {p50_s:.2f} s, p95: {p95_s:.2f} s\n"
        f"True-positive rate: {tpr_pct}% ({tp}/{total_pos} attempts)\n"
        f"False-positive rate: {fpr_pct:.1f}% ({fp}/{total_neg} attempts)\n"
        f"Tolerance: {tolerance:.2f}\n"
        f"Seed set: {seed_people} people x {attempts_per_person} attempts; "
        f"control set: {strangers_count} strangers x {attempts_per_stranger} attempts"
    )


def compute_violations(tp: int, total_pos: int, fp: int, total_neg: int) -> list[str]:
    violations: list[str] = []
    if total_pos > 0:
        tpr = tp / total_pos * 100
        if tpr < 95.0:
            violations.append(f"WARNING: TPR {tpr:.0f}% below NFR10 target of 95%")
    if total_neg > 0 and fp > 0:
        fpr = fp / total_neg * 100
        violations.append(f"WARNING: FPR {fpr:.1f}% violates NFR9 target of 0%")
    return violations


def gather_probe_images_for(
    name: str,
    faces_folder: Path,
    seed_folder: Path | None = None,
) -> list[Path]:
    """Return up to 10 probe paths for *name*.

    Prefers ``seed_folder/<safe>/*.{jpg,jpeg,png}`` (held-out set), falls
    back to ``faces_folder/<safe>.jpg`` (the canonical source photo).
    Returns ``[]`` if nothing is available.
    """
    try:
        safe = _safe_name(name)
    except ValueError:
        return []

    paths: list[Path] = []
    if seed_folder is not None:
        person_dir = Path(seed_folder) / safe
        if person_dir.is_dir():
            for entry in sorted(person_dir.iterdir()):
                if entry.is_file() and entry.suffix.lower() in IMAGE_EXTENSIONS:
                    paths.append(entry)
    if not paths:
        canonical = Path(faces_folder) / f"{safe}.jpg"
        if canonical.is_file():
            paths.append(canonical)
    return paths[:ATTEMPTS_PER_PERSON]


def gather_stranger_images(strangers_folder: Path) -> list[Path]:
    folder = Path(strangers_folder)
    if not folder.is_dir():
        return []
    return sorted(
        entry
        for entry in folder.iterdir()
        if entry.is_file() and entry.suffix.lower() in IMAGE_EXTENSIONS
    )


# ---------- attempt runner (recognize seam) ----------


RecognizeFn = Callable[[np.ndarray, Registry, float], "str | None"]


def _load_image(path: Path) -> np.ndarray | None:
    img = cv2.imread(str(path))
    return img


def _run_attempts(
    probe_paths: list[Path],
    expected_name: str | None,
    registry: Registry,
    tolerance: float,
    recognize_fn: RecognizeFn,
    *,
    attempts: int,
) -> tuple[int, list[float]]:
    """Run *attempts* recognize_fn calls, cycling through probe_paths.

    Returns ``(matches, latencies_s)``. For positive samples,
    *expected_name* is the registered person's name; a match counts when
    the function returns that exact string. For negative samples,
    *expected_name* is None; any non-None return counts as a false positive.
    """
    if not probe_paths:
        return (0, [])

    matches = 0
    latencies: list[float] = []
    for i in range(attempts):
        path = probe_paths[i % len(probe_paths)]
        image = _load_image(path)
        if image is None:
            continue
        start = time.perf_counter()
        result = recognize_fn(image, registry, tolerance)
        latencies.append(time.perf_counter() - start)
        if expected_name is None:
            if result is not None:
                matches += 1  # false positive count
        else:
            if result == expected_name:
                matches += 1
    return matches, latencies


def _pad_registry_for_capacity(registry: Registry, target: int) -> Registry:
    """Return a Registry padded with synthetic embeddings up to *target* rows."""
    current = registry.encodings.shape[0]
    if current >= target:
        return registry
    rng = np.random.default_rng(seed=0)
    extra = target - current
    extra_encodings = rng.standard_normal((extra, EMBEDDING_DIM))
    padded_encodings = np.vstack([registry.encodings, extra_encodings])
    padded_names = list(registry.names) + [f"_synthetic_{i}" for i in range(extra)]
    return Registry(names=padded_names, encodings=padded_encodings)


# ---------- main ----------


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Recognition accuracy + latency benchmark")
    parser.add_argument("--seed-folder", default=str(DEFAULT_SEED_FOLDER))
    parser.add_argument("--strangers-folder", default=str(DEFAULT_STRANGERS_FOLDER))
    args = parser.parse_args(list(argv) if argv is not None else None)

    config = load_config()
    tolerance = float(config.get("recognition_tolerance", 0.5))
    people_db_path = Path(config.get("people_db_path", "people.json"))
    faces_folder = Path(config.get("faces_folder", "faces"))
    seed_folder = Path(args.seed_folder)
    strangers_folder = Path(args.strangers_folder)

    if not people_db_path.exists():
        print(f"Error: people.json not found at {people_db_path}", file=sys.stderr)
        return 2

    registry = load_registry(people_db_path)
    if not registry.names:
        print(
            f"Error: people.json at {people_db_path} has no registered people; "
            "add at least one via /add_person or add_person.py first.",
            file=sys.stderr,
        )
        return 2

    stranger_paths = gather_stranger_images(strangers_folder)
    if not stranger_paths:
        print(
            f"Error: no stranger control images found in {strangers_folder} "
            "(expected .jpg/.png files). Provide an AR12 control set before benchmarking.",
            file=sys.stderr,
        )
        return 2

    total_tp = 0
    total_pos_attempts = 0
    all_latencies: list[float] = []
    missing_probes: list[str] = []

    for name in registry.names:
        probes = gather_probe_images_for(name, faces_folder, seed_folder)
        if not probes:
            missing_probes.append(name)
            continue
        matches, latencies = _run_attempts(
            probes, name, registry, tolerance, recognize_dual,
            attempts=ATTEMPTS_PER_PERSON,
        )
        total_tp += matches
        total_pos_attempts += len(latencies)
        all_latencies.extend(latencies)

    if missing_probes:
        print(
            "Error: no probe images found for: " + ", ".join(missing_probes)
            + f". Place photos in {seed_folder}/<safe-name>/ or {faces_folder}/<safe-name>.jpg.",
            file=sys.stderr,
        )
        return 2

    total_fp = 0
    total_neg_attempts = 0
    for stranger_path in stranger_paths:
        matches, latencies = _run_attempts(
            [stranger_path], None, registry, tolerance, recognize_dual,
            attempts=ATTEMPTS_PER_STRANGER,
        )
        total_fp += matches
        total_neg_attempts += len(latencies)
        all_latencies.extend(latencies)

    p50_s = percentile(all_latencies, 50)
    p95_s = percentile(all_latencies, 95)

    report = format_report(
        p50_s=p50_s,
        p95_s=p95_s,
        tp=total_tp,
        total_pos=total_pos_attempts,
        fp=total_fp,
        total_neg=total_neg_attempts,
        tolerance=tolerance,
        seed_people=len(registry.names),
        attempts_per_person=ATTEMPTS_PER_PERSON,
        strangers_count=len(stranger_paths),
        attempts_per_stranger=ATTEMPTS_PER_STRANGER,
    )
    print(report)

    # Capacity check.
    padded = _pad_registry_for_capacity(registry, CAPACITY_TARGET)
    if padded.encodings.shape[0] > registry.encodings.shape[0]:
        first_probe = gather_probe_images_for(registry.names[0], faces_folder, seed_folder)
        if first_probe:
            _matches, cap_latencies = _run_attempts(
                first_probe, registry.names[0], padded, tolerance, recognize_dual,
                attempts=CAPACITY_SAMPLE_CALLS,
            )
            if cap_latencies:
                cap_p50 = percentile(cap_latencies, 50)
                cap_p95 = percentile(cap_latencies, 95)
                print(
                    f"Capacity ({CAPACITY_TARGET} registered): "
                    f"p50 {cap_p50:.2f} s, p95 {cap_p95:.2f} s"
                )
                if cap_p50 > 1.0 or cap_p95 > 2.0:
                    print(
                        f"WARNING: capacity p50/p95 ({cap_p50:.2f}/{cap_p95:.2f}) "
                        "exceeds NFR1 target (1.0 / 2.0 s)",
                        file=sys.stderr,
                    )

    for warning in compute_violations(total_tp, total_pos_attempts, total_fp, total_neg_attempts):
        print(warning, file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
