"""Project paths, configuration loading, and validation."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = ROOT / "src"
CONFIG_PATH = ROOT / "config.json"
REPORT_PATH = ROOT / "Scoring Report.html"
DESKTOP_README_PATH = Path.home() / "Desktop" / "README.html"
ANSWER_KEY_PATH = Path.home() / "Desktop" / "Answer Key.md"
HOST = "127.0.0.1"
PORT = 5000
SCRIPT_TIMEOUT_SECONDS = 120
MODULE_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")


class CpSimError(Exception):
    """Expected configuration or runtime error."""


def load_config() -> list[str]:
    try:
        config: Any = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CpSimError(f"Configuration file not found: {CONFIG_PATH}") from exc
    except json.JSONDecodeError as exc:
        raise CpSimError(f"Invalid JSON in {CONFIG_PATH}: {exc}") from exc
    if not isinstance(config, dict) or set(config) != {"vulnerabilities"}:
        raise CpSimError('config.json must be one object containing only "vulnerabilities".')
    modules = config["vulnerabilities"]
    if not isinstance(modules, list) or not all(
        isinstance(item, str) and MODULE_NAME_PATTERN.fullmatch(item) for item in modules
    ):
        raise CpSimError('"vulnerabilities" must be an array of valid src subdirectory names.')
    if len(modules) != len(set(modules)):
        raise CpSimError('"vulnerabilities" must not contain duplicate names.')
    return modules


def load_user_lists() -> dict[str, list[str]]:
    """Load and validate the four account lists used by the users module."""
    path = SOURCE_DIR / "users" / "users.json"
    try:
        data: Any = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CpSimError(f"User configuration not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CpSimError(f"Invalid JSON in {path}: {exc}") from exc
    keys = {
        "authorizedUsers", "unauthorizedUsers",
        "authorizedAdministrators", "unauthorizedAdministrators",
    }
    if not isinstance(data, dict) or set(data) != keys:
        raise CpSimError(f"{path} must contain exactly: {', '.join(sorted(keys))}.")
    username_pattern = re.compile(r"^(?!root$)[a-z_][a-z0-9_-]*[$]?$")
    result: dict[str, list[str]] = {}
    for key in keys:
        values = data[key]
        if not isinstance(values, list) or any(
            not isinstance(value, str) or not username_pattern.fullmatch(value) for value in values
        ):
            raise CpSimError(f'{path}: "{key}" must be an array of valid Linux usernames.')
        if len(values) != len(set(values)):
            raise CpSimError(f'{path}: "{key}" must not contain duplicate usernames.')
        result[key] = values
    return result


def module_directory(name: str) -> Path:
    candidate = (SOURCE_DIR / name).resolve()
    try:
        candidate.relative_to(SOURCE_DIR.resolve())
    except ValueError as exc:
        raise CpSimError(f"Module path escapes src/: {name}") from exc
    if not candidate.is_dir():
        raise CpSimError(f"Configured module directory does not exist: src/{name}")
    return candidate
