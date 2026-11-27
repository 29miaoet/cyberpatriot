#!/usr/bin/env bash
set -euo pipefail
[[ -e /etc/shadow ]] || exit 2
mode="$(stat -c '%a' /etc/shadow)" || exit 2
[[ "$mode" == "600" ]] && exit 0
exit 1
