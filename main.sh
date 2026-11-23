#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

# Refuse to install packages or run on a physical host.
is_vm=false
if command -v systemd-detect-virt >/dev/null 2>&1 \
    && systemd-detect-virt --vm --quiet; then
    is_vm=true
else
    for dmi_file in \
        /sys/class/dmi/id/sys_vendor \
        /sys/class/dmi/id/product_name \
        /sys/class/dmi/id/board_vendor; do
        if [[ -r "$dmi_file" ]] \
            && grep -Eiq 'kvm|qemu|vmware|virtualbox|innotek|microsoft corporation|virtual machine|xen|parallels|bhyve|amazon ec2|google' "$dmi_file"; then
            is_vm=true
            break
        fi
    done
fi

if [[ "$is_vm" != true ]] \
    && grep -Eiq '^flags[[:space:]]*:.*(^|[[:space:]])hypervisor([[:space:]]|$)' /proc/cpuinfo 2>/dev/null; then
    is_vm=true
fi

if [[ "$is_vm" != true ]]; then
    printf 'cp-sim: VM safety check failed; refusing to install dependencies or run.\n' >&2
    exit 1
fi

if [[ ! -r /etc/os-release ]]; then
    printf 'cp-sim: cannot identify the Linux distribution.\n' >&2
    exit 1
fi
# shellcheck disable=SC1091
source /etc/os-release

# Pass distribution metadata to the Python template renderer.
export CP_SIM_OS_ID="${ID:-linux}"
export CP_SIM_OS_PRETTY_NAME="${PRETTY_NAME:-${NAME:-Linux}}"
export CP_SIM_OS_VERSION="${VERSION_ID:-}"

# Fail early with a useful message if either HTML template is missing.
for template in ReadMe.html ScoringReport.html; do
    if [[ ! -f "$ROOT/templates/$template" ]]; then
        printf 'cp-sim: required template is missing: %s\n' "$ROOT/templates/$template" >&2
        exit 1
    fi
done
if [[ "${ID:-} ${ID_LIKE:-}" != *debian* && "${ID:-} ${ID_LIKE:-}" != *ubuntu* ]]; then
    printf 'cp-sim: automatic dependency installation supports Debian/Ubuntu-based distributions only.\n' >&2
    exit 1
fi
if ! command -v apt-get >/dev/null 2>&1; then
    printf 'cp-sim: apt-get is required to install system dependencies.\n' >&2
    exit 1
fi

if [[ "$EUID" -eq 0 ]]; then
    APT=(apt-get)
else
    if ! command -v sudo >/dev/null 2>&1; then
        printf 'cp-sim: run as root or install sudo to install system dependencies.\n' >&2
        exit 1
    fi
    APT=(sudo apt-get)
fi

packages_missing=false
for package in python3 python3-venv python3-pip; do
    if ! dpkg-query -W -f='${Status}' "$package" 2>/dev/null | grep -q 'install ok installed'; then
        packages_missing=true
        break
    fi
done

if [[ "$packages_missing" == true ]]; then
    "${APT[@]}" update
    "${APT[@]}" install -y python3 python3-venv python3-pip
fi

VENV="$ROOT/.venv"
python3 -m venv "$VENV"
"$VENV/bin/python" -m pip install -r "$ROOT/requirements.txt"

exec "$VENV/bin/python" "$ROOT/main.py" "$@"
