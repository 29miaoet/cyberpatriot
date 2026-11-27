#!/usr/bin/env bash
set -euo pipefail
source ../common.sh
status="$(cp_sim_root passwd -S root 2>/dev/null | awk '{print $2}')" || exit 2
[[ "$status" == "L" || "$status" == "LK" ]] && exit 0
exit 1
