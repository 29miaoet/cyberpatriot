#!/usr/bin/env bash
set -euo pipefail
command -v lsb_release >/dev/null || { printf 'apt_sources: lsb_release is required\n' >&2; exit 2; }
release_info="$(lsb_release -a 2>/dev/null)" || { printf 'apt_sources: lsb_release -a failed\n' >&2; exit 2; }
distro="$(awk -F: '/^Distributor ID:/ {gsub(/^[[:space:]]+/, "", $2); print tolower($2)}' <<< "$release_info")"
codename="$(awk -F: '/^Codename:/ {gsub(/^[[:space:]]+/, "", $2); print $2}' <<< "$release_info")"
[[ -n "$distro" && -n "$codename" ]] || exit 2
case "$distro" in
  ubuntu|debian) base_codename="$codename" ;;
  linuxmint)
    base_codename="$(. /etc/os-release; printf '%s' "${UBUNTU_CODENAME:-}")"
    [[ -n "$base_codename" ]] || exit 2
    ;;
  *) printf 'apt_sources: unsupported distribution: %s\n' "$distro" >&2; exit 2 ;;
esac
python3 - "$distro" "$codename" "$base_codename" <<'PY'
from pathlib import Path
import sys

distro, codename, base_codename = sys.argv[1:]
sources = []
root = Path("/etc/apt")
paths = [root / "sources.list"]
directory = root / "sources.list.d"
if directory.is_dir():
    paths.extend(sorted(directory.glob("*.list")))
    paths.extend(sorted(directory.glob("*.sources")))

def add(uri, suites):
    for suite in suites:
        sources.append((uri.lower().rstrip("/"), suite))

for path in paths:
    if not path.is_file():
        continue
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        continue
    if path.suffix == ".sources":
        for paragraph in content.split("\n\n"):
            fields = {}
            for line in paragraph.splitlines():
                if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
                    continue
                key, value = line.split(":", 1)
                fields[key.strip().lower()] = value.strip()
            if "deb" in fields.get("types", "").split():
                for uri in fields.get("uris", "").split():
                    add(uri, fields.get("suites", "").split())
    else:
        for line in content.splitlines():
            stripped = line.strip()
            if not stripped.startswith("deb "):
                continue
            tokens = stripped.split()
            uri_index = next((i for i, token in enumerate(tokens) if token.startswith(("http://", "https://"))), None)
            if uri_index is not None and uri_index + 1 < len(tokens):
                add(tokens[uri_index], [tokens[uri_index + 1]])

def has(uri_fragment, suite):
    return any(uri_fragment in source_uri and source_suite == suite
               for source_uri, source_suite in sources)

if distro == "ubuntu":
    valid = (
        has("archive.ubuntu.com/ubuntu", codename)
        and has("archive.ubuntu.com/ubuntu", codename + "-updates")
        and has("security.ubuntu.com/ubuntu", codename + "-security")
    )
elif distro == "debian":
    valid = (
        has("deb.debian.org/debian", codename)
        and has("deb.debian.org/debian", codename + "-updates")
        and has("security.debian.org", codename + "-security")
    )
else:
    valid = (
        has("packages.linuxmint.com", codename)
        and has("archive.ubuntu.com/ubuntu", base_codename)
        and has("archive.ubuntu.com/ubuntu", base_codename + "-updates")
        and has("security.ubuntu.com/ubuntu", base_codename + "-security")
    )
raise SystemExit(0 if valid else 1)
PY
