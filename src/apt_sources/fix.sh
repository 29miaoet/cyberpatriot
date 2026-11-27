#!/usr/bin/env bash
set -euo pipefail
source ../common.sh
command -v lsb_release >/dev/null || { printf 'apt_sources: install lsb-release first\n' >&2; exit 2; }
command -v apt-get >/dev/null || exit 2

release_info="$(lsb_release -a 2>/dev/null)" || { printf 'apt_sources: lsb_release -a failed\n' >&2; exit 2; }
distro="$(awk -F: '/^Distributor ID:/ {gsub(/^[[:space:]]+/, "", $2); print tolower($2)}' <<< "$release_info")"
codename="$(awk -F: '/^Codename:/ {gsub(/^[[:space:]]+/, "", $2); print $2}' <<< "$release_info")"
[[ -n "$distro" && -n "$codename" ]] || { printf 'apt_sources: cannot determine distribution/codename\n' >&2; exit 2; }
[[ "$codename" =~ ^[a-zA-Z0-9.-]+$ ]] || { printf 'apt_sources: invalid release codename\n' >&2; exit 2; }

case "$distro" in
  ubuntu)
    components="main restricted universe multiverse"
    lines="deb http://archive.ubuntu.com/ubuntu $codename $components
deb http://archive.ubuntu.com/ubuntu $codename-updates $components
deb http://security.ubuntu.com/ubuntu $codename-security $components"
    ;;
  debian)
    components="main contrib non-free non-free-firmware"
    lines="deb http://deb.debian.org/debian $codename $components
deb http://deb.debian.org/debian $codename-updates $components
deb http://security.debian.org/debian-security $codename-security $components"
    ;;
  linuxmint)
    ubuntu_codename="$(. /etc/os-release; printf '%s' "${UBUNTU_CODENAME:-}")"
    [[ -n "$ubuntu_codename" && "$ubuntu_codename" =~ ^[a-zA-Z0-9.-]+$ ]] || {
      printf 'apt_sources: Linux Mint base Ubuntu codename is unavailable in /etc/os-release\n' >&2
      exit 2
    }
    components="main restricted universe multiverse"
    lines="deb http://packages.linuxmint.com $codename main upstream import backport
deb http://archive.ubuntu.com/ubuntu $ubuntu_codename $components
deb http://archive.ubuntu.com/ubuntu $ubuntu_codename-updates $components
deb http://security.ubuntu.com/ubuntu $ubuntu_codename-security $components"
    ;;
  *)
    printf 'apt_sources: unsupported distribution ID: %s\n' "$distro" >&2
    exit 2
    ;;
esac

target=/etc/apt/sources.list.d/00-cp-sim-official.list
printf 'The following official repository entries will be written to %s:\n\n%s\n\n' "$target" "$lines"
printf 'Existing source files and third-party repositories will be left untouched.\n'
cp_sim_confirm "Add/update the cp-sim managed official APT source list for $distro ($codename)." || exit 0

backup="$(mktemp)"
had_previous=0
if [[ -f "$target" ]]; then
  cp_sim_root cp -p "$target" "$backup"
  had_previous=1
fi
if ! printf '%s\n' "$lines" | cp_sim_write_root_file "$target" 644; then
  rm -f "$backup"
  exit 1
fi
if ! cp_sim_root apt-get update; then
  printf 'apt_sources: apt-get update failed; restoring previous managed source file\n' >&2
  if [[ "$had_previous" -eq 1 ]]; then
    cp_sim_root cp -p "$backup" "$target"
  else
    cp_sim_root rm -f "$target"
  fi
  rm -f "$backup"
  exit 1
fi
rm -f "$backup"
printf 'apt_sources: official repository entries updated; existing third-party sources were preserved\n'
