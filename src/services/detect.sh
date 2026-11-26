#!/usr/bin/env bash
set -euo pipefail

MODULE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$MODULE_DIR/services.json"

if [[ ! -r "$CONFIG_FILE" ]]; then
    printf 'services: cannot read %s\n' "$CONFIG_FILE" >&2
    exit 2
fi

mapfile -t SERVICES < <(python3 - "$CONFIG_FILE" <<'PY'
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
) || exit 2

declare -A UNITS=([ssh]=ssh.service [vsftpd]=vsftpd.service [postfix]=postfix.service [apache2]=apache2.service)
findings=0

for service in "${SERVICES[@]}"; do
    unit="${UNITS[$service]}"
    active=0
    enabled=0
    systemctl is-active --quiet "$unit" 2>/dev/null && active=1
    systemctl is-enabled --quiet "$unit" 2>/dev/null && enabled=1
    if ((active || enabled)); then
        printf 'UNAUTHORIZED_SERVICE:%s\n' "$service"
        findings=1
    fi
done

exit "$findings"
