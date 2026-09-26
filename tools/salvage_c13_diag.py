#!/usr/bin/env python3
"""Export Candidate 13 boot evidence from the Standalone Diag USB volume.

The default is a host-only dry run. ``--execute-authorized-ram-boot`` is
required before this script may issue ``fastboot boot``. That command loads
Standalone into RAM; it does not flash partitions or restore a ROM. The script
does not issue ``fastboot reboot`` or write to the captured misc/oops devices.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FASTBOOT = ROOT / "tools" / "platform-tools" / "fastboot.exe"
SERIAL = "[REDACTED_DEVICE_ID]"
DIAG_BOOT = ROOT / "work" / "standalone_diag" / "standalone_diag_boot.img"
DIAG_BOOT_BYTES = 201_326_592
DIAG_BOOT_SHA256 = "8A5803F09CBCB11056D8356F8D235C3C4450846244FA1B4033ABAAACB213E98B"
EXPORT_BASE = ROOT / "work" / "reports" / "20260925_CANDIDATE13_LOG_SALVAGE"
EXPECTED_PRODUCT = "thyme"
EXPECTED_SLOT = "a"


def run(command: list[str], timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def timeline(path: Path, event: str, details: dict[str, object] | None = None) -> None:
    is_new = not path.exists()
    with path.open("a", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        if is_new:
            writer.writerow(("host_utc", "event", "details_json"))
        writer.writerow((utc_now(), event, json.dumps(details or {}, ensure_ascii=False, sort_keys=True)))
        stream.flush()
        os.fsync(stream.fileno())


def fastboot_var(name: str) -> str:
    result = run([str(FASTBOOT), "-s", SERIAL, "getvar", name], timeout=10)
    output = result.stdout + "\n" + result.stderr
    if result.returncode != 0:
        raise RuntimeError(f"fastboot getvar {name} failed ({result.returncode}): {output.strip()}")
    match = re.search(rf"(?m)^\s*(?:\(bootloader\)\s*)?{re.escape(name)}:\s*(.*?)\s*$", output)
    if not match:
        raise RuntimeError(f"Fastboot did not report {name}: {output.strip()}")
    return match.group(1).strip()


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
        "$volumes = @(Get-Volume -FileSystemLabel 'THYME_DIAG' -ErrorAction SilentlyContinue | "
        "Where-Object DriveLetter); "
        "if ($volumes.Count -eq 1) { Write-Output ($volumes[0].DriveLetter + ':\\') }"
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute-authorized-ram-boot",
        action="store_true",
        help="Permit fastboot boot only after the user has separately authorized this Standalone RAM session.",
    )
    args = parser.parse_args()
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
    if not args.execute_authorized_ram_boot:
        print("[DRY-RUN] No Fastboot query or device command issued.")
        print("[NEXT] After separate Standalone RAM-start authorization, pass --execute-authorized-ram-boot.")
        return 0

    export_dir = new_export_dir()
    event_path = export_dir / "host_salvage_timeline.csv"
    timeline(event_path, "salvage_script_started", {"image_sha256": actual_hash, "image_bytes": DIAG_BOOT_BYTES})
    print(f"[WAIT] Waiting up to 300 seconds for Fastboot target {SERIAL}...")
    timeline(event_path, "fastboot_wait_started", {"serial": SERIAL})
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline and not fastboot_has_target():
        time.sleep(1)
    if not fastboot_has_target():
        print("[ERROR] Target device did not appear in Fastboot.")
        timeline(event_path, "fastboot_target_timeout", {"serial": SERIAL})
        return 2

    try:
        product = fastboot_var("product")
        slot = fastboot_var("current-slot")
        unlocked = fastboot_var("unlocked")
        is_userspace = fastboot_var("is-userspace")
    except RuntimeError as exc:
        timeline(event_path, "fastboot_preflight_failed", {"error": str(exc)})
        print(f"[ERROR] {exc}")
        return 2
    if (product, slot, unlocked, is_userspace) != (EXPECTED_PRODUCT, EXPECTED_SLOT, "yes", "no"):
        details = {
            "serial": SERIAL, "product": product, "current_slot": slot,
            "unlocked": unlocked, "is_userspace": is_userspace,
        }
        timeline(event_path, "fastboot_preflight_failed", details)
        print(f"[ERROR] Unexpected Fastboot identity/state; stopped without RAM boot: {details}")
        return 2
    timeline(event_path, "fastboot_preflight_passed", {
        "serial": SERIAL, "product": product, "current_slot": slot,
        "unlocked": unlocked, "is_userspace": is_userspace,
    })

    print("[BOOT] Loading Standalone Diag into RAM with fastboot boot; no partition is written.")
    timeline(event_path, "fastboot_boot_started", {"command": "fastboot boot standalone_diag_boot.img"})
    boot = run([str(FASTBOOT), "-s", SERIAL, "boot", str(DIAG_BOOT)], timeout=120)
    print(boot.stdout, end="")
    print(boot.stderr, end="", file=sys.stderr)
    if boot.returncode != 0:
        print(f"[ERROR] fastboot boot failed with exit code {boot.returncode}.")
        timeline(event_path, "fastboot_boot_failed", {"exit_code": boot.returncode, "stdout": boot.stdout, "stderr": boot.stderr})
        return 3
    timeline(event_path, "fastboot_boot_finished", {"exit_code": 0, "stdout": boot.stdout, "stderr": boot.stderr})

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
        timeline(event_path, "diag_volume_timeout", {})
        return 4

    required_files = ("diag_status.log", "dmesg_diag_boot.txt")
    missing_files = [name for name in required_files if not (volume / name).is_file()]
    if missing_files:
        print(f"[ERROR] THYME_DIAG label matched, but required Standalone evidence files are missing: {missing_files}")
        timeline(event_path, "diag_volume_invalid", {"volume": str(volume), "missing_files": missing_files})
        return 5

    print(f"[EXPORT] Copying from dynamically detected volume {volume} to {export_dir}")
    timeline(event_path, "diag_volume_found", {"volume": str(volume)})
    (export_dir / "EXPORT_SOURCE.txt").write_text(
        "Source: the unique host volume labeled THYME_DIAG, exposed by the Standalone RAM diagnostic environment.\n"
        "dmesg_diag_boot.txt is the Standalone diagnostic kernel log, not the preceding Candidate 13 kernel log.\n"
        f"Export started (UTC): {utc_now()}\n",
        encoding="utf-8",
    )
    timeline(event_path, "copy_started", {"volume": str(volume)})
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

    timeline(event_path, "copy_finished", {"file_count": len(copied), "files": [item[0] for item in copied]})
    print(f"[DONE] Exported {len(copied)} files to {export_dir}")
    print("[NEXT] Review the new Candidate 13 console/pmsg logs before restoring PixelOS A0'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
