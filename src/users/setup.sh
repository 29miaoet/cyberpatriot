#!/usr/bin/env bash
set -euo pipefail

USERS_FILE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/users.json"
if [[ ! -r "$USERS_FILE" ]]; then
    printf 'users: cannot read %s\n' "$USERS_FILE" >&2
    exit 2
fi

CONFIG="$(python3 - "$USERS_FILE" <<'PY'
import json
import re
import sys

path = sys.argv[1]
keys = ("authorizedUsers", "unauthorizedUsers",
        "authorizedAdministrators", "unauthorizedAdministrators")
try:
    with open(path, encoding="utf-8") as stream:
        data = json.load(stream)
except (OSError, json.JSONDecodeError) as exc:
    raise SystemExit(f"users: invalid users.json: {exc}")
if not isinstance(data, dict) or set(data) != set(keys):
    raise SystemExit("users: users.json must contain exactly the four required arrays")
pattern = re.compile(r"^(?!root$)[a-z_][a-z0-9_-]*[$]?$")
for key in keys:
    values = data[key]
    if not isinstance(values, list):
        raise SystemExit(f"users: {key} must be an array")
    if any(not isinstance(value, str) or not pattern.fullmatch(value) for value in values):
        raise SystemExit(f"users: {key} contains an invalid or protected username")
    if len(values) != len(set(values)):
        raise SystemExit(f"users: {key} contains duplicate usernames")
    for value in values:
        print(f"{key}:{value}")
PY
)" || exit 2

declare -A AUTH_USERS=() UNAUTH_USERS=() AUTH_ADMINS=() UNAUTH_ADMINS=()
while IFS=: read -r key username; do
    [[ -n "${key:-}" && -n "${username:-}" ]] || continue
    case "$key" in
        authorizedUsers) AUTH_USERS["$username"]=1 ;;
        unauthorizedUsers) UNAUTH_USERS["$username"]=1 ;;
        authorizedAdministrators) AUTH_ADMINS["$username"]=1 ;;
        unauthorizedAdministrators) UNAUTH_ADMINS["$username"]=1 ;;
    esac
done <<< "$CONFIG"

run_privileged() {
    if [[ "$EUID" -eq 0 ]]; then
        "$@"
    else
        sudo "$@"
    fi
}

is_admin() {
    local username="$1" groups
    groups="$(id -nG "$username" 2>/dev/null)" || return 1
    [[ " $groups " =~ [[:space:]](sudo|admin|wheel)[[:space:]] ]]
}

# Ensure the standard Debian/Ubuntu administrative group exists.
if ! getent group sudo >/dev/null; then
    run_privileged groupadd sudo
fi

# An administrator is also an account that must exist.
for username in "${!AUTH_USERS[@]}" "${!AUTH_ADMINS[@]}"; do
    [[ -n "$username" ]] || continue
    # An explicitly unauthorized user must never be recreated.
    [[ -n "${UNAUTH_USERS[$username]:-}" ]] && continue
    if ! getent passwd "$username" >/dev/null; then
        run_privileged useradd --create-home --shell /bin/bash "$username"
        run_privileged passwd --lock "$username"
    fi
done

# Grant sudo only when the account is not explicitly denied administrator rights.
for username in "${!AUTH_ADMINS[@]}"; do
    [[ -n "$username" ]] || continue
    [[ -n "${UNAUTH_USERS[$username]:-}" ]] && continue
    [[ -n "${UNAUTH_ADMINS[$username]:-}" ]] && continue
    run_privileged usermod --append --groups sudo "$username"
done
