#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
USERS_FILE="$SCRIPT_DIR/users.json"
FIX_SCRIPT="$SCRIPT_DIR/fix.sh"

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
    printf 'users: created administrative group sudo\n'
fi

# Create all authorized accounts. Administrators are also users.
for username in "${!AUTH_USERS[@]}" "${!AUTH_ADMINS[@]}"; do
    [[ -n "$username" ]] || continue

    # Unauthorized-user removal takes precedence over authorization.
    if [[ -n "${UNAUTH_USERS[$username]:-}" ]]; then
        printf 'users: skipping %s because it is listed as unauthorized\n' "$username"
        continue
    fi

    if getent passwd "$username" >/dev/null; then
        printf 'users: account %s already exists\n' "$username"
    else
        run_privileged useradd --create-home --shell /bin/bash "$username"
        run_privileged passwd --lock "$username" >/dev/null
        printf 'users: created account %s (password locked)\n' "$username"
    fi

    if ! getent passwd "$username" >/dev/null; then
        printf 'users: account creation failed verification for %s\n' "$username" >&2
        exit 1
    fi
done

# Grant sudo only to explicitly authorized administrators.
for username in "${!AUTH_ADMINS[@]}"; do
    [[ -n "$username" ]] || continue
    [[ -n "${UNAUTH_USERS[$username]:-}" ]] && continue
    [[ -n "${UNAUTH_ADMINS[$username]:-}" ]] && continue

    if ! getent passwd "$username" >/dev/null; then
        printf 'users: cannot grant administrator privileges; account %s is missing\n' "$username" >&2
        exit 1
    fi
    if id -nG "$username" | tr ' ' '\n' | grep -Fxq sudo; then
        printf 'users: %s already belongs to sudo\n' "$username"
    else
        run_privileged usermod --append --groups sudo "$username"
        printf 'users: granted sudo membership to %s\n' "$username"
    fi
done

# Apply the deny lists too: remove unauthorized accounts and demote
# unauthorized administrators, while preserving the precedence rule.
if [[ ! -f "$FIX_SCRIPT" ]]; then
    printf 'users: required remediation script is missing: %s\n' "$FIX_SCRIPT" >&2
    exit 1
fi
/bin/bash "$FIX_SCRIPT"

# Verify the requested account policy after remediation.
for username in "${!AUTH_USERS[@]}" "${!AUTH_ADMINS[@]}"; do
    [[ -n "$username" ]] || continue
    if [[ -n "${UNAUTH_USERS[$username]:-}" ]]; then
        if getent passwd "$username" >/dev/null; then
            printf 'users: unauthorized account %s still exists after remediation\n' "$username" >&2
            exit 1
        fi
        continue
    fi
    if ! getent passwd "$username" >/dev/null; then
        printf 'users: authorized account %s is missing after setup\n' "$username" >&2
        exit 1
    fi
done

for username in "${!AUTH_ADMINS[@]}"; do
    [[ -n "$username" ]] || continue
    [[ -n "${UNAUTH_USERS[$username]:-}" || -n "${UNAUTH_ADMINS[$username]:-}" ]] && continue
    if ! is_admin "$username"; then
        printf 'users: authorized administrator %s lacks administrative group membership\n' "$username" >&2
        exit 1
    fi
done

printf 'users: account setup and policy verification completed successfully\n'
