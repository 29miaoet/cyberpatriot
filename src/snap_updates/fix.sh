#!/usr/bin/env bash
set -euo pipefail
source ../common.sh
if command -v snap >/dev/null; then
    cp_sim_root snap refresh
fi
