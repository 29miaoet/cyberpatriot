#!/usr/bin/env bash
set -euo pipefail
source ../common.sh
cp_sim_write_root_file /etc/apt/apt.conf.d/20auto-upgrades 644 <<'EOF'
APT::Periodic::Update-Package-Lists "0";
APT::Periodic::Unattended-Upgrade "0";
EOF
