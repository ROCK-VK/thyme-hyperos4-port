#!/usr/bin/env python3
"""
THYME-OS4 Candidate 46: RAM Log Salvage Script
Waits for the device in Fastboot after the C46 first boot observation,
loads Standalone Diag into RAM, and exports DDR RAM pmsg-ramoops-0 and console-ramoops-0.
"""

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SALVAGE_PY = ROOT / "tools" / "salvage_c13_diag.py"
OUTPUT_BASE = ROOT / "reports" / "c46_candidate46_build_20261004" / "standalone"
FASTBOOT = ROOT / "tools" / "platform-tools" / "fastboot.exe"
SERIAL = "[REDACTED_DEVICE_ID]"

def check_fastboot():
    res = subprocess.run([str(FASTBOOT), "devices", "-l"], capture_output=True, text=True)
    for line in res.stdout.splitlines():
        if line.strip().startswith(SERIAL):
            return True
    return False

def main():
    print("=== C46 RAM SALVAGE PIPELINE ===")
    print(f"Checking for device {SERIAL} in Fastboot...")
    if not check_fastboot():
        print(f"[ERROR] Device {SERIAL} not in Fastboot. (Hold Vol Down + Power to enter Fastboot)")
        return 1

    print("[SALVAGE] Starting Standalone RAM dump...")
    OUTPUT_BASE.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        str(SALVAGE_PY),
        "--candidate", "C46",
        "--output-base", str(OUTPUT_BASE),
        "--execute-authorized-ram-boot"
    ]
    res = subprocess.run(cmd, text=True)
    print(f"Salvage exit code: {res.returncode}")
    return res.returncode

if __name__ == "__main__":
    sys.exit(main())
