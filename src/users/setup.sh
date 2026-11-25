#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
USERS_FILE="$SCRIPT_DIR/users.json"

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

declare -A ALL_USERS=() ALL_ADMINS=()
while IFS=: read -r key username; do
    [[ -n "${key:-}" && -n "${username:-}" ]] || continue
    case "$key" in
        authorizedUsers|unauthorizedUsers)
            ALL_USERS["$username"]=1
            ;;
        authorizedAdministrators|unauthorizedAdministrators)
            ALL_USERS["$username"]=1
            ALL_ADMINS["$username"]=1
            ;;
    esac
done <<< "$CONFIG"

run_privileged() {
    if [[ "$EUID" -eq 0 ]]; then
        "$@"
    else
        sudo "$@"
    fi
}

# Ensure the standard Debian/Ubuntu groups used by this module exist.
for group in users sudo; do
    if ! getent group "$group" >/dev/null; then
        run_privileged groupadd --system "$group"
        printf 'users: created group %s\n' "$group"
    fi
done

# Create every configured account, including accounts intentionally marked
# unauthorized so that the practice VM starts in the configured vulnerable state.
for username in "${!ALL_USERS[@]}"; do
    [[ -n "$username" ]] || continue

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

    # All configured accounts belong to the shared users group.
    if id -nG "$username" | tr ' ' '\n' | grep -Fxq users; then
        printf 'users: %s already belongs to users\n' "$username"
    else
        run_privileged usermod --append --groups users "$username"
        printf 'users: added %s to users\n' "$username"
    fi
done

# Both authorized and unauthorized administrators receive sudo membership.
# The latter deliberately creates the vulnerable state detected by detect.sh.
for username in "${!ALL_ADMINS[@]}"; do
    [[ -n "$username" ]] || continue

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

# Verify setup responsibilities only. Deny-list remediation belongs to --fix.
for username in "${!ALL_USERS[@]}"; do
    [[ -n "$username" ]] || continue

    if ! getent passwd "$username" >/dev/null; then
        printf 'users: configured account %s is missing after setup\n' "$username" >&2
        exit 1
    fi
    if ! id -nG "$username" | tr ' ' '\n' | grep -Fxq users; then
        printf 'users: configured account %s lacks users group membership\n' "$username" >&2
        exit 1
    fi
done

for username in "${!ALL_ADMINS[@]}"; do
    [[ -n "$username" ]] || continue
    if ! id -nG "$username" | tr ' ' '\n' | grep -Fxq sudo; then
        printf 'users: configured administrator %s lacks sudo membership\n' "$username" >&2
        exit 1
    fi
done

printf 'users: configured account setup completed successfully\n'
