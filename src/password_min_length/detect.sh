#!/usr/bin/env bash
set -euo pipefail
file=/etc/pam.d/common-password
[[ -r "$file" ]] || exit 2
awk '
    /^[[:space:]]*#/ { next }
    /pam_unix\.so/ {
        found=1
        if ($0 !~ /(^|[[:space:]])minlen=10([[:space:]]|$)/) bad=1
    }
    END { if (!found) exit 2; if (bad) exit 1; exit 0 }
' "$file"
