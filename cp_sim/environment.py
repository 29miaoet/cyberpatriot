"""Virtual-machine safety checks and operating-system metadata."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from .config import CpSimError


def is_virtual_machine() -> tuple[bool, str]:
    """Detect a VM heuristically; this is a safety gate, not proof."""
    detector = shutil.which("systemd-detect-virt")
    if detector:
        try:
            result = subprocess.run(
                [detector, "--vm"], check=False, capture_output=True,
                text=True, timeout=5,
            )
            detected = result.stdout.strip()
            if result.returncode == 0 and detected and detected != "none":
                return True, f"systemd-detect-virt: {detected}"
        except (OSError, subprocess.TimeoutExpired):
            pass
    dmi_files = (
        Path("/sys/class/dmi/id/sys_vendor"),
        Path("/sys/class/dmi/id/product_name"),
        Path("/sys/class/dmi/id/board_vendor"),
    )
    known_vm_terms = (
        "kvm", "qemu", "vmware", "virtualbox", "innotek",
        "microsoft corporation", "virtual machine", "xen",
        "parallels", "bhyve", "amazon ec2", "google",
    )
    for path in dmi_files:
        try:
            value = path.read_text(encoding="utf-8", errors="replace").strip().lower()
        except OSError:
            continue
        if any(term in value for term in known_vm_terms):
            return True, f"virtualization marker in {path}"
    try:
        cpu_info = Path("/proc/cpuinfo").read_text(
            encoding="utf-8", errors="replace"
        ).lower()
        if re.search(r"^flags\s*:.*\bhypervisor\b", cpu_info, re.MULTILINE):
            return True, "hypervisor CPU flag"
    except OSError:
        pass
    return False, "no recognized virtual-machine marker was found"


def require_vm() -> None:
    if not sys.platform.startswith("linux"):
        raise CpSimError("cp-sim only supports Linux virtual machines.")
    virtual, reason = is_virtual_machine()
    if not virtual:
        raise CpSimError(
            "VM safety check failed; refusing to continue. "
            "Run cp-sim inside a supported Linux VM. "
            f"Detection result: {reason}"
        )


def read_os_details() -> dict[str, str]:
    """Read distribution details supplied by the launcher or /etc/os-release."""
    values = {
        "ID": os.environ.get("CP_SIM_OS_ID", ""),
        "PRETTY_NAME": os.environ.get("CP_SIM_OS_PRETTY_NAME", ""),
        "VERSION_ID": os.environ.get("CP_SIM_OS_VERSION", ""),
    }
    if not all(values.values()):
        try:
            for line in Path("/etc/os-release").read_text(
                encoding="utf-8", errors="replace"
            ).splitlines():
                key, separator, value = line.partition("=")
                if separator and key in values and not values[key]:
                    values[key] = value.strip().strip('"').strip("'")
        except OSError:
            pass
    return {
        "id": values["ID"] or "linux",
        "pretty_name": values["PRETTY_NAME"] or "Linux",
        "version": values["VERSION_ID"],
    }
