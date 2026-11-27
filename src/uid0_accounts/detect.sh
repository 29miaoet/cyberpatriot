#!/usr/bin/env bash
set -euo pipefail
CONFIG="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/authorizedRootAccounts.json"
python3 - "$CONFIG" <<'PY'
import json
import re
import subprocess
import sys

try:
    data = json.load(open(sys.argv[1], encoding="utf-8"))
except (OSError, json.JSONDecodeError) as exc:
    print(f"uid0_accounts: invalid allowlist: {exc}", file=sys.stderr)
    raise SystemExit(2)
if not isinstance(data, dict) or set(data) != {"authorizedRootAccounts"}:
    raise SystemExit("uid0_accounts: expected authorizedRootAccounts array")
allowed = data["authorizedRootAccounts"]
if not isinstance(allowed, list) or not allowed or "root" not in allowed or any(
    not isinstance(x, str) or not re.fullmatch(r"[a-z_][a-z0-9_-]*[$]?", x) for x in allowed
) or len(allowed) != len(set(allowed)):
    raise SystemExit("uid0_accounts: invalid or duplicate account names in allowlist")
try:
    entries = subprocess.check_output(["getent", "passwd"], text=True)
except subprocess.CalledProcessError as exc:
    raise SystemExit(f"uid0_accounts: getent failed: {exc.returncode}")
unexpected = []
for line in entries.splitlines():
    fields = line.split(":")
    if len(fields) >= 4 and fields[2] == "0" and fields[0] not in allowed:
        unexpected.append(fields[0])
if unexpected:
    print("uid0_accounts: unapproved UID-0 accounts: " + ", ".join(unexpected))
    raise SystemExit(1)
raise SystemExit(0)
PY
