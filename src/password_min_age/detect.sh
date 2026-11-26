#!/usr/bin/env bash
set -euo pipefail
awk '
    $1 == "PASS_MIN_DAYS" { found=1; value=$2 }
    END { if (!found) exit 2; if (value == 2) exit 0; exit 1 }
' /etc/login.defs
