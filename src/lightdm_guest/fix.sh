#!/usr/bin/env bash
set -euo pipefail
if command -v lightdm >/dev/null; then
    source ../common.sh
    cp_sim_set_lightdm_guest false
fi
