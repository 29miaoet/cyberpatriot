#!/usr/bin/env bash
set -euo pipefail
value="$(sysctl -n "net.ipv4.ip_forward" 2>/dev/null)" || exit 2
[[ "$value" == "0" ]] && exit 0
exit 1
