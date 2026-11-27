#!/usr/bin/env bash
set -euo pipefail
source ../common.sh
cp_sim_set_sysctl "net.ipv4.tcp_syncookies" "0" "tcp_syncookies"
