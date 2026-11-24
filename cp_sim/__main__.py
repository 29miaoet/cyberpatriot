"""Command-line startup for cp-sim; invoked only by the main.sh launcher."""
from __future__ import annotations

import argparse
import logging
import subprocess

from .config import CpSimError, HOST, PORT, load_config, load_user_lists, module_directory
from .environment import require_vm
from .modules import apply_setups
from .reports import write_desktop_launcher, write_module_readme, write_scoring_report
from .web import app

logger = logging.getLogger("cp-sim")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the VM-only cp-sim scoring service.")
    parser.add_argument(
        "--apply", action="store_true",
        help="execute configured setup.sh scripts before starting the service",
    )
    args = parser.parse_args()
    try:
        require_vm()
        modules = load_config()
        for name in modules:
            module_directory(name)
        if "users" in modules:
            load_user_lists()
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
