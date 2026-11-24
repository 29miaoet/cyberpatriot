"""Vulnerability-module script execution and metadata."""
from __future__ import annotations

import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any

from .config import CpSimError, SCRIPT_TIMEOUT_SECONDS, module_directory

logger = logging.getLogger("cp-sim")


def run_module_script(
    script: Path, module_dir: Path, label: str
) -> subprocess.CompletedProcess[str]:
    if not script.is_file():
        raise CpSimError(f"Missing {label} script: {script}")
    if script.is_symlink():
        raise CpSimError(f"Refusing to execute symlinked script: {script}")
    return subprocess.run(
        ["/bin/bash", str(script)], cwd=module_dir, check=False,
        capture_output=True, text=True, timeout=SCRIPT_TIMEOUT_SECONDS,
        env={**os.environ, "PATH": os.environ.get("PATH", "/usr/sbin:/usr/bin:/sbin:/bin")},
    )


def _run_module_scripts(modules: list[str], script_name: str, action: str) -> None:
    for name in modules:
        directory = module_directory(name)
        script = directory / script_name
        if not script.exists():
            logger.info("No %s found for %s; skipping.", script_name, name)
            continue
        logger.info("Running %s for %s (--%s was supplied).", script_name, name, action)
        try:
            result = run_module_script(script, directory, script_name)
        except subprocess.TimeoutExpired as exc:
            raise CpSimError(f"{script_name} timed out for {name}.") from exc
        if result.stdout:
            logger.info("%s", result.stdout.rstrip())
        if result.stderr:
            logger.warning("%s", result.stderr.rstrip())
        if result.returncode != 0:
            raise CpSimError(
                f"{script_name} for {name} exited with status {result.returncode}; "
                f"remaining {script_name} scripts were not run."
            )


def apply_setups(modules: list[str]) -> None:
    """Execute configured setup.sh scripts to prepare practice states."""
    _run_module_scripts(modules, "setup.sh", "apply")


def apply_fixes(modules: list[str]) -> None:
    """Execute configured fix.sh scripts to remediate practice states."""
    _run_module_scripts(modules, "fix.sh", "fix")


def load_module_properties(name: str) -> dict[str, Any]:
    """Load optional display/scoring metadata without trusting its types."""
    properties_path = module_directory(name) / "properties.json"
    try:
        data: Any = json.loads(properties_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    points = data.get("points", 1)
    if isinstance(points, bool) or not isinstance(points, int) or points < 0:
        points = 1
    display_name = data.get("name")
    if not isinstance(display_name, str) or not display_name.strip():
        display_name = name.replace("_", " ").replace("-", " ").title()
    fix = data.get("fix") if isinstance(data.get("fix"), str) else ""
    vulnerability = data.get("vulnerability") if isinstance(data.get("vulnerability"), str) else ""
    return {"name": display_name, "points": points, "fix": fix, "vulnerability": vulnerability}
