"""HTML report and desktop artifact generation."""
from __future__ import annotations

import html
import logging
import os
from datetime import datetime
from typing import Any

from markupsafe import Markup

from .config import DESKTOP_README_PATH, REPORT_PATH, ROOT, CpSimError, load_config, load_user_lists
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
    document = render_template("ReadMe.html", {
        "OS": os_details["pretty_name"], "TITLE": title,
        "LINUX_ROOT_POLICY": root_policy, "USER_README_HTML": user_readme_html,
        "AUTHORIZED_USERS": authorized_users,
        "AUTHORIZED_ADMINISTRATORS": authorized_administrators,
    })
    DESKTOP_README_PATH.write_text(document, encoding="utf-8")
    logger.info("Wrote module README to %s.", DESKTOP_README_PATH)


def write_scoring_report() -> None:
    """Populate the scoring report from live detector results."""
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
        ) for name in modules
    )
    fixed = [item for item in checks if item["status"] == "fixed"]
    errors = [item for item in checks if item["status"] == "error"]
    score = sum(item.get("points", metadata[item["name"]]["points"]) for item in fixed)
    point_lines = [
        f"{html.escape(item.get('label', metadata[item['name']]['name']))}: "
        f"{item.get('points', metadata[item['name']]['points']):g} points"
        for item in fixed
    ]
    point_rows = Markup("<br>\n".join(point_lines)) if point_lines else Markup(
        "No scored issues fixed yet."
    )
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
        "STALE_REPORT_WARNING": Markup(""), "SCORE": f"{score:g}",
        "TOTAL_POINTS": f"{total_points:g}", "REMOTE_LINKS_SECTION": Markup(""),
        "OVERALL_COLOR": overall_color, "OVERALL_STATUS": overall_status,
        "NET_COLOR": "gray", "NET_STATUS": "Not checked", "PENALTY_COUNT": 0,
        "DETRACTED_POINTS": 0, "PENALTY_ROWS": Markup("None"),
        "FIXED_COUNT": len(fixed), "SCORED_VULNS": len(checks),
        "CONTRIBUTED_POINTS": f"{score:g}", "POINT_ROWS": point_rows, "HINTS": hints,
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
