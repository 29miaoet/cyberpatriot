#!/usr/bin/env bash
set -euo pipefail
source ../common.sh
command -v apt-get >/dev/null || {
    printf 'apt_updates: apt-get is not available\n' >&2
    exit 2
}
cp_sim_root apt-get update
cp_sim_root env DEBIAN_FRONTEND=noninteractive apt-get -y upgrade
cp_sim_root env DEBIAN_FRONTEND=noninteractive apt-get -y full-upgrade
