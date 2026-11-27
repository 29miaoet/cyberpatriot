#!/usr/bin/env bash
set -euo pipefail
source ../common.sh
command -v apt-get >/dev/null || exit 2
if ! dpkg -s unattended-upgrades >/dev/null 2>&1; then
    cp_sim_root env DEBIAN_FRONTEND=noninteractive apt-get install -y unattended-upgrades
fi
cp_sim_write_root_file /etc/apt/apt.conf.d/20auto-upgrades 644 <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
EOF
