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
from markupsafe import Markup

ROOT = Path(__file__).resolve().parent
SOURCE_DIR = ROOT / "src"
CONFIG_PATH = ROOT / "config.json"
REPORT_PATH = ROOT / "Scoring Report.html"
DESKTOP_README_PATH = Path.home() / "Desktop" / "README.html"
HOST = "127.0.0.1"
PORT = 5000
SCRIPT_TIMEOUT_SECONDS = 120
MODULE_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")

app = Flask(__name__, template_folder=str(ROOT / "templates"))
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
        if re.search(r"^flags\s*:.*\bhypervisor\b", cpu_info, re.MULTILINE):
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
    username_pattern = re.compile(r"^[a-z_][a-z0-9_-]*[$]?$")
    result: dict[str, list[str]] = {}
    for key in keys:
        values = data[key]
        if not isinstance(values, list) or any(
            not isinstance(value, str) or not username_pattern.fullmatch(value)
            for value in values
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


def read_os_details() -> dict[str, str]:
    """Read distribution details supplied by main.sh or /etc/os-release."""
    values = {
        "ID": os.environ.get("CP_SIM_OS_ID", ""),
        "PRETTY_NAME": os.environ.get("CP_SIM_OS_PRETTY_NAME", ""),
        "VERSION_ID": os.environ.get("CP_SIM_OS_VERSION", ""),
    }
    if not all(values.values()):
        try:
            for line in Path("/etc/os-release").read_text(
                encoding="utf-8", errors="replace"
            ).splitlines():
                key, separator, value = line.partition("=")
                if separator and key in values and not values[key]:
                    values[key] = value.strip().strip('"').strip("'")
        except OSError:
            pass
    return {
        "id": values["ID"] or "linux",
        "pretty_name": values["PRETTY_NAME"] or "Linux",
        "version": values["VERSION_ID"],
    }


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
    fix = data.get("fix")
    if not isinstance(fix, str):
        fix = ""
    vulnerability = data.get("vulnerability")
    if not isinstance(vulnerability, str):
        vulnerability = ""
    return {
        "name": display_name,
        "points": points,
        "fix": fix,
        "vulnerability": vulnerability,
    }


def render_template(template_name: str, context: dict[str, Any]) -> str:
    """Render one HTML template using Flask/Jinja autoescaping."""
    try:
        return app.jinja_env.get_template(template_name).render(**context)
    except Exception as exc:
        raise CpSimError(
            f"Could not render templates/{template_name}: {exc}"
        ) from exc


def write_module_readme(modules: list[str]) -> None:
    """Populate templates/ReadMe.html and write the desktop README."""
    DESKTOP_README_PATH.parent.mkdir(parents=True, exist_ok=True)
    os_details = read_os_details()
    title = os.environ.get("CP_SIM_TITLE", "CyberPatriot")
    root_policy = os.environ.get(
        "CP_SIM_LINUX_ROOT_POLICY",
        "Use administrative privileges only when necessary. Do not modify "
        "root account settings unless a verified requirement calls for it.",
    )
    # Optional user-authored HTML can be added without changing the template.
    user_readme_path = ROOT / "UserReadMe.html"
    try:
        user_readme_html = Markup(user_readme_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        user_readme_html = Markup("")

    context = {
        "OS": os_details["pretty_name"],
        "TITLE": title,
        "LINUX_ROOT_POLICY": root_policy,
        "USER_README_HTML": user_readme_html,
    }
    document = render_template("ReadMe.html", context)
    DESKTOP_README_PATH.write_text(document, encoding="utf-8")
    logger.info("Wrote module README to %s.", DESKTOP_README_PATH)


def write_scoring_report() -> None:
    """Populate templates/ScoringReport.html from live module detector results."""
    modules = load_config()
    checks = collect_scores()
    metadata = {name: load_module_properties(name) for name in modules}
    user_lists = load_user_lists() if "users" in modules else None
    total_points = sum(
        metadata[name]["points"] * (
            len(user_lists["unauthorizedUsers"])
            + len(set(user_lists["unauthorizedAdministrators"])
                  - set(user_lists["unauthorizedUsers"]))
            if name == "users" and user_lists is not None else 1
        )
        for name in modules
    )
    fixed = [item for item in checks if item["status"] == "fixed"]
    errors = [item for item in checks if item["status"] == "error"]
    score = sum(
        item.get("points", metadata[item["name"]]["points"])
        for item in fixed
    )

    point_lines = [
        f"{html.escape(item.get('label', metadata[item['name']]['name']))}: "
        f"{item.get('points', metadata[item['name']]['points']):g} points"
        for item in fixed
    ]
    point_rows = Markup("<br>\n".join(point_lines)) if point_lines else Markup(
        "No scored issues fixed yet."
    )
    penalty_rows = Markup("None")
    hint_lines = []
    for item in checks:
        if item["status"] == "unresolved":
            hint = metadata[item["name"]]["fix"] or metadata[item["name"]]["vulnerability"]
            if hint:
                hint_lines.append(
                    f"<li><strong>{html.escape(item.get('label', metadata[item['name']]['name']))}:</strong> "
                    f"{html.escape(hint)}</li>"
                )
    hints = Markup("<ul>\n" + "\n".join(hint_lines) + "\n</ul>") if hint_lines else Markup(
        "<p>No hints are available for unresolved modules.</p>"
    )

    if not modules:
        overall_status, overall_color = "No modules configured", "gray"
    elif errors:
        overall_status, overall_color = "Detector errors detected", "red"
    else:
        overall_status, overall_color = "Detectors operational", "green"

    context = {
        "DISPLAY_TEAM_ID": os.environ.get("CP_SIM_TEAM_ID", "Not configured"),
        "TITLE": os.environ.get("CP_SIM_REPORT_TITLE", "CyberPatriot Scoring Report"),
        "GENERATED_AT": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z"),
        "STALE_REPORT_WARNING": Markup(""),
        "SCORE": f"{score:g}",
        "TOTAL_POINTS": f"{total_points:g}",
        "REMOTE_LINKS_SECTION": Markup(""),
        "OVERALL_COLOR": overall_color,
        "OVERALL_STATUS": overall_status,
        "NET_COLOR": "gray",
        "NET_STATUS": "Not checked",
        "PENALTY_COUNT": 0,
        "DETRACTED_POINTS": 0,
        "PENALTY_ROWS": penalty_rows,
        "FIXED_COUNT": len(fixed),
        "SCORED_VULNS": len(checks),
        "CONTRIBUTED_POINTS": f"{score:g}",
        "POINT_ROWS": point_rows,
        "HINTS": hints,
    }
    document = render_template("ScoringReport.html", context)
    REPORT_PATH.write_text(document, encoding="utf-8")
    logger.info("Wrote scoring report to %s.", REPORT_PATH)


def write_desktop_launcher() -> None:
    """Create a desktop shortcut that opens the already-running scoring service."""
    desktop_dir = Path.home() / "Desktop"
    desktop_dir.mkdir(parents=True, exist_ok=True)
    launcher_path = desktop_dir / "Scoring Report.desktop"
    launcher = "\n".join((
        "[Desktop Entry]",
        "Version=1.0",
        "Type=Application",
        "Name=Scoring Report",
        "Comment=Open the local cp-sim scoring report",
        "Exec=xdg-open http://127.0.0.1:5000/",
        "Terminal=false",
        "Categories=Education;Development;",
        "",
    ))
    launcher_path.write_text(launcher, encoding="utf-8")
    launcher_path.chmod(0o755)
    logger.info("Created desktop launcher at %s.", launcher_path)


def collect_user_scores(directory: Path) -> list[dict[str, Any]]:
    """Score each unauthorized account independently, with user-removal precedence."""
    users = load_user_lists()
    expected = (
        [("UNAUTHORIZED_USER", name, f"Unauthorized user: {name}")
         for name in users["unauthorizedUsers"]]
        + [("UNAUTHORIZED_ADMIN", name, f"Unauthorized administrator: {name}")
           for name in users["unauthorizedAdministrators"]
           if name not in set(users["unauthorizedUsers"])]
    )
    detector = directory / "detect.sh"
    if not detector.is_file():
        return [{"name": "users", "status": "error", "detail": "detect.sh is missing"}]
    try:
        result = run_module_script(detector, directory, "detect.sh")
    except subprocess.TimeoutExpired:
        return [{"name": "users", "status": "error", "detail": "detector timed out"}]

    if result.returncode not in (0, 1):
        return [{
            "name": "users", "status": "error",
            "detail": f"detector exited with status {result.returncode}",
        }]

    findings: set[tuple[str, str]] = set()
    valid_findings = {
        ("UNAUTHORIZED_USER", name) for name in users["unauthorizedUsers"]
    } | {
        ("UNAUTHORIZED_ADMIN", name)
        for name in users["unauthorizedAdministrators"]
        if name not in set(users["unauthorizedUsers"])
    }
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        kind, separator, username = line.partition(":")
        finding = (kind, username)
        if not separator or finding not in valid_findings:
            return [{
                "name": "users", "status": "error",
                "detail": f"invalid detector output: {line!r}",
            }]
        findings.add(finding)

    if bool(findings) != (result.returncode == 1):
        return [{
            "name": "users", "status": "error",
            "detail": "detector exit status did not match its findings",
        }]

    return [{
        "name": "users",
        "label": label,
        "status": "unresolved" if (kind, username) in findings else "fixed",
        "points": 3,
        "detail": f"{kind.lower().replace('_', ' ')} remains present",
    } for kind, username, label in expected]


def collect_scores() -> list[dict[str, Any]]:
    modules = load_config()
    checks: list[dict[str, Any]] = []
    for name in modules:
        directory = module_directory(name)
        if name == "users":
            checks.extend(collect_user_scores(directory))
            continue
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
    try:
        # The template uses a periodic page refresh; regenerate scores each time.
        write_scoring_report()
    except (CpSimError, OSError, subprocess.SubprocessError) as exc:
        logger.error("Could not refresh scoring report: %s", exc)
        return "Unable to generate scoring report. Check the cp-sim terminal output.", 500
    response = send_file(REPORT_PATH, max_age=0)
    response.headers["Cache-Control"] = "no-store"
    return response


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
        write_desktop_launcher()
    except (CpSimError, OSError, subprocess.SubprocessError) as exc:
        logger.error("%s", exc)
        return 1

    logger.info("Scoring report: http://%s:%s/", HOST, PORT)
    app.run(host=HOST, port=PORT, debug=False, threaded=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
