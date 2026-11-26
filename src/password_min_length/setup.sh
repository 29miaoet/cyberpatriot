#!/usr/bin/env bash
set -euo pipefail
source ../common.sh
cp_sim_set_pam_unix_option /etc/pam.d/common-password minlen 6
