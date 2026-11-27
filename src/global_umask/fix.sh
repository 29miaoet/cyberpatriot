#!/usr/bin/env bash
set -euo pipefail
source ../common.sh
cp_sim_set_login_def UMASK 027
cp_sim_write_root_file /etc/profile.d/99-cp-sim-umask.sh 644 <<'EOF'
# Managed by cp-sim: restrict default permissions for login shells.
umask 027
EOF
printf 'global_umask: login defaults updated; existing sessions are unchanged\n'
