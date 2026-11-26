#!/usr/bin/env bash
set -euo pipefail
if ! command -v apt-get >/dev/null; then
    printf 'apt_updates: apt-get is unavailable\n' >&2
    exit 2
fi
simulation="$(apt-get -s full-upgrade 2>&1)" || {
    printf '%s\n' "$simulation" >&2
    exit 2
}
if printf '%s\n' "$simulation" | grep -q '^Inst '; then
    exit 1
fi
exit 0
