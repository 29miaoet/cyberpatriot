#!/usr/bin/env bash
set -euo pipefail
source ../common.sh
while IFS=: read -r username password uid gid gecos home shell; do
    [[ "$uid" =~ ^[0-9]+$ ]] || continue
    (( uid >= 1000 && uid != 65534 )) || continue
    [[ "$shell" != */nologin && "$shell" != */false ]] || continue
    value="$(cp_sim_root getent shadow "$username" | cut -d: -f5)" || exit 2
    [[ "$value" == "90" ]] || {
        printf 'MAX_PASSWORD_AGE:%s:%s\n' "$username" "$value"
        exit 1
    }
done < <(getent passwd)
exit 0
