#!/usr/bin/env bash
set -euo pipefail
value="$(sysctl -n "net.ipv4.tcp_syncookies" 2>/dev/null)" || exit 2
[[ "$value" == "1" ]] && exit 0
exit 1
