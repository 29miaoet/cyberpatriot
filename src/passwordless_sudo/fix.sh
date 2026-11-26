#!/usr/bin/env bash
set -euo pipefail
source ../common.sh
command -v python3 >/dev/null || exit 2
cp_sim_root python3 - <<'PY'
import pathlib
import re
import subprocess

paths = [pathlib.Path("/etc/sudoers")]
directory = pathlib.Path("/etc/sudoers.d")
if directory.is_dir():
    paths.extend(path for path in sorted(directory.iterdir()) if path.is_file() and not path.is_symlink())
originals = {}
for path in paths:
    try:
        original = path.read_bytes()
    except OSError:
        continue
    updated = re.sub(rb"(?i)\bNOPASSWD\s*:", b"PASSWD:", original)
    if updated != original:
        originals[path] = original
        path.write_bytes(updated)

result = subprocess.run(["visudo", "-c"], check=False)
if result.returncode:
    for path, original in originals.items():
        path.write_bytes(original)
    raise SystemExit("visudo rejected the edited sudoers policy; original files restored")
PY
