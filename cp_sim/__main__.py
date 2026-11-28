"""Command-line lifecycle management for cp-sim."""
from __future__ import annotations

import argparse
import logging
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

from .config import (
    HOST, LOG_FILE_PATH, MARKDOWN_REPORT_PATH, PID_FILE_PATH, PORT, ROOT,
    CpSimError, load_config, load_user_lists, module_directory,
)
from .environment import require_vm
from .modules import apply_fixes, apply_setups
from .reports import (
    write_answer_key, write_desktop_launcher, write_markdown_scoring_report,
    write_module_readme, write_scoring_report,
)
from .web import app

logger = logging.getLogger("cp-sim")


def validate_project() -> list[str]:
    require_vm()
    modules = load_config()
    for name in modules:
        module_directory(name)
    if "users" in modules:
        load_user_lists()
    return modules


def prepare_artifacts(modules: list[str]) -> None:
    write_module_readme(modules)
    write_answer_key(modules)
    write_scoring_report()
    write_desktop_launcher()


def _read_server_pid() -> int | None:
    try:
        raw = PID_FILE_PATH.read_text(encoding="ascii").strip()
        pid = int(raw)
        return pid if pid > 1 else None
    except (OSError, ValueError):
        return None


def _is_cp_sim_process(pid: int) -> bool:
    try:
        command = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode()
    except OSError:
        return False
    return "-m cp_sim" in command and "--serve" in command


def start_server() -> int:
    existing = _read_server_pid()
    if existing and _is_cp_sim_process(existing):
        logger.info("Flask server is already running (PID %s).", existing)
        print(f"Scoring report: http://{HOST}:{PORT}/")
        return 0
    if PID_FILE_PATH.exists():
        PID_FILE_PATH.unlink()

    command = [sys.executable, "-m", "cp_sim", "--serve"]
    with LOG_FILE_PATH.open("a", encoding="utf-8") as log_file:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            close_fds=True,
        )
    PID_FILE_PATH.write_text(f"{process.pid}\n", encoding="ascii")
    deadline = time.monotonic() + 8
    ready = False
    while time.monotonic() < deadline:
        if process.poll() is not None:
            break
        try:
            with socket.create_connection((HOST, PORT), timeout=0.25):
                ready = True
                break
        except OSError:
            time.sleep(0.2)
    if not ready:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
        PID_FILE_PATH.unlink(missing_ok=True)
        logger.error("Flask server did not become ready. See %s.", LOG_FILE_PATH)
        return 1
    logger.info("Started Flask server in the background (PID %s).", process.pid)
    logger.info("Progress tracking is active through the live scoring page and /api/scores.")
    print(f"Scoring report: http://{HOST}:{PORT}/")
    print(f"Server PID: {process.pid}")
    return 0


def stop_server() -> int:
    pid = _read_server_pid()
    if pid is None:
        PID_FILE_PATH.unlink(missing_ok=True)
        logger.info("No running cp-sim server was recorded.")
        return 0
    if not _is_cp_sim_process(pid):
        PID_FILE_PATH.unlink(missing_ok=True)
        logger.warning("Removed stale PID file; PID %s is not a cp-sim server.", pid)
        return 0
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        PID_FILE_PATH.unlink(missing_ok=True)
        logger.info("Flask server was already stopped.")
        return 0
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            PID_FILE_PATH.unlink(missing_ok=True)
            logger.info("Stopped Flask server (PID %s).", pid)
            return 0
        time.sleep(0.2)
    logger.error("Flask server PID %s did not exit after SIGTERM; PID file was retained.", pid)
    return 1


def serve() -> int:
    modules = validate_project()
    prepare_artifacts(modules)
    logger.info("Flask scoring server listening at http://%s:%s/.", HOST, PORT)
    app.run(host=HOST, port=PORT, debug=False, threaded=True, use_reloader=False)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="CyberPatriot practice and scoring simulator.")
    actions = parser.add_mutually_exclusive_group(required=False)
    actions.add_argument("--setup", action="store_true", help="prepare the configured practice state; do not start Flask")
    actions.add_argument("--start", action="store_true", help="start Flask in the background and track scoring progress")
    actions.add_argument("--stop", action="store_true", help="stop the background Flask server")
    actions.add_argument("--fix", action="store_true", help="run the existing confirmed vulnerability remediation scripts")
    actions.add_argument("--report", action="store_true", help="generate and open a Markdown scoring report")
    parser.add_argument("--serve", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not args.serve and not any((args.setup, args.start, args.stop, args.fix, args.report)):
        parser.error("choose one action: --setup, --start, --stop, --fix, or --report")
    if args.serve and any((args.setup, args.start, args.stop, args.fix, args.report)):
        parser.error("--serve is an internal option and cannot be combined with other actions")

    try:
        if args.serve:
            return serve()
        if args.stop:
            require_vm()
            return stop_server()
        modules = validate_project()
        if args.setup:
            apply_setups(modules)
            logger.info("Setup completed. Flask was not started.")
            return 0
        if args.start:
            return start_server()
        if args.fix:
            apply_fixes(modules)
            logger.info("Configured remediation scripts completed.")
            return 0
        if args.report:
            output = write_markdown_scoring_report()
            logger.info("Markdown scoring report written to %s.", output)
            try:
                result = subprocess.run(["xdg-open", str(output)], check=False, timeout=10)
            except (FileNotFoundError, subprocess.TimeoutExpired):
                result = None
            if result is None or result.returncode != 0:
                print(output.read_text(encoding="utf-8"))
            else:
                print(f"Opened scoring report: {output}")
            return 0
    except (CpSimError, OSError, subprocess.SubprocessError) as exc:
        logger.error("%s", exc)
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
