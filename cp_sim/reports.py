"""HTML report and desktop artifact generation."""
from __future__ import annotations

import json
import logging
import os
import shutil
from datetime import datetime
from typing import Any

from markupsafe import Markup

from .config import ANSWER_KEY_PATH, DESKTOP_README_PATH, REPORT_PATH, ROOT, CpSimError, load_config, load_user_lists
from .environment import read_os_details
from .modules import load_module_properties
from .scoring import collect_scores
from .web import app

logger = logging.getLogger("cp-sim")


def render_template(template_name: str, context: dict[str, Any]) -> str:
    """Render an HTML template using Flask/Jinja autoescaping."""
    try:
        return app.jinja_env.get_template(template_name).render(**context)
    except Exception as exc:
        raise CpSimError(f"Could not render templates/{template_name}: {exc}") from exc


def render_account_list(usernames: list[str]) -> Markup:
    """Render configured account names as an escaped HTML list."""
    if not usernames:
        return Markup("<p>None configured.</p>")
    items = Markup("").join(
        Markup("<li>{}</li>").format(username) for username in usernames
    )
    return Markup("<ul>{}</ul>").format(items)


def render_service_list(services: list[str]) -> Markup:
    """Render configured service identifiers and their human-readable roles."""
    descriptions = {
        "ssh": "OpenSSH server",
        "vsftpd": "FTP server",
        "postfix": "SMTP mail-transfer service",
        "apache2": "Apache HTTP server",
    }
    if not services:
        return Markup("<p>None configured.</p>")
    items = Markup("").join(
        Markup("<li><code>{}</code> — {}</li>").format(
            service, descriptions.get(service, "Service")
        )
        for service in services
    )
    return Markup("<ul>{}</ul>").format(items)


def write_module_readme(modules: list[str]) -> None:
    """Populate the module README template and write the desktop README."""
    DESKTOP_README_PATH.parent.mkdir(parents=True, exist_ok=True)
    os_details = read_os_details()
    title = os.environ.get("CP_SIM_TITLE", "CyberPatriot")
    root_policy = os.environ.get(
        "CP_SIM_LINUX_ROOT_POLICY",
        "Use administrative privileges only when necessary. Do not modify "
        "root account settings unless a verified requirement calls for it.",
    )
    try:
        user_readme_html = Markup((ROOT / "UserReadMe.html").read_text(encoding="utf-8"))
    except FileNotFoundError:
        user_readme_html = Markup("")
    if "users" in modules:
        user_lists = load_user_lists()
        authorized_users = render_account_list(user_lists["authorizedUsers"])
        authorized_administrators = render_account_list(
            user_lists["authorizedAdministrators"]
        )
    else:
        authorized_users = Markup("<p>Not configured.</p>")
        authorized_administrators = Markup("<p>Not configured.</p>")
    if "applications" in modules:
        applications_path = ROOT / "src" / "applications" / "applications.json"
        try:
            application_config = json.loads(
                applications_path.read_text(encoding="utf-8")
            )
            authorized_applications = application_config["authorizedApplications"]
            if not isinstance(authorized_applications, list) or not all(
                isinstance(item, str) for item in authorized_applications
            ):
                raise ValueError("authorizedApplications must be an array of strings")
        except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
            raise CpSimError(
                f"Invalid application configuration in {applications_path}: {exc}"
            ) from exc
        authorized_applications_html = render_account_list(authorized_applications)
    else:
        authorized_applications_html = Markup("<p>Not configured.</p>")

    if "services" in modules:
        services_path = ROOT / "src" / "services" / "services.json"
        try:
            service_config = json.loads(services_path.read_text(encoding="utf-8"))
            authorized_services = service_config["authorizedServices"]
            if not isinstance(authorized_services, list) or not all(
                isinstance(item, str) for item in authorized_services
            ):
                raise ValueError("authorizedServices must be an array of strings")
        except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
            raise CpSimError(f"Invalid service configuration in {services_path}: {exc}") from exc
        authorized_services_html = render_service_list(authorized_services)
    else:
        authorized_services_html = Markup("<p>Not configured.</p>")

    document = render_template("ReadMe.html", {
        "OS": os_details["pretty_name"], "TITLE": title,
        "LINUX_ROOT_POLICY": root_policy, "USER_README_HTML": user_readme_html,
        "AUTHORIZED_USERS": authorized_users,
        "AUTHORIZED_ADMINISTRATORS": authorized_administrators,
        "AUTHORIZED_APPLICATIONS": authorized_applications_html,
        "AUTHORIZED_SERVICES": authorized_services_html,
    })
    DESKTOP_README_PATH.write_text(document, encoding="utf-8")
    for asset_name in ("background.jpg", "logo.svg"):
        asset_path = ROOT / "templates" / asset_name
        if asset_path.is_file():
            shutil.copy2(asset_path, DESKTOP_README_PATH.parent / asset_name)
    logger.info("Wrote module README to %s.", DESKTOP_README_PATH)



def write_answer_key(modules: list[str]) -> None:
    """Write module vulnerabilities and remediation guidance to the desktop answer key."""
    lines = [
        "# Answer Key",
        "",
        "This file contains the vulnerability descriptions and remediation guidance "
        "for the configured practice modules.",
        "",
        f"Generated: {datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}",
        "",
        "> Keep this file separate from the scoring report during practice.",
        "",
    ]

    for name in modules:
        metadata = load_module_properties(name)
        if name == "users":
            users = load_user_lists()
            unauthorized_users = users["unauthorizedUsers"]
            unauthorized_user_set = set(unauthorized_users)
            unauthorized_admins = [
                username for username in users["unauthorizedAdministrators"]
                if username not in unauthorized_user_set
            ]
            lines.extend([
                f"## {metadata['name']}",
                "",
                f"**Issue:** {metadata['vulnerability'] or 'No issue description configured.'}",
                "",
            ])
            for username in unauthorized_users:
                lines.extend([
                    f"### Unauthorized user: `{username}`",
                    "",
                    "The account is expected to exist in the vulnerable practice state. "
                    "The remediation removes the account.",
                    "",
                    f"**Remediation:** {metadata['fix'] or 'No remediation guidance configured.'}",
                    "",
                ])
            for username in unauthorized_admins:
                lines.extend([
                    f"### Unauthorized administrator: `{username}`",
                    "",
                    "The account is expected to exist and have administrative privileges "
                    "in the vulnerable practice state. Remediation removes those privileges "
                    "while preserving the account.",
                    "",
                    f"**Remediation:** {metadata['fix'] or 'No remediation guidance configured.'}",
                    "",
                ])
            if not unauthorized_users and not unauthorized_admins:
                lines.extend(["No unauthorized account checks are configured.", ""])
            continue


        if name in {"applications", "services"}:
            config_filename = f"{name}.json"
            list_key = (
                "unauthorizedApplications" if name == "applications"
                else "unauthorizedServices"
            )
            try:
                module_config = json.loads(
                    (ROOT / "src" / name / config_filename).read_text(encoding="utf-8")
                )
                unauthorized_items = module_config.get(list_key, [])
                if not isinstance(unauthorized_items, list):
                    unauthorized_items = []
            except (OSError, json.JSONDecodeError, AttributeError):
                unauthorized_items = []
            lines.extend([
                f"## {metadata['name']}",
                "",
                f"**Issue:** {metadata['vulnerability'] or 'No issue description configured.'}",
                "",
            ])
            for item in unauthorized_items:
                if name == "applications":
                    heading = f"Unauthorized application: `{item}`"
                    description = "The package is expected to be installed in the vulnerable practice state. Remediation removes the package."
                else:
                    heading = f"Unauthorized service: `{item}`"
                    description = "The service is expected to be enabled and running in the vulnerable practice state. Remediation stops and disables it but leaves the package installed."
                lines.extend([
                    f"### {heading}",
                    "",
                    description,
                    "",
                    f"**Remediation:** {metadata['fix'] or 'No remediation guidance configured.'}",
                    "",
                ])
            if not unauthorized_items:
                lines.extend(["No unauthorized entries are configured.", ""])
            continue

        lines.extend([
            f"## {metadata['name']}",
            "",
            f"**Issue:** {metadata['vulnerability'] or 'No issue description configured.'}",
            "",
            f"**Remediation:** {metadata['fix'] or 'No remediation guidance configured.'}",
            "",
        ])

    if not modules:
        lines.extend(["No modules are configured.", ""])

    ANSWER_KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    ANSWER_KEY_PATH.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Wrote answer key to %s.", ANSWER_KEY_PATH)


def write_scoring_report() -> None:
    """Populate the scoring report from live detector results."""
    modules = load_config()
    checks = collect_scores()
    metadata = {name: load_module_properties(name) for name in modules}
    user_lists = load_user_lists() if "users" in modules else None
    def configured_finding_count(name: str) -> int:
        if name == "users" and user_lists is not None:
            return (
                len(user_lists["unauthorizedUsers"])
                + len(set(user_lists["unauthorizedAdministrators"])
                      - set(user_lists["unauthorizedUsers"]))
            )
        policy_files = {
            "applications": ("applications.json", "unauthorizedApplications"),
            "services": ("services.json", "unauthorizedServices"),
        }
        if name in policy_files:
            filename, key = policy_files[name]
            try:
                data = json.loads(
                    (ROOT / "src" / name / filename).read_text(encoding="utf-8")
                )
            except (OSError, json.JSONDecodeError):
                return 0
            values = data.get(key, []) if isinstance(data, dict) else []
            return len(values) if isinstance(values, list) else 0
        return 1

    total_points = sum(
        metadata[name]["points"] * configured_finding_count(name)
        for name in modules
    )
    fixed = [item for item in checks if item["status"] == "fixed"]
    errors = [item for item in checks if item["status"] == "error"]
    score = sum(item.get("points", metadata[item["name"]]["points"]) for item in fixed)
    issue_rows = Markup("<br>").join(
        Markup("{}").format(
            item.get("message") or metadata[item["name"]]["fixed_message"]
            or metadata[item["name"]]["name"]
        )
        for item in fixed
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
        "STALE_REPORT_WARNING": Markup(""), "SCORE": f"{score:g}",
        "TOTAL_POINTS": f"{total_points:g}", "REMOTE_LINKS_SECTION": Markup(""),
        "OVERALL_COLOR": overall_color, "OVERALL_STATUS": overall_status,
        "NET_COLOR": "gray", "NET_STATUS": "Not checked", "PENALTY_COUNT": 0,
        "DETRACTED_POINTS": 0, "PENALTY_ROWS": Markup("None"),
        "FIXED_COUNT": len(fixed), "SCORED_VULNS": len(checks),
        "CONTRIBUTED_POINTS": f"{score:g}",
        "ISSUES": issue_rows,
    }
    REPORT_PATH.write_text(render_template("ScoringReport.html", context), encoding="utf-8")
    logger.info("Wrote scoring report to %s.", REPORT_PATH)


def write_desktop_launcher() -> None:
    """Create a desktop shortcut that opens the already-running scoring service."""
    desktop_dir = DESKTOP_README_PATH.parent
    desktop_dir.mkdir(parents=True, exist_ok=True)
    launcher_path = desktop_dir / "Scoring Report.desktop"
    launcher = "\n".join((
        "[Desktop Entry]", "Version=1.0", "Type=Application",
        "Name=Scoring Report", "Comment=Open the local cp-sim scoring report",
        "Exec=xdg-open http://127.0.0.1:5000/", "Terminal=false",
        "Categories=Education;Development;", "",
    ))
    launcher_path.write_text(launcher, encoding="utf-8")
    launcher_path.chmod(0o755)
    logger.info("Created desktop launcher at %s.", launcher_path)
