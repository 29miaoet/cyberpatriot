#!/usr/bin/env bash
set -euo pipefail
source ../common.sh
cp_sim_set_sysctl "kernel.randomize_va_space" "0" "address_space_randomization"
