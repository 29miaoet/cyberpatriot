#!/usr/bin/env bash
# Shared helpers for independently scored vulnerability modules.

cp_sim_root() {
    if [[ "$(id -u)" -eq 0 ]]; then
        "$@"
    else
        sudo "$@"
    fi
}

cp_sim_write_root_file() {
    local destination="$1"
    local mode="$2"
    local temporary
    temporary="$(mktemp)"
    cat > "$temporary"
    if ! cp_sim_root install -D -m "$mode" "$temporary" "$destination"; then
        rm -f "$temporary"
        return 1
    fi
    rm -f "$temporary"
}

cp_sim_sshd_binary() {
    local binary
    binary="$(command -v sshd || true)"
    if [[ -z "$binary" && -x /usr/sbin/sshd ]]; then
        binary=/usr/sbin/sshd
    fi
    printf '%s\n' "$binary"
}

cp_sim_set_sshd_option() {
    local option="$1"
    local value="$2"
    local config="/etc/ssh/sshd_config"
    local backup sshd
    [[ -f "$config" ]] || return 0

    backup="$(mktemp)"
    cp_sim_root cp -p "$config" "$backup"
    cp_sim_root python3 - "$config" "$option" "$value" <<'PY'
import pathlib
import re
import sys

path = pathlib.Path(sys.argv[1])
option, value = sys.argv[2:]
lines = path.read_text(encoding="utf-8").splitlines()
pattern = re.compile(r"^\s*" + re.escape(option) + r"\s+", re.IGNORECASE)
lines = [line for line in lines if not pattern.match(line) or line.lstrip().startswith("#")]
path.write_text(option + " " + value + "\n" + "\n".join(lines) + "\n", encoding="utf-8")
PY
    sshd="$(cp_sim_sshd_binary)"
    if [[ -n "$sshd" ]] && ! cp_sim_root "$sshd" -t -f "$config"; then
        cp_sim_root cp -p "$backup" "$config"
        rm -f "$backup"
        printf 'sshd: rejected the updated configuration; original file restored\n' >&2
        return 1
    fi
    rm -f "$backup"
}

cp_sim_sshd_value() {
    local option="$1"
    local config="/etc/ssh/sshd_config"
    local sshd output value
    sshd="$(cp_sim_sshd_binary)"
    if [[ -z "$sshd" || ! -f "$config" ]]; then
        printf 'no\n'
        return 0
    fi
    output="$(cp_sim_root "$sshd" -T -f "$config" 2>/dev/null)" || return 2
    value="$(printf '%s\n' "$output" | awk -v key="$option" '$1 == key { print $2; found=1; exit } END { if (!found) exit 2 }')" || return 2
    printf '%s\n' "$value"
}

cp_sim_set_pam_unix_option() {
    local config="$1"
    local option="$2"
    local value="$3"
    [[ -r "$config" ]] || {
        printf 'PAM configuration not found: %s\n' "$config" >&2
        return 1
    }
    cp_sim_root python3 - "$config" "$option" "$value" <<'PY'
import pathlib
import re
import sys

path = pathlib.Path(sys.argv[1])
option, value = sys.argv[2:]
lines = path.read_text(encoding="utf-8").splitlines()
updated = []
found = False
for line in lines:
    if line.lstrip().startswith("#") or "pam_unix.so" not in line:
        updated.append(line)
        continue
    found = True
    if option == "minlen":
        line = re.sub(r"(?<!\S)minlen=\S+", "", line)
        line = line.rstrip() + f" minlen={value}"
    elif option == "nullok":
        line = re.sub(r"(?<!\S)nullok(?!\S)", "", line)
        if value == "yes":
            line = line.rstrip() + " nullok"
    updated.append(line.rstrip())
if not found:
    raise SystemExit(f"No active pam_unix.so entry was found in {path}")
path.write_text("\n".join(updated) + "\n", encoding="utf-8")
PY
}

cp_sim_set_pwhistory() {
    local enabled="$1"
    local config="/etc/pam.d/common-password"
    [[ -r "$config" ]] || {
        printf 'PAM configuration not found: %s\n' "$config" >&2
        return 1
    }
    cp_sim_root python3 - "$config" "$enabled" <<'PY'
import pathlib
import re
import sys

path = pathlib.Path(sys.argv[1])
enabled = sys.argv[2] == "yes"
lines = path.read_text(encoding="utf-8").splitlines()
updated = [
    line for line in lines
    if line.lstrip().startswith("#") or "pam_pwhistory.so" not in line
]
if enabled:
    for index, line in enumerate(updated):
        if not line.lstrip().startswith("#") and re.search(r"\bpassword\b.*\bpam_unix\.so\b", line):
            updated.insert(index, "password required pam_pwhistory.so remember=3 use_authtok")
            break
    else:
        raise SystemExit(f"No active password pam_unix.so entry was found in {path}")
path.write_text("\n".join(updated) + "\n", encoding="utf-8")
PY
}

cp_sim_set_login_def() {
    local key="$1"
    local value="$2"
    local config="/etc/login.defs"
    [[ -r "$config" ]] || {
        printf 'Configuration file not found: %s\n' "$config" >&2
        return 1
    }
    cp_sim_root python3 - "$config" "$key" "$value" <<'PY'
import pathlib
import re
import sys

path = pathlib.Path(sys.argv[1])
key, value = sys.argv[2:]
lines = path.read_text(encoding="utf-8").splitlines()
pattern = re.compile(r"^\s*#?\s*" + re.escape(key) + r"\b")
result = []
written = False
for line in lines:
    if pattern.match(line):
        if not written:
            result.append(f"{key} {value}")
            written = True
    else:
        result.append(line)
if not written:
    result.append(f"{key} {value}")
path.write_text("\n".join(result) + "\n", encoding="utf-8")
PY
}

cp_sim_set_lightdm_guest() {
    local value="$1"
    local config="/etc/lightdm/lightdm.conf.d/99-cp-sim-guest.conf"
    cp_sim_write_root_file "$config" 644 <<EOF
[Seat:*]
allow-guest=$value
EOF
}

cp_sim_set_sysctl() {
    local key="$1"
    local value="$2"
    local slug="$3"
    local config="/etc/sysctl.d/99-z-cp-sim-"$slug".conf"

    cp_sim_root python3 - /etc/sysctl.conf "$key" "$value" <<'PY'
import pathlib
import re
import sys

path = pathlib.Path(sys.argv[1])
key, value = sys.argv[2:]
try:
    lines = path.read_text(encoding="utf-8").splitlines()
except FileNotFoundError:
    lines = []
pattern = re.compile(r"^\s*#?\s*" + re.escape(key) + r"\s*=")
result = [line for line in lines if not pattern.match(line)]
result.append(f"{key} = {value}")
path.write_text("\n".join(result) + "\n", encoding="utf-8")
PY

    cp_sim_write_root_file "$config" 644 <<EOF
$key = $value
EOF
    cp_sim_root sysctl -p "$config"
}
