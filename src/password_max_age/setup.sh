#!/usr/bin/env bash
set -euo pipefail
source ../common.sh
while IFS=: read -r username password uid gid gecos home shell; do
    [[ "$uid" =~ ^[0-9]+$ ]] || continue
    (( uid >= 1000 && uid != 65534 )) || continue
    [[ "$shell" != */nologin && "$shell" != */false ]] || continue
    cp_sim_root chage --maxdays 99999 "$username"
done < <(getent passwd)
