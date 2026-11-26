#!/usr/bin/env bash
set -euo pipefail
if ! command -v lightdm >/dev/null; then
    exit 0
fi
output="$(lightdm --show-config 2>&1)" || {
    printf '%s\n' "$output" >&2
    exit 2
}
value="$(printf '%s\n' "$output" | awk -F= '/^[[:space:]]*allow-guest[[:space:]]*=/ {gsub(/[[:space:]]/, "", $2); value=$2} END {print value}')"
[[ "$value" == "false" ]] && exit 0
exit 1
