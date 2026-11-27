#!/usr/bin/env bash
set -euo pipefail
source ../common.sh
CONFIG="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/authorizedRootAccounts.json"
CONFIG_DATA="$(python3 - "$CONFIG" <<'PY'
import json
import re
import subprocess
import sys

try:
    data = json.load(open(sys.argv[1], encoding="utf-8"))
except (OSError, json.JSONDecodeError) as exc:
    raise SystemExit(f"uid0_accounts: invalid allowlist: {exc}")
if not isinstance(data, dict) or set(data) != {"authorizedRootAccounts"}:
    raise SystemExit("uid0_accounts: expected authorizedRootAccounts array")
allowed = data["authorizedRootAccounts"]
if not isinstance(allowed, list) or not allowed or "root" not in allowed or any(
    not isinstance(x, str) or not re.fullmatch(r"[a-z_][a-z0-9_-]*[$]?", x) for x in allowed
) or len(allowed) != len(set(allowed)):
    raise SystemExit("uid0_accounts: invalid or duplicate account names in allowlist")
entries = subprocess.check_output(["getent", "passwd"], text=True)
for line in entries.splitlines():
    fields = line.split(":")
    if len(fields) >= 4 and fields[2] == "0" and fields[0] not in allowed:
        print(fields[0])
PY
)" || exit 2
mapfile -t UNAUTHORIZED <<< "$CONFIG_DATA"
if ((${#UNAUTHORIZED[@]} == 0)) || [[ -z "${UNAUTHORIZED[0]:-}" ]]; then
    printf '%s\n' 'uid0_accounts: no unapproved UID-0 accounts found'
    exit 0
fi
printf '%s\n' 'uid0_accounts: accounts scheduled for removal (home directories will be preserved):'
printf '  %s\n' "${UNAUTHORIZED[@]}"
cp_sim_confirm "Remove these UID-0 accounts while preserving their home directories?" || exit 0
for username in "${UNAUTHORIZED[@]}"; do
    cp_sim_root userdel "$username"
    printf 'uid0_accounts: removed account %s; home directory was not deleted\n' "$username"
done
