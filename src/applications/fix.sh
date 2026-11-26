#!/usr/bin/env bash
set -euo pipefail

MODULE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$MODULE_DIR/applications.json"

if [[ ! -r "$CONFIG_FILE" ]]; then
    printf 'applications: cannot read %s\n' "$CONFIG_FILE" >&2
    exit 2
fi

CONFIG="$(python3 - "$CONFIG_FILE" <<'PY'
import json
import re
import sys

keys = ("authorizedApplications", "unauthorizedApplications")
try:
    with open(sys.argv[1], encoding="utf-8") as stream:
        data = json.load(stream)
except (OSError, json.JSONDecodeError) as exc:
    raise SystemExit(f"applications: invalid applications.json: {exc}")
if not isinstance(data, dict) or set(data) != set(keys):
    raise SystemExit("applications: applications.json must contain exactly the two required arrays")
pattern = re.compile(r"^[a-z0-9][a-z0-9+.-]*$")
seen = set()
for key in keys:
    values = data[key]
    if not isinstance(values, list) or any(not isinstance(x, str) or not pattern.fullmatch(x) for x in values):
        raise SystemExit(f"applications: {key} must be an array of valid Debian package names")
    if len(values) != len(set(values)):
        raise SystemExit(f"applications: {key} contains duplicate package names")
    overlap = seen.intersection(values)
    if overlap:
        raise SystemExit(f"applications: package appears in both policy lists: {sorted(overlap)}")
    seen.update(values)
    if key == "unauthorizedApplications":
        for value in values:
            print(value)
PY
)" || exit 2
PACKAGES=()
if [[ -n "$CONFIG" ]]; then
    mapfile -t PACKAGES <<< "$CONFIG"
fi

run_privileged() {
    if [[ "$EUID" -eq 0 ]]; then "$@"; else sudo "$@"; fi
}

export DEBIAN_FRONTEND=noninteractive
for package in "${PACKAGES[@]}"; do
    status="$(dpkg-query -W -f='${db:Status-Status}' "$package" 2>/dev/null || true)"
    if [[ "$status" == installed ]]; then
        run_privileged apt-get remove --yes -- "$package"
        printf 'applications: removed unauthorized application %s\n' "$package"
    fi
done

printf 'applications: unauthorized application remediation completed\n'
