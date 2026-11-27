#!/usr/bin/env bash
set -euo pipefail
source ../common.sh
cp_sim_set_sshd_option PermitEmptyPasswords no
