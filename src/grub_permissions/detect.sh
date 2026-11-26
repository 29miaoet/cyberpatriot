#!/usr/bin/env bash
set -euo pipefail
if [[ ! -e /boot/grub/grub.cfg ]]; then
    exit 0
fi
mode="$(stat -c '%a' /boot/grub/grub.cfg)" || exit 2
[[ "$mode" == "600" ]] && exit 0
exit 1
