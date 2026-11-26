#!/usr/bin/env bash
set -euo pipefail
file=/etc/pam.d/common-password
[[ -r "$file" ]] || exit 2
awk '
    /^[[:space:]]*#/ { next }
    /pam_pwhistory\.so/ {
        found=1
        if ($0 !~ /remember=3([[:space:]]|$)/ || $0 !~ /use_authtok/) bad=1
    }
    END { if (!found || bad) exit 1; exit 0 }
' "$file"
