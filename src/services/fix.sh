#!/usr/bin/env bash
set -euo pipefail

MODULE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$MODULE_DIR/services.json"

if [[ ! -r "$CONFIG_FILE" ]]; then
    printf 'services: cannot read %s\n' "$CONFIG_FILE" >&2
    exit 2
fi

CONFIG="$(python3 - "$CONFIG_FILE" <<'PY'
import json
import sys

keys = ("authorizedServices", "unauthorizedServices")
try:
    with open(sys.argv[1], encoding="utf-8") as stream:
        data = json.load(stream)
except (OSError, json.JSONDecodeError) as exc:
    raise SystemExit(f"services: invalid services.json: {exc}")
if not isinstance(data, dict) or set(data) != set(keys):
    raise SystemExit("services: services.json must contain exactly the two required arrays")
allowed = {"ssh", "vsftpd", "postfix", "apache2"}
seen = set()
for key in keys:
    values = data[key]
    if not isinstance(values, list) or any(not isinstance(x, str) or x not in allowed for x in values):
        raise SystemExit(f"services: {key} contains an unsupported service; supported values: {', '.join(sorted(allowed))}")
    if len(values) != len(set(values)):
        raise SystemExit(f"services: {key} contains duplicate service names")
    overlap = seen.intersection(values)
    if overlap:
        raise SystemExit(f"services: service appears in both policy lists: {sorted(overlap)}")
    seen.update(values)
    if key == "unauthorizedServices":
        for value in values:
            print(value)
PY
)" || exit 2
SERVICES=()
if [[ -n "$CONFIG" ]]; then
    mapfile -t SERVICES <<< "$CONFIG"
fi

declare -A UNITS=([ssh]=ssh.service [vsftpd]=vsftpd.service [postfix]=postfix.service [apache2]=apache2.service)

run_privileged() {
    if [[ "$EUID" -eq 0 ]]; then "$@"; else sudo "$@"; fi
}

for service in "${SERVICES[@]}"; do
    unit="${UNITS[$service]}"
    if systemctl list-unit-files "$unit" --no-legend 2>/dev/null | grep -Fq "$unit"; then
        run_privileged systemctl disable --now "$unit"
        printf 'services: stopped and disabled unauthorized service %s\n' "$service"
    else
        printf 'services: %s is not installed; nothing to disable\n' "$service"
    fi
done

printf 'services: unauthorized service remediation completed\n'
