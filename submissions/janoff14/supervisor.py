"""Runtime supervisor for player, recognition worker, and bot stub."""

from __future__ import annotations

import contextlib
import multiprocessing
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO

REPO_ROOT = Path(__file__).resolve().parent
WORKER_JOIN_TIMEOUT_S = 5
BOT_JOIN_TIMEOUT_S = 5
MONITOR_INTERVAL_S = 1
COMPONENT_LOGS = ("player", "worker", "bot", "webapp", "supervisor")
WEBAPP_JOIN_TIMEOUT_S = 5
PLAYER_JOIN_TIMEOUT_S = 5


@dataclass
class WorkerHandle:
    process: multiprocessing.Process
    stop_event: Any


@dataclass
class PlayerHandle:
    process: multiprocessing.Process


@dataclass
class BotHandle:
    process: subprocess.Popen
    log_handle: TextIO


@dataclass
class WebappHandle:
    process: subprocess.Popen
    log_handle: TextIO


def _log_dir(config: dict[str, Any]) -> Path:
    log_dir = Path(config.get("log_directory", "logs"))
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def append_supervisor_log(log_dir: Path, message: str) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with (log_dir / "supervisor.log").open("a", encoding="utf-8") as handle:
        handle.write(f"[{stamp}] {message}\n")


def _worker_entrypoint(
    config: dict[str, Any],
    stop_event,
    greeting_queue,
    debug_camera_queue,
    log_path: str,
) -> int:
    from recognition.worker import run as run_worker

    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", buffering=1) as handle, \
         contextlib.redirect_stdout(handle), \
         contextlib.redirect_stderr(handle):
        print("WORKER_STARTING", flush=True)
        return run_worker(config, stop_event, greeting_queue, debug_camera_queue)


def start_recognition_worker(
    config: dict[str, Any],
    greeting_queue,
    debug_camera_queue=None,
    log_dir: Path | None = None,
) -> WorkerHandle:
    log_dir = log_dir or _log_dir(config)
    stop_event = multiprocessing.Event()
    process = multiprocessing.Process(
        target=_worker_entrypoint,
        args=(config, stop_event, greeting_queue, debug_camera_queue, str(log_dir / "worker.log")),
        name="recognition-worker",
    )
    process.start()
    append_supervisor_log(log_dir, f"Started worker pid={process.pid}")
    return WorkerHandle(process=process, stop_event=stop_event)


def _player_entrypoint(
    config: dict[str, Any],
    greeting_queue,
    debug_camera_queue,
    log_path: str,
) -> int:
    from player.main import run_player

    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", buffering=1) as handle, \
         contextlib.redirect_stdout(handle), \
         contextlib.redirect_stderr(handle):
        print("PLAYER_STARTING", flush=True)
        return run_player(
            config,
            greeting_queue=greeting_queue,
            debug_camera_queue=debug_camera_queue,
        )


def start_player_process(
    config: dict[str, Any],
    greeting_queue,
    debug_camera_queue=None,
    log_dir: Path | None = None,
) -> PlayerHandle:
    log_dir = log_dir or _log_dir(config)
    process = multiprocessing.Process(
        target=_player_entrypoint,
        args=(config, greeting_queue, debug_camera_queue, str(log_dir / "player.log")),
        name="kiosk-player",
    )
    process.start()
    append_supervisor_log(log_dir, f"Started player pid={process.pid}")
    return PlayerHandle(process=process)


def stop_player_process(handle: PlayerHandle | None) -> None:
    if handle is None:
        return
    if handle.process.is_alive():
        handle.process.terminate()
        handle.process.join(timeout=PLAYER_JOIN_TIMEOUT_S)
    if handle.process.is_alive():
        handle.process.kill()
        handle.process.join(timeout=PLAYER_JOIN_TIMEOUT_S)


def stop_recognition_worker(handle: WorkerHandle | None) -> None:
    if handle is None:
        return
    handle.stop_event.set()
    handle.process.join(timeout=WORKER_JOIN_TIMEOUT_S)
    if handle.process.is_alive():
        handle.process.terminate()
        handle.process.join(timeout=WORKER_JOIN_TIMEOUT_S)


def start_bot_process(
    log_dir: Path,
    python_executable: str | None = None,
    repo_root: Path = REPO_ROOT,
    bot_script: Path | None = None,
) -> BotHandle:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_handle = (log_dir / "bot.log").open("a", encoding="utf-8", buffering=1)
    script = bot_script or (repo_root / "bot.py")
    process = subprocess.Popen(
        [python_executable or sys.executable, str(script)],
        cwd=str(repo_root),
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
    )
    append_supervisor_log(log_dir, f"Started bot pid={process.pid}")
    return BotHandle(process=process, log_handle=log_handle)


def stop_bot_process(handle: BotHandle | None) -> None:
    if handle is None:
        return
    if not handle.log_handle.closed:
        handle.log_handle.flush()
        handle.log_handle.close()
    if handle.process.poll() is None:
        handle.process.terminate()
        try:
            handle.process.wait(timeout=BOT_JOIN_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            handle.process.kill()
            handle.process.wait(timeout=BOT_JOIN_TIMEOUT_S)
    # Windows can release redirected stdout/stderr handles a beat after
    # process wait() returns; give temp-file cleanup and restarts room.
    time.sleep(0.2)


def start_webapp_process(
    log_dir: Path,
    python_executable: str | None = None,
    repo_root: Path = REPO_ROOT,
    webapp_script: Path | None = None,
) -> WebappHandle:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_handle = (log_dir / "webapp.log").open("a", encoding="utf-8", buffering=1)
    script = webapp_script or (repo_root / "webapp.py")
    process = subprocess.Popen(
        [python_executable or sys.executable, str(script)],
        cwd=str(repo_root),
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
    )
    append_supervisor_log(log_dir, f"Started webapp pid={process.pid}")
    return WebappHandle(process=process, log_handle=log_handle)


def stop_webapp_process(handle: WebappHandle | None) -> None:
    if handle is None:
        return
    if not handle.log_handle.closed:
        handle.log_handle.flush()
        handle.log_handle.close()
    if handle.process.poll() is None:
        handle.process.terminate()
        try:
            handle.process.wait(timeout=WEBAPP_JOIN_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            handle.process.kill()
            handle.process.wait(timeout=WEBAPP_JOIN_TIMEOUT_S)
    time.sleep(0.2)


def wait_for_log_text(path: Path, text: str, timeout_s: float = 5.0) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if path.exists() and text in path.read_text(encoding="utf-8", errors="replace"):
            return True
        time.sleep(0.1)
    return False


def _tail_lines(path: Path, line_count: int) -> list[str]:
    if not path.exists():
        return ["<missing>"]
    return path.read_text(encoding="utf-8", errors="replace").splitlines()[-line_count:]


def format_log_tail(log_dir: Path, line_count: int = 20) -> str:
    blocks: list[str] = []
    for component in COMPONENT_LOGS:
        path = log_dir / f"{component}.log"
        blocks.append(f"== {component}.log ==")
        blocks.extend(_tail_lines(path, line_count))
    return "\n".join(blocks)


def print_log_tail(log_dir: Path, line_count: int = 20) -> None:
    print(format_log_tail(log_dir, line_count=line_count), flush=True)


class ComponentSupervisor:
    """Supervise background components while the Qt player runs in main."""

    def __init__(
        self,
        config: dict[str, Any],
        greeting_queue,
        debug_camera_queue=None,
        start_monitor_thread: bool = True,
    ) -> None:
        self.config = config
        self.greeting_queue = greeting_queue
        self.debug_camera_queue = debug_camera_queue
        self.log_dir = _log_dir(config)
        self.player: PlayerHandle | None = None
        self.worker: WorkerHandle | None = None
        self.bot: BotHandle | None = None
        self.webapp: WebappHandle | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._start_monitor_thread = start_monitor_thread
        self.requested_exit_code: int | None = None

    def start(self) -> None:
        append_supervisor_log(self.log_dir, "Supervisor starting")
        self.worker = start_recognition_worker(
            self.config,
            self.greeting_queue,
            self.debug_camera_queue,
            log_dir=self.log_dir,
        )
        self.player = start_player_process(
            self.config,
            self.greeting_queue,
            self.debug_camera_queue,
            log_dir=self.log_dir,
        )
        self.bot = start_bot_process(self.log_dir)
        self.webapp = start_webapp_process(self.log_dir)
        if self._start_monitor_thread:
            self._thread = threading.Thread(target=self._monitor_loop, name="component-supervisor", daemon=True)
            self._thread.start()

    def tick(self) -> None:
        if self.player is not None and self.player.process.exitcode is not None:
            exitcode = self.player.process.exitcode
            if exitcode == 0:
                append_supervisor_log(self.log_dir, "Player exited cleanly; shutting down")
                self.requested_exit_code = 0
                self._stop.set()
                return
            append_supervisor_log(self.log_dir, f"Restarting player after exit code {exitcode}")
            old_player = self.player
            stop_player_process(old_player)
            self.player = start_player_process(
                self.config,
                self.greeting_queue,
                self.debug_camera_queue,
                log_dir=self.log_dir,
            )

        if self.worker is not None and self.worker.process.exitcode is not None:
            exitcode = self.worker.process.exitcode
            append_supervisor_log(self.log_dir, f"Restarting worker after exit code {exitcode}")
            old_worker = self.worker
            stop_recognition_worker(old_worker)
            self.worker = start_recognition_worker(
                self.config,
                self.greeting_queue,
                self.debug_camera_queue,
                log_dir=self.log_dir,
            )

        if self.bot is not None:
            returncode = self.bot.process.poll()
            if returncode is not None:
                append_supervisor_log(self.log_dir, f"Restarting bot after exit code {returncode}")
                old_bot = self.bot
                stop_bot_process(old_bot)
                self.bot = start_bot_process(self.log_dir)

        if self.webapp is not None:
            returncode = self.webapp.process.poll()
            if returncode is not None:
                append_supervisor_log(self.log_dir, f"Restarting webapp after exit code {returncode}")
                old_webapp = self.webapp
                stop_webapp_process(old_webapp)
                self.webapp = start_webapp_process(self.log_dir)

    def _monitor_loop(self) -> None:
        while not self._stop.wait(MONITOR_INTERVAL_S):
            self.tick()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=MONITOR_INTERVAL_S + 1)
        stop_player_process(self.player)
        stop_recognition_worker(self.worker)
        stop_bot_process(self.bot)
        stop_webapp_process(self.webapp)
        append_supervisor_log(self.log_dir, "Supervisor stopped")
