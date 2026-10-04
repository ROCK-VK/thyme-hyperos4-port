#!/usr/bin/env python3
"""Export boot evidence from the Standalone Diag USB volume.

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
DEFAULT_EXPORT_BASE = ROOT / "work" / "reports" / "20260925_CANDIDATE13_LOG_SALVAGE"
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


def new_export_dir(export_base: Path) -> Path:
    export_base.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    candidate = export_base / f"run_{stamp}"
    suffix = 1
    while candidate.exists():
        candidate = export_base / f"run_{stamp}_{suffix:02d}"
        suffix += 1
    candidate.mkdir(parents=False, exist_ok=False)
    return candidate


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--candidate",
        default="C13-original",
        help="Label the boot whose evidence is being salvaged (default: C13-original).",
    )
    parser.add_argument(
        "--output-base",
        type=Path,
        default=DEFAULT_EXPORT_BASE,
        help="Parent directory for a new, non-overwriting export folder.",
    )
    parser.add_argument(
        "--diag-boot",
        type=Path,
        default=DIAG_BOOT,
        help="Standalone RAM image to boot. A non-default image requires explicit expected size and SHA-256.",
    )
    parser.add_argument(
        "--expected-bytes",
        type=int,
        help="Required with --expected-sha256 when using a non-default --diag-boot.",
    )
    parser.add_argument(
        "--expected-sha256",
        help="Required with --expected-bytes when using a non-default --diag-boot.",
    )
    parser.add_argument(
        "--execute-authorized-ram-boot",
        action="store_true",
        help="Permit fastboot boot only after the user has separately authorized this Standalone RAM session.",
    )
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9._-]+", args.candidate):
        print("[ERROR] Candidate label may contain only letters, digits, dot, underscore, and hyphen.")
        return 1
    print(f"=== {args.candidate} STANDALONE DIAGNOSTIC EXPORT ===")
    if not FASTBOOT.is_file():
        print(f"[ERROR] Fastboot executable missing: {FASTBOOT}")
        return 1
    diag_boot = args.diag_boot.resolve()
    using_default_image = diag_boot == DIAG_BOOT.resolve()
    if using_default_image:
        expected_bytes = DIAG_BOOT_BYTES
        expected_sha256 = DIAG_BOOT_SHA256
    else:
        if args.expected_bytes is None or not args.expected_sha256:
            print("[ERROR] A non-default --diag-boot requires both --expected-bytes and --expected-sha256.")
            return 1
        expected_bytes = args.expected_bytes
        expected_sha256 = args.expected_sha256.upper()
    if not diag_boot.is_file() or diag_boot.stat().st_size != expected_bytes:
        print(f"[ERROR] Standalone Diag image missing or wrong size: {diag_boot}; expected {expected_bytes} bytes")
        return 1
    actual_hash = sha256_file(diag_boot)
    if actual_hash != expected_sha256:
        print(f"[ERROR] Standalone Diag SHA256 mismatch: {actual_hash}")
        return 1

    print(f"[READY] Standalone Diag image verified: {diag_boot} ({expected_bytes} bytes; SHA256={actual_hash})")
    if not args.execute_authorized_ram_boot:
        print("[DRY-RUN] No Fastboot query or device command issued.")
        print("[NEXT] Pass --execute-authorized-ram-boot only when this RAM diagnostic boot is authorized.")
        return 0

    export_dir = new_export_dir(args.output_base)
    event_path = export_dir / "host_salvage_timeline.csv"
    timeline(event_path, "salvage_script_started", {
        "image_path": str(diag_boot), "image_sha256": actual_hash, "image_bytes": expected_bytes,
    })
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
    timeline(event_path, "fastboot_boot_started", {
        "command": "fastboot boot <verified Standalone image>", "image_path": str(diag_boot),
        "image_sha256": actual_hash,
    })
    boot = run([str(FASTBOOT), "-s", SERIAL, "boot", str(diag_boot)], timeout=120)
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

    # The RAM image may not expose a separate dmesg file. Its own dmesg, when
    # captured, is explicitly named dmesg_standalone.txt and must not be
    # mistaken for the preceding Android boot log.
    required_files = ("diag_status.log",)
    missing_files = [name for name in required_files if not (volume / name).is_file()]
    if missing_files:
        print(
            "[WARN] THYME_DIAG volume matched, but expected Standalone files are "
            f"missing; remaining accessible files will still be copied: {missing_files}"
        )

    print(f"[EXPORT] Copying from dynamically detected volume {volume} to {export_dir}")
    timeline(event_path, "diag_volume_found", {"volume": str(volume)})
    (export_dir / "EXPORT_SOURCE.txt").write_text(
        "Source: the unique host volume labeled THYME_DIAG, exposed by the Standalone RAM diagnostic environment.\n"
        f"dmesg_diag_boot.txt is the Standalone diagnostic kernel log, not the preceding {args.candidate} kernel log.\n"
        f"Salvaged boot label: {args.candidate}.\n"
        f"Export started (UTC): {utc_now()}\n",
        encoding="utf-8",
    )
    timeline(event_path, "copy_started", {"volume": str(volume)})
    copied: list[tuple[str, int, str]] = []
    copy_errors: list[str] = [f"missing required top-level file: {name}" for name in missing_files]
    volume_export = export_dir / "THYME_DIAG"
    volume_export.mkdir()

    def record_walk_error(error: OSError) -> None:
        message = f"directory {error.filename!r}: {error}"
        copy_errors.append(message)
        print(f"  [COPY-ERROR] {message}")

    for source_root, dirs, files in os.walk(volume, onerror=record_walk_error):
        dirs.sort()
        files.sort()
        relative_dir = Path(source_root).relative_to(volume)
        for dirname in dirs:
            (volume_export / relative_dir / dirname).mkdir(parents=True, exist_ok=True)
        for filename in files:
            source = Path(source_root) / filename
            relative = source.relative_to(volume)
            destination = volume_export / relative
            try:
                destination.parent.mkdir(parents=True, exist_ok=True)
                source_size_before = source.stat().st_size
                shutil.copy2(source, destination)
                source_size_after = source.stat().st_size
                destination_size = destination.stat().st_size
                source_digest = sha256_file(source)
                destination_digest = sha256_file(destination)
                if source_size_before != source_size_after:
                    raise OSError("source size changed while it was being copied")
                if source_size_after != destination_size:
                    raise OSError(
                        f"size mismatch: source={source_size_after}, copy={destination_size}"
                    )
                if source_digest != destination_digest:
                    raise OSError(
                        f"SHA-256 mismatch: source={source_digest}, copy={destination_digest}"
                    )
            except OSError as exc:
                message = f"file {relative.as_posix()!r}: {exc}"
                copy_errors.append(message)
                print(f"  [COPY-ERROR] {message}")
                continue
            copied.append((relative.as_posix(), destination_size, destination_digest))
            print(
                f"  [SAVED] {relative.as_posix()} ({destination_size:,} bytes) "
                f"SHA256={destination_digest} (source verified)"
            )

    manifest = export_dir / "SHA256SUMS.txt"
    with manifest.open("w", encoding="utf-8", newline="\n") as stream:
        for relative, _size, digest in copied:
            stream.write(f"{digest}  THYME_DIAG/{relative}\n")

    file_manifest = export_dir / "FILE_MANIFEST.csv"
    with file_manifest.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(("relative_path", "bytes", "sha256"))
        for relative, size, digest in copied:
            writer.writerow((f"THYME_DIAG/{relative}", size, digest))

    if copy_errors:
        (export_dir / "COPY_ERRORS.txt").write_text(
            "Some source content could not be traversed or verified:\n"
            + "\n".join(copy_errors)
            + "\n",
            encoding="utf-8",
        )

    timeline(event_path, "copy_finished", {
        "file_count": len(copied),
        "copy_error_count": len(copy_errors),
        "files": [item[0] for item in copied],
        "copy_errors": copy_errors,
    })
    print(
        f"[DONE] Exported and source-verified {len(copied)} files to {volume_export}; "
        f"copy errors={len(copy_errors)}"
    )
    print(f"[NEXT] Review the new {args.candidate} console/pmsg logs before any recovery action.")
    return 6 if copy_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
