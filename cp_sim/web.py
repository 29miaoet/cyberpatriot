"""Flask application and local scoring endpoints."""
from __future__ import annotations

import logging
import subprocess
from datetime import datetime, timezone

from flask import Flask, jsonify, send_file, send_from_directory

from .config import HOST, PORT, REPORT_PATH, ROOT, CpSimError
from .scoring import collect_scores

app = Flask(__name__, template_folder=str(ROOT / "templates"))
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("cp-sim")


@app.get("/")
def scoring_report():
    try:
        from .reports import write_scoring_report
        write_scoring_report()
    except (CpSimError, OSError, subprocess.SubprocessError) as exc:
        logger.error("Could not refresh scoring report: %s", exc)
        return "Unable to generate scoring report. Check the cp-sim terminal output.", 500
    response = send_file(REPORT_PATH, max_age=0)
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/background.jpg")
def background_image():
    """Serve the README background image from the templates directory."""
    return send_from_directory(ROOT / "templates", "background.jpg", max_age=3600)


@app.get("/logo.svg")
def logo_image():
    """Serve the README logo from the templates directory."""
    return send_from_directory(ROOT / "templates", "logo.svg", max_age=3600)


@app.get("/api/scores")
def api_scores():
    try:
        checks = collect_scores()
    except CpSimError as exc:
        return jsonify({"error": str(exc), "checks": []}), 500
    return jsonify({"timestamp": datetime.now(timezone.utc).isoformat(), "checks": checks})
