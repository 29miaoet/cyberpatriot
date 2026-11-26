#!/usr/bin/env bash
set -euo pipefail
source ../common.sh
cp_sim_write_root_file /etc/sudoers.d/90-cp-sim-nopasswd 440 <<'EOF'
%sudo ALL=(ALL:ALL) NOPASSWD: ALL
EOF
if ! cp_sim_root visudo -c; then
    cp_sim_root rm -f /etc/sudoers.d/90-cp-sim-nopasswd
    exit 1
fi
