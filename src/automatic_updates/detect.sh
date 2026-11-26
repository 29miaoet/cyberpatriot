#!/usr/bin/env bash
set -euo pipefail
if ! command -v apt-config >/dev/null; then
    exit 2
fi
settings="$(apt-config dump 2>/dev/null)" || exit 2
printf '%s\n' "$settings" | grep -Eq '^APT::Periodic::Update-Package-Lists "1";$' || exit 1
printf '%s\n' "$settings" | grep -Eq '^APT::Periodic::Unattended-Upgrade "1";$' || exit 1
exit 0
