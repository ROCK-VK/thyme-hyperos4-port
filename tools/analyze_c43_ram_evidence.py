#!/usr/bin/env python3
"""
THYME-OS4 Candidate 43: RAM Evidence Analysis Script
Inspects pstore/console-ramoops-0 and pstore/pmsg-ramoops-0 from C43 first boot.
"""

from pathlib import Path
import re

LOG_DIR = Path(r"[LOCAL_PROJECT_ROOT]\reports\c43_candidate43_build_20261004\standalone\run_20261004_152655\THYME_DIAG\pstore")
CONSOLE = LOG_DIR / "console-ramoops-0"
PMSG = LOG_DIR / "pmsg-ramoops-0"

def inspect_file(path: Path):
    print(f"\n==================== Inspecting: {path.name} ({path.stat().st_size} bytes) ====================")
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        print(f"Error reading {path}: {e}")
        return

    lines = content.splitlines()
    print(f"Total lines: {len(lines)}")

    # Check for apexd
    apexd_lines = [l for l in lines if "apexd" in l.lower()]
    print(f"\n--- apexd mentions ({len(apexd_lines)}) ---")
    for l in apexd_lines[:30]:
        print(l)

    # Check for tethering
    tethering_lines = [l for l in lines if "tethering" in l.lower()]
    print(f"\n--- tethering mentions ({len(tethering_lines)}) ---")
    for l in tethering_lines[:30]:
        print(l)

    # Check for netd
    netd_lines = [l for l in lines if "netd" in l.lower()]
    print(f"\n--- netd mentions ({len(netd_lines)}) ---")
    for l in netd_lines[:30]:
        print(l)

    # Check for zygote / system_server / surfaceflinger
    core_services = ["surfaceflinger", "bootanimation", "zygote", "system_server"]
    print("\n--- Core Services Presence ---")
    for s in core_services:
        cnt = sum(1 for l in lines if s in l.lower())
        print(f"  {s}: {cnt} lines")

    # Check for init errors / panics / aborts
    fatal_lines = [l for l in lines if any(k in l.lower() for k in ["fatal", "panic", "abort", "died", "killed", "wait_for_prop"])]
    print(f"\n--- Fatal / Panic / Abort / Killed / Wait ({len(fatal_lines)}) ---")
    for l in fatal_lines[:40]:
        print(l)

    # Tail of the log
    print("\n--- Last 30 lines ---")
    for l in lines[-30:]:
        print(l)

if __name__ == "__main__":
    if CONSOLE.exists():
        inspect_file(CONSOLE)
    if PMSG.exists():
        inspect_file(PMSG)
