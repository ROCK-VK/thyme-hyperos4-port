#!/usr/bin/env python3
"""Export Candidate 13 boot evidence from the Standalone Diag USB volume.

This script boots the diagnostic image into RAM with ``fastboot boot`` and
copies diagnostic files. It does not flash partitions or restore a ROM, and
it issues no explicit ``fastboot reboot`` command.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FASTBOOT = ROOT / "tools" / "platform-tools" / "fastboot.exe"
SERIAL = "[REDACTED_DEVICE_ID]"
DIAG_BOOT = ROOT / "work" / "standalone_diag" / "standalone_diag_boot.img"
DIAG_BOOT_BYTES = 201_326_592
DIAG_BOOT_SHA256 = "8A5803F09CBCB11056D8356F8D235C3C4450846244FA1B4033ABAAACB213E98B"
EXPORT_BASE = ROOT / "work" / "reports" / "20260925_CANDIDATE13_LOG_SALVAGE"


def run(command: list[str], timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def fastboot_has_target() -> bool:
    result = run([str(FASTBOOT), "devices", "-l"])
    if result.returncode != 0:
        return False
    return any(line.split()[:2] == [SERIAL, "fastboot"] for line in result.stdout.splitlines())


def find_diag_volume() -> Path | None:
    query = (
        "$v = Get-Volume -FileSystemLabel 'THYME_DIAG' -ErrorAction SilentlyContinue | "
        "Where-Object DriveLetter | Select-Object -First 1 -ExpandProperty DriveLetter; "
        "if ($v) { Write-Output ($v + ':\\') }"
    )
    result = run(["powershell.exe", "-NoProfile", "-Command", query], timeout=10)
    if result.returncode != 0:
        return None
    drive = result.stdout.strip()
    if len(drive) >= 3 and drive[1:3] == ":\\":
        return Path(drive)
    return None


def new_export_dir() -> Path:
    EXPORT_BASE.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    candidate = EXPORT_BASE / f"run_{stamp}"
    suffix = 1
    while candidate.exists():
        candidate = EXPORT_BASE / f"run_{stamp}_{suffix:02d}"
        suffix += 1
    candidate.mkdir(parents=False, exist_ok=False)
    return candidate


def main() -> int:
    print("=== CANDIDATE 13 STANDALONE DIAGNOSTIC EXPORT ===")
    if not FASTBOOT.is_file():
        print(f"[ERROR] Fastboot executable missing: {FASTBOOT}")
        return 1
    if not DIAG_BOOT.is_file() or DIAG_BOOT.stat().st_size != DIAG_BOOT_BYTES:
        print(f"[ERROR] Standalone Diag image missing or wrong size: {DIAG_BOOT}")
        return 1
    actual_hash = sha256_file(DIAG_BOOT)
    if actual_hash != DIAG_BOOT_SHA256:
        print(f"[ERROR] Standalone Diag SHA256 mismatch: {actual_hash}")
        return 1

    print(f"[READY] Standalone Diag SHA256 verified: {actual_hash}")
    print(f"[WAIT] Waiting up to 300 seconds for Fastboot target {SERIAL}...")
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline and not fastboot_has_target():
        time.sleep(1)
    if not fastboot_has_target():
        print("[ERROR] Target device did not appear in Fastboot.")
        return 2

    print("[BOOT] Loading Standalone Diag into RAM with fastboot boot; no partition is written.")
    boot = run([str(FASTBOOT), "-s", SERIAL, "boot", str(DIAG_BOOT)], timeout=120)
    print(boot.stdout, end="")
    print(boot.stderr, end="", file=sys.stderr)
    if boot.returncode != 0:
        print(f"[ERROR] fastboot boot failed with exit code {boot.returncode}.")
        return 3

    print("[WAIT] Waiting up to 180 seconds for a volume labeled THYME_DIAG...")
    deadline = time.monotonic() + 180
    volume: Path | None = None
    while time.monotonic() < deadline:
        volume = find_diag_volume()
        if volume is not None:
            break
        time.sleep(2)
    if volume is None:
        print("[ERROR] THYME_DIAG volume was not found; no drive letter was assumed.")
        return 4

    export_dir = new_export_dir()
    print(f"[EXPORT] Copying from dynamically detected volume {volume} to {export_dir}")
    copied: list[tuple[str, int, str]] = []
    for source_root, dirs, files in os.walk(volume):
        dirs[:] = [name for name in dirs if name not in {"System Volume Information", "$RECYCLE.BIN"}]
        for filename in files:
            source = Path(source_root) / filename
            relative = source.relative_to(volume)
            destination = export_dir / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            size = destination.stat().st_size
            digest = sha256_file(destination)
            copied.append((relative.as_posix(), size, digest))
            print(f"  [SAVED] {relative.as_posix()} ({size:,} bytes) SHA256={digest}")

    manifest = export_dir / "SHA256SUMS.txt"
    with manifest.open("w", encoding="utf-8", newline="\n") as stream:
        for relative, _size, digest in copied:
            stream.write(f"{digest}  {relative}\n")

    print(f"[DONE] Exported {len(copied)} files to {export_dir}")
    print("[NEXT] Review the new Candidate 13 console/pmsg logs before restoring PixelOS A0'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
