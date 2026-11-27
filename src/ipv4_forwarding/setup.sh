#!/usr/bin/env bash
set -euo pipefail
source ../common.sh
cp_sim_set_sysctl "net.ipv4.ip_forward" "1" "ipv4_forwarding"
