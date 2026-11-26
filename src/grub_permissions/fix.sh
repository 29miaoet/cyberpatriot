#!/usr/bin/env bash
set -euo pipefail
if [[ -e /boot/grub/grub.cfg ]]; then
    source ../common.sh
    cp_sim_root chmod 600 /boot/grub/grub.cfg
fi
