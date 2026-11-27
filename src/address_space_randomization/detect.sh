#!/usr/bin/env bash
set -euo pipefail
value="$(sysctl -n "kernel.randomize_va_space" 2>/dev/null)" || exit 2
[[ "$value" == "2" ]] && exit 0
exit 1
