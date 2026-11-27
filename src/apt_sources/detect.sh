#!/usr/bin/env bash
set -euo pipefail
command -v lsb_release >/dev/null || { printf 'apt_sources: lsb_release is required\n' >&2; exit 2; }
release_info="$(lsb_release -a 2>/dev/null)" || { printf 'apt_sources: lsb_release -a failed\n' >&2; exit 2; }
id="$(awk -F: '/^Distributor ID:/ {gsub(/^[[:space:]]+/, "", $2); print tolower($2)}' <<< "$release_info")"
codename="$(awk -F: '/^Codename:/ {gsub(/^[[:space:]]+/, "", $2); print $2}' <<< "$release_info")"
[[ -n "$id" && -n "$codename" ]] || exit 2
case "$id" in
  ubuntu) expected="archive.ubuntu.com/ubuntu" ;;
  debian) expected="deb.debian.org/debian" ;;
  linuxmint) expected="packages.linuxmint.com" ;;
  *) printf 'apt_sources: unsupported distribution: %s\n' "$id" >&2; exit 2 ;;
esac
file=/etc/apt/sources.list.d/00-cp-sim-official.list
[[ -r "$file" ]] || exit 1
grep -Fq "$expected" "$file" || exit 1
case "$id" in
  linuxmint) grep -Fq "packages.linuxmint.com $codename " "$file" || exit 1 ;;
  *) grep -Eq "^[[:space:]]*deb[[:space:]]+.*[[:space:]]$codename([[:space:]]|$)" "$file" || exit 1 ;;
esac
exit 0
