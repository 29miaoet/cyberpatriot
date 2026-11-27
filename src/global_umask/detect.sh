#!/usr/bin/env bash
set -euo pipefail
grep -Eq '^[[:space:]]*UMASK[[:space:]]+027([[:space:]]|$)' /etc/login.defs || exit 1
profile=/etc/profile.d/99-cp-sim-umask.sh
[[ -r "$profile" ]] || exit 1
grep -Eq '^[[:space:]]*umask[[:space:]]+027([[:space:]]|$)' "$profile" || exit 1
exit 0
