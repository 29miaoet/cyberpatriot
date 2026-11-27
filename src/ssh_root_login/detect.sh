#!/usr/bin/env bash
set -euo pipefail
source ../common.sh
value="$(cp_sim_sshd_value permitrootlogin)" || exit 2
[[ "$value" == "no" ]] && exit 0
exit 1
