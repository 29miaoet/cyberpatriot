#!/usr/bin/env bash
set -euo pipefail
if ! command -v snap >/dev/null; then
    exit 0
fi
output="$(snap refresh --list 2>&1)" || {
    printf '%s\n' "$output" >&2
    exit 2
}
if printf '%s\n' "$output" | grep -Eq '^[[:alnum:]_][[:alnum:]._+-]*[[:space:]]+[0-9]'; then
    exit 1
fi
exit 0
