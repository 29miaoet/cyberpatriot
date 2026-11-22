#!/usr/bin/env python3
"""cp-sim: VM-only CyberPatriot scoring simulator."""

from __future__ import annotations

import argparse
import html
import json
import logging
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, send_file

ROOT = Path(__file__).resolve().parent
SOURCE_DIR = ROOT / "src"
CONFIG_PATH = ROOT / "config.json"
REPORT_PATH = ROOT / "Scoring Report.html"
DESKTOP_README_PATH = Path.home() / "Desktop" / "README.html"
HOST = "127.0.0.1"
PORT = 5000
SCRIPT_TIMEOUT_SECONDS = 120
MODULE_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("cp-sim")


class CpSimError(Exception):
    """Expected configuration or runtime error."""


def is_virtual_machine() -> tuple[bool, str]:
    """Detect a VM heuristically; this is a safety gate, not proof."""
    detector = shutil.which("systemd-detect-virt")
    if detector:
        try:
            result = subprocess.run(
                [detector, "--vm"], check=False, capture_output=True,
                text=True, timeout=5,
            )
            detected = result.stdout.strip()
            if result.returncode == 0 and detected and detected != "none":
                return True, f"systemd-detect-virt: {detected}"
        except (OSError, subprocess.TimeoutExpired):
            pass

    dmi_files = (
        Path("/sys/class/dmi/id/sys_vendor"),
        Path("/sys/class/dmi/id/product_name"),
        Path("/sys/class/dmi/id/board_vendor"),
    )
    known_vm_terms = (
        "kvm", "qemu", "vmware", "virtualbox", "innotek",
        "microsoft corporation", "virtual machine", "xen",
        "parallels", "bhyve", "amazon ec2", "google",
    )
    for path in dmi_files:
        try:
            value = path.read_text(encoding="utf-8", errors="replace").strip().lower()
        except OSError:
            continue
        if any(term in value for term in known_vm_terms):
            return True, f"virtualization marker in {path}"

    try:
        cpu_info = Path("/proc/cpuinfo").read_text(
            encoding="utf-8", errors="replace"
        ).lower()
        if re.search(r"^flags\\s*:.*\\bhypervisor\\b", cpu_info, re.MULTILINE):
            return True, "hypervisor CPU flag"
    except OSError:
        pass

    return False, "no recognized virtual-machine marker was found"


def require_vm() -> None:
    if not sys.platform.startswith("linux"):
        raise CpSimError("cp-sim only supports Linux virtual machines.")
    virtual, reason = is_virtual_machine()
    if not virtual:
        raise CpSimError(
            "VM safety check failed; refusing to continue. "
            "Run cp-sim inside a supported Linux VM. "
            f"Detection result: {reason}"
        )
    logger.info("VM check passed (%s).", reason)


def load_config() -> list[str]:
    try:
        config: Any = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CpSimError(f"Configuration file not found: {CONFIG_PATH}") from exc
    except json.JSONDecodeError as exc:
        raise CpSimError(f"Invalid JSON in {CONFIG_PATH}: {exc}") from exc

    if not isinstance(config, dict) or set(config) != {"vulnerabilities"}:
        raise CpSimError(
            'config.json must be one object containing only "vulnerabilities".'
        )

    modules = config["vulnerabilities"]
    if not isinstance(modules, list) or not all(
        isinstance(item, str) and MODULE_NAME_PATTERN.fullmatch(item)
        for item in modules
    ):
        raise CpSimError(
            '"vulnerabilities" must be an array of valid src subdirectory names.'
        )
    if len(modules) != len(set(modules)):
        raise CpSimError('"vulnerabilities" must not contain duplicate names.')
    return modules


def module_directory(name: str) -> Path:
    candidate = (SOURCE_DIR / name).resolve()
    try:
        candidate.relative_to(SOURCE_DIR.resolve())
    except ValueError as exc:
        raise CpSimError(f"Module path escapes src/: {name}") from exc
    if not candidate.is_dir():
        raise CpSimError(f"Configured module directory does not exist: src/{name}")
    return candidate


def run_module_script(
    script: Path, module_dir: Path, label: str
) -> subprocess.CompletedProcess[str]:
    if not script.is_file():
        raise CpSimError(f"Missing {label} script: {script}")
    if script.is_symlink():
        raise CpSimError(f"Refusing to execute symlinked script: {script}")
    return subprocess.run(
        ["/bin/bash", str(script)],
        cwd=module_dir,
        check=False,
        capture_output=True,
        text=True,
        timeout=SCRIPT_TIMEOUT_SECONDS,
        env={
            **os.environ,
            "PATH": os.environ.get("PATH", "/usr/sbin:/usr/bin:/sbin:/bin"),
        },
    )


def apply_setups(modules: list[str]) -> None:
    for name in modules:
        directory = module_directory(name)
        setup_script = directory / "setup.sh"
        if not setup_script.exists():
            logger.info("No setup.sh found for %s; skipping.", name)
            continue
        logger.info("Running setup.sh for %s (--apply was supplied).", name)
        try:
            result = run_module_script(setup_script, directory, "setup.sh")
        except subprocess.TimeoutExpired as exc:
            raise CpSimError(f"setup.sh timed out for {name}.") from exc
        if result.stdout:
            logger.info("%s", result.stdout.rstrip())
        if result.stderr:
            logger.warning("%s", result.stderr.rstrip())
        if result.returncode != 0:
            raise CpSimError(
                f"setup.sh for {name} exited with status {result.returncode}; "
                "remaining setup scripts were not run."
            )


def write_module_readme(modules: list[str]) -> None:
    DESKTOP_README_PATH.parent.mkdir(parents=True, exist_ok=True)
    entries = "\n".join(
        f"<li><code>{html.escape(name)}</code></li>" for name in modules
    ) or "<li>No modules are configured.</li>"
    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>cp-sim — configured modules</title>
</head>
<body>
  <h1>Configured vulnerability modules</h1>
  <p>Generated from <code>config.json</code>.</p>
  <ul>
    {entries}
  </ul>
</body>
</html>
"""
    DESKTOP_README_PATH.write_text(document, encoding="utf-8")
    logger.info("Wrote module list to %s.", DESKTOP_README_PATH)


def write_scoring_report() -> None:
    document = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>cp-sim — Scoring Report</title>
  <style>
    body { font: 16px/1.5 system-ui, sans-serif; margin: 2rem auto; max-width: 52rem; padding: 0 1rem; }
    li { margin: .5rem 0; }
    .muted { color: #666; }
    .error { color: #a21d1d; }
  </style>
</head>
<body>
  <h1>Scoring Report</h1>
  <p class="muted">Live detector results. This page refreshes automatically.</p>
  <p id="updated" class="muted">Loading…</p>
  <ul id="checks" aria-live="polite"></ul>
  <script>
    "use strict";
    const checks = document.getElementById("checks");
    const updated = document.getElementById("updated");

    async function refreshScores() {
      try {
        const response = await fetch("/api/scores", { cache: "no-store" });
        if (!response.ok) throw new Error("HTTP " + response.status);
        const payload = await response.json();
        checks.replaceChildren();

        for (const item of payload.checks) {
          // Exit 0 means fixed; exit 1 means unresolved and is intentionally hidden.
          if (item.status === "fixed") {
            const li = document.createElement("li");
            li.textContent = item.message;
            checks.appendChild(li);
          } else if (item.status === "error") {
            const li = document.createElement("li");
            li.className = "error";
            li.textContent = item.name + ": detector error (" + item.detail + ")";
            checks.appendChild(li);
          }
        }

        if (checks.children.length === 0) {
          const li = document.createElement("li");
          li.className = "muted";
          li.textContent = "No fixed checks reported.";
          checks.appendChild(li);
        }
        updated.textContent =
          "Last updated: " + new Date(payload.timestamp).toLocaleTimeString();
      } catch (error) {
        updated.textContent = "Unable to retrieve scores: " + error.message;
      }
    }

    refreshScores();
    window.setInterval(refreshScores, 5000);
  </script>
</body>
</html>
"""
    REPORT_PATH.write_text(document, encoding="utf-8")
    logger.info("Wrote scoring report to %s.", REPORT_PATH)


def collect_scores() -> list[dict[str, str]]:
    modules = load_config()
    checks: list[dict[str, str]] = []
    for name in modules:
        directory = module_directory(name)
        detector = directory / "detect.sh"
        if not detector.is_file():
            checks.append({
                "name": name, "status": "error", "detail": "detect.sh is missing"
            })
            continue
        try:
            result = run_module_script(detector, directory, "detect.sh")
        except subprocess.TimeoutExpired:
            checks.append({
                "name": name, "status": "error", "detail": "detector timed out"
            })
            continue

        if result.returncode == 0:
            checks.append({
                "name": name,
                "status": "fixed",
                "message": f"{name.upper()} has been enabled",
            })
        elif result.returncode == 1:
            checks.append({"name": name, "status": "unresolved"})
        else:
            checks.append({
                "name": name,
                "status": "error",
                "detail": f"exit status {result.returncode}",
            })
    return checks


@app.get("/")
def scoring_report():
    return send_file(REPORT_PATH)


@app.get("/api/scores")
def api_scores():
    try:
        checks = collect_scores()
    except CpSimError as exc:
        return jsonify({"error": str(exc), "checks": []}), 500
    return jsonify({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
    })


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the VM-only cp-sim scoring service."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="execute configured setup.sh scripts before starting the service",
    )
    args = parser.parse_args()

    try:
        require_vm()
        modules = load_config()
        for name in modules:
            module_directory(name)
        if args.apply:
            apply_setups(modules)
        else:
            logger.info("Read-only startup: setup scripts will not be executed.")
        write_module_readme(modules)
        write_scoring_report()
    except (CpSimError, OSError, subprocess.SubprocessError) as exc:
        logger.error("%s", exc)
        return 1

    logger.info("Scoring report: http://%s:%d/", HOST, PORT)
    app.run(host=HOST, port=PORT, debug=False, threaded=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
