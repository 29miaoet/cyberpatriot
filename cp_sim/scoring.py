"""Run module detectors and convert their results into scoring records."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from .config import load_config, load_user_lists, module_directory
from .modules import run_module_script


def collect_user_scores(directory: Path) -> list[dict[str, Any]]:
    """Score each unauthorized account independently, with user-removal precedence."""
    users = load_user_lists()
    unauthorized_users = set(users["unauthorizedUsers"])
    expected = (
        [("UNAUTHORIZED_USER", name, f"Removed unauthorized user {name}")
         for name in users["unauthorizedUsers"]]
        + [("UNAUTHORIZED_ADMIN", name,
            f"Removed administrative privileges from unauthorized administrator {name}")
           for name in users["unauthorizedAdministrators"] if name not in unauthorized_users]
    )
    detector = directory / "detect.sh"
    if not detector.is_file():
        return [{"name": "users", "status": "error", "detail": "detect.sh is missing"}]
    try:
        result = run_module_script(detector, directory, "detect.sh")
    except subprocess.TimeoutExpired:
        return [{"name": "users", "status": "error", "detail": "detector timed out"}]
    if result.returncode not in (0, 1):
        return [{"name": "users", "status": "error",
                 "detail": f"detector exited with status {result.returncode}"}]
    valid_findings = {
        ("UNAUTHORIZED_USER", name) for name in users["unauthorizedUsers"]
    }
    valid_findings.update(
        ("UNAUTHORIZED_ADMIN", name) for name in users["unauthorizedAdministrators"]
        if name not in unauthorized_users
    )
    findings: set[tuple[str, str]] = set()
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        kind, separator, username = line.partition(":")
        finding = (kind, username)
        if not separator or finding not in valid_findings:
            return [{"name": "users", "status": "error",
                     "detail": f"invalid detector output: {line!r}"}]
        findings.add(finding)
    if bool(findings) != (result.returncode == 1):
        return [{"name": "users", "status": "error",
                 "detail": "detector exit status did not match its findings"}]
    return [{
        "name": "users", "message": message,
        "status": "unresolved" if (kind, username) in findings else "fixed",
        "points": 3, "detail": f"{kind.lower().replace('_', ' ')} remains present",
    } for kind, username, message in expected]


def collect_policy_list_scores(
    directory: Path,
    config_filename: str,
    authorized_key: str,
    unauthorized_key: str,
    finding_kind: str,
    module_name: str,
    item_label: str,
    remediation: str,
) -> list[dict[str, Any]]:
    """Score each configured unauthorized package/service as an independent issue."""
    config_path = directory / config_filename
    try:
        data: Any = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [{"name": module_name, "status": "error",
                 "detail": f"cannot load {config_filename}: {exc}"}]
    if not isinstance(data, dict) or set(data) != {authorized_key, unauthorized_key}:
        return [{"name": module_name, "status": "error",
                 "detail": f"{config_filename} must contain exactly {authorized_key} and {unauthorized_key}"}]
    authorized = data[authorized_key]
    unauthorized = data[unauthorized_key]
    if (not isinstance(authorized, list) or not isinstance(unauthorized, list)
            or any(not isinstance(value, str) or not value for value in authorized + unauthorized)
            or len(authorized) != len(set(authorized))
            or len(unauthorized) != len(set(unauthorized))
            or set(authorized).intersection(unauthorized)):
        return [{"name": module_name, "status": "error",
                 "detail": f"{config_filename} contains invalid, duplicate, or overlapping entries"}]

    detector = directory / "detect.sh"
    if not detector.is_file():
        return [{"name": module_name, "status": "error", "detail": "detect.sh is missing"}]
    try:
        result = run_module_script(detector, directory, "detect.sh")
    except subprocess.TimeoutExpired:
        return [{"name": module_name, "status": "error", "detail": "detector timed out"}]
    if result.returncode not in (0, 1):
        return [{"name": module_name, "status": "error",
                 "detail": f"detector exited with status {result.returncode}"}]

    valid_findings = {(finding_kind, value) for value in unauthorized}
    findings: set[tuple[str, str]] = set()
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        kind, separator, value = line.partition(":")
        finding = (kind, value)
        if not separator or finding not in valid_findings:
            return [{"name": module_name, "status": "error",
                     "detail": f"invalid detector output: {line!r}"}]
        findings.add(finding)
    if bool(findings) != (result.returncode == 1):
        return [{"name": module_name, "status": "error",
                 "detail": "detector exit status did not match its findings"}]

    return [{
        "name": module_name,
        "message": f"{remediation} {value}",
        "status": "unresolved" if (finding_kind, value) in findings else "fixed",
        "points": 3,
        "detail": f"unauthorized {item_label} remains present",
    } for value in unauthorized]


def collect_scores() -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for name in load_config():
        directory = module_directory(name)
        if name == "users":
            checks.extend(collect_user_scores(directory))
            continue
        if name == "applications":
            checks.extend(collect_policy_list_scores(
                directory, "applications.json", "authorizedApplications",
                "unauthorizedApplications", "UNAUTHORIZED_APPLICATION",
                "applications", "application", "Removed unauthorized application",
            ))
            continue
        if name == "services":
            checks.extend(collect_policy_list_scores(
                directory, "services.json", "authorizedServices",
                "unauthorizedServices", "UNAUTHORIZED_SERVICE",
                "services", "service", "Stopped and disabled unauthorized service",
            ))
            continue
        detector = directory / "detect.sh"
        if not detector.is_file():
            checks.append({"name": name, "status": "error", "detail": "detect.sh is missing"})
            continue
        try:
            result = run_module_script(detector, directory, "detect.sh")
        except subprocess.TimeoutExpired:
            checks.append({"name": name, "status": "error", "detail": "detector timed out"})
            continue
        if result.returncode == 0:
            checks.append({"name": name, "status": "fixed"})
        elif result.returncode == 1:
            checks.append({"name": name, "status": "unresolved"})
        else:
            checks.append({"name": name, "status": "error",
                           "detail": f"exit status {result.returncode}"})
    return checks
