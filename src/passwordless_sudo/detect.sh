#!/usr/bin/env bash
set -euo pipefail
source ../common.sh
cp_sim_root python3 - <<'PY'
import pathlib
import re

paths = [pathlib.Path("/etc/sudoers")]
directory = pathlib.Path("/etc/sudoers.d")
if directory.is_dir():
    paths.extend(path for path in directory.iterdir() if path.is_file() and not path.is_symlink())
for path in paths:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        raise SystemExit(2)
    if any(not line.lstrip().startswith("#") and re.search(r"\bNOPASSWD\s*:", line, re.IGNORECASE) for line in lines):
        print(f"UNRESOLVED: {path}")
        raise SystemExit(1)
raise SystemExit(0)
PY
