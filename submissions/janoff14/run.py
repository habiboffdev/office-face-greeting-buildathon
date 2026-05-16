"""Kiosk entry point and Story 3.1 component supervisor launcher."""

from __future__ import annotations

import argparse
import multiprocessing
import sys
import time
from pathlib import Path
from typing import Any

import yaml

from supervisor import (
    COMPONENT_LOGS,
    ComponentSupervisor,
    append_supervisor_log,
    format_log_tail,
)

REPO_ROOT = Path(__file__).resolve().parent
CONFIG_PATH = REPO_ROOT / "config.yaml"
EXAMPLE_CONFIG_PATH = REPO_ROOT / "config.yaml.example"
GREETING_QUEUE_MAXSIZE = 8
DEBUG_CAMERA_QUEUE_MAXSIZE = 2


def load_config() -> dict[str, Any]:
    """Load ``config.yaml`` if present, otherwise fall back to the example."""
    path = CONFIG_PATH if CONFIG_PATH.exists() else EXAMPLE_CONFIG_PATH
    if path is EXAMPLE_CONFIG_PATH:
        print(
            f"WARNING: {CONFIG_PATH.name} not found; using {EXAMPLE_CONFIG_PATH.name} defaults",
            file=sys.stderr,
        )
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the kiosk supervisor.")
    parser.add_argument(
        "--tail-logs",
        action="store_true",
        help="Print recent player/worker/bot/supervisor logs and exit.",
    )
    parser.add_argument("--tail-lines", type=int, default=20)
    return parser.parse_args(argv)


def _log_dir(config: dict[str, Any]) -> Path:
    log_dir = Path(config.get("log_directory", "logs"))
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def _close_queue(q) -> None:
    if q is None:
        return
    q.close()
    q.join_thread()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = load_config()
    log_dir = _log_dir(config)

    if args.tail_logs:
        print(format_log_tail(log_dir, line_count=args.tail_lines))
        return 0

    for component in COMPONENT_LOGS:
        (log_dir / f"{component}.log").touch(exist_ok=True)

    greeting_queue = multiprocessing.Queue(maxsize=GREETING_QUEUE_MAXSIZE)
    debug_camera_queue = (
        multiprocessing.Queue(maxsize=DEBUG_CAMERA_QUEUE_MAXSIZE)
        if config.get("debug_camera_overlay", False)
        else None
    )
    component_supervisor = ComponentSupervisor(
        config=config,
        greeting_queue=greeting_queue,
        debug_camera_queue=debug_camera_queue,
    )

    exit_code = 0
    try:
        component_supervisor.start()
        while component_supervisor.requested_exit_code is None:
            time.sleep(0.2)
        exit_code = component_supervisor.requested_exit_code
    except KeyboardInterrupt:
        append_supervisor_log(log_dir, "KeyboardInterrupt received; shutting down")
        exit_code = 130
    finally:
        component_supervisor.stop()
        _close_queue(greeting_queue)
        _close_queue(debug_camera_queue)
    return exit_code


if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
