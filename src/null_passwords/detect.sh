#!/usr/bin/env bash
set -euo pipefail
file=/etc/pam.d/common-auth
[[ -r "$file" ]] || exit 2
if grep -E '^[[:space:]]*[^#].*pam_unix\.so.*(^|[[:space:]])nullok([[:space:]]|$)' "$file" >/dev/null; then
    exit 1
fi
grep -Eq '^[[:space:]]*[^#].*pam_unix\.so' "$file" || exit 2
exit 0
