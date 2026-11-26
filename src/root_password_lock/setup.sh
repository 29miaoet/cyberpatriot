#!/usr/bin/env bash
set -euo pipefail
source ../common.sh
status="$(cp_sim_root passwd -S root | awk '{print $2}')"
if [[ "$status" == "L" || "$status" == "LK" ]]; then
    hash="$(cp_sim_root getent shadow root | cut -d: -f2)"
    hash="$(printf '%s' "$hash" | sed 's/^!//')"
    if [[ -n "$hash" && "$hash" != "*" && "$hash" != "!" && "$hash" != \!* ]]; then
        cp_sim_root passwd -u root
    else
        printf 'root_password_lock: root has no usable password hash; leaving it locked\n'
    fi
fi
