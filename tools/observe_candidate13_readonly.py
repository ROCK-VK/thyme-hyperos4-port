#!/usr/bin/env python3
"""Read-only host observer for a separately authorized Android boot.

This tool never reboots, boots, flashes, erases, or writes to the device. It
polls ADB/Fastboot discovery, streams ADB logcat while ADB is online, and saves
read-only startup snapshots, and tries to copy readable pstore files as soon as
ADB becomes available. Start it before the separately authorized startup
command and stop it with Ctrl-C after the observation window.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADB = ROOT / "tools" / "platform-tools" / "adb.exe"
FASTBOOT = ROOT / "tools" / "platform-tools" / "fastboot.exe"
SERIAL = "[REDACTED_DEVICE_ID]"
DEFAULT_BASE = ROOT / "work" / "reports" / "20260925_CANDIDATE13_STORAGE_SAFETY_AND_FIRST_FAILURE" / "observations"
SNAPSHOT_PROPERTIES = (
    "ro.product.device",
    "ro.build.version.release",
    "ro.build.version.sdk",
    "ro.build.display.id",
    "ro.bootmode",
    "ro.boot.mode",
    "ro.boot.slot_suffix",
    "ro.boot.bootreason",
    "ro.boot.force_normal_boot",
    "ro.boot.init_fatal_reboot_target",
    "ro.boot.init_fatal_panic",
    "ro.boot.verifiedbootstate",
    "ro.boot.selinux",
    "sys.boot_completed",
    "init.svc.vold",
    "ro.crypto.state",
    "ro.crypto.type",
    "vold.decrypt",
)
RELEVANT_SERVICE_TOKENS = ("vold", "keymaster", "gatekeeper", "zygote", "surfaceflinger", "bootanim")
ADB_SHELL_STATES = {"device", "recovery"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def append_host_event(path: Path, event: str, **fields: object) -> None:
    record = {"host_utc": utc_now(), "event": event, **fields}
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def run_readonly(command: list[str], timeout: float = 4.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )


def run_readonly_bytes(command: list[str], timeout: float = 8.0) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        command,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def matching_state(output: str, serial: str, expected_state: str) -> str:
    for line in output.splitlines():
        fields = line.split()
        if len(fields) >= 2 and fields[0] == serial and fields[1] == expected_state:
            return expected_state
        if len(fields) >= 2 and fields[0] == serial:
            return fields[1]
    return "absent"


def create_run_dir(base: Path) -> Path:
    base.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    candidate = base / f"run_{stamp}"
    suffix = 1
    while candidate.exists():
        candidate = base / f"run_{stamp}_{suffix:02d}"
        suffix += 1
    candidate.mkdir(parents=False, exist_ok=False)
    return candidate


def snapshot(run_dir: Path, index: int, include_dmesg: bool) -> None:
    out_path = run_dir / f"adb_snapshot_{index:04d}.txt"
    with out_path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(f"host_utc={utc_now()}\nserial={SERIAL}\n")
        result = run_readonly([str(ADB), "-s", SERIAL, "shell", "getprop"], timeout=3.0)
        stream.write(f"\n--- selected getprop values (exit {result.returncode}) ---\n")
        properties: dict[str, str] = {}
        for line in result.stdout.splitlines():
            match = re.match(r"^\[([^\]]+)\]: \[(.*)\]$", line)
            if match:
                properties[match.group(1)] = match.group(2)
        for prop in SNAPSHOT_PROPERTIES:
            stream.write(f"{prop}={properties.get(prop, '<missing>')}\n")
        for prop, value in sorted(properties.items()):
            if prop.startswith("init.svc.") and any(token in prop for token in RELEVANT_SERVICE_TOKENS):
                if prop not in SNAPSHOT_PROPERTIES:
                    stream.write(f"{prop}={value}\n")
        if result.stderr:
            stream.write("\n[stderr]\n" + result.stderr)
        if index == 1:
            result = run_readonly([str(ADB), "-s", SERIAL, "shell", "cat", "/proc/cmdline"], timeout=3.0)
            stream.write(f"\n--- /proc/cmdline (exit {result.returncode}) ---\n")
            stream.write(result.stdout)
            if result.stderr:
                stream.write("\n[stderr]\n" + result.stderr)
            result = run_readonly([str(ADB), "-s", SERIAL, "shell", "cat", "/proc/version"], timeout=3.0)
            stream.write(f"\n--- /proc/version (exit {result.returncode}) ---\n")
            stream.write(result.stdout)
            if result.stderr:
                stream.write("\n[stderr]\n" + result.stderr)
        if include_dmesg:
            result = run_readonly([str(ADB), "-s", SERIAL, "shell", "dmesg"], timeout=5.0)
            stream.write(f"\n--- dmesg (exit {result.returncode}) ---\n")
            stream.write(result.stdout)
            if result.stderr:
                stream.write("\n[stderr]\n" + result.stderr)
            for label, command in (
                ("getenforce", ["getenforce"]),
                ("/dev/ion SELinux label", ["ls", "-lZ", "/dev/ion"]),
                ("/data and /metadata mounts", ["grep", "-E", " /(data|metadata) ", "/proc/mounts"]),
                ("SELinux process labels", ["ps", "-AZ"]),
            ):
                result = run_readonly([str(ADB), "-s", SERIAL, "shell", *command], timeout=3.0)
                stream.write(f"\n--- {label} (exit {result.returncode}) ---\n")
                stream.write(result.stdout)
                if result.stderr:
                    stream.write("\n[stderr]\n" + result.stderr)


def capture_pstore_from_adb(run_dir: Path, index: int) -> None:
    """Try to preserve pstore while ADB is available (including Recovery ADB).

    The remote operations are limited to directory listing and file reads. ADB
    permissions vary by boot mode; failures are recorded without escalation.
    """
    capture_dir = run_dir / "adb_pstore" / f"capture_{index:02d}"
    capture_dir.mkdir(parents=True, exist_ok=False)
    status_lines = [f"capture_started_utc={utc_now()}", f"serial={SERIAL}", "remote_path=/sys/fs/pstore"]
    listing = run_readonly([str(ADB), "-s", SERIAL, "shell", "ls", "-1", "/sys/fs/pstore"], timeout=6.0)
    status_lines.append(f"list_exit={listing.returncode}")
    if listing.stdout:
        status_lines.append("listing:")
        status_lines.extend(listing.stdout.splitlines())
    if listing.stderr:
        status_lines.append("listing_stderr:")
        status_lines.extend(listing.stderr.splitlines())

    manifest_lines: list[str] = []
    if listing.returncode == 0:
        for name in listing.stdout.splitlines():
            name = name.strip()
            if not re.fullmatch(r"[A-Za-z0-9_.-]+", name) or name in {".", ".."}:
                continue
            result = run_readonly_bytes(
                [str(ADB), "-s", SERIAL, "exec-out", "cat", f"/sys/fs/pstore/{name}"],
                timeout=12.0,
            )
            if result.returncode != 0:
                detail = result.stderr.decode("utf-8", errors="replace").strip()
                status_lines.append(f"read_failed={name} exit={result.returncode} stderr={detail}")
                continue
            destination = capture_dir / name
            destination.write_bytes(result.stdout)
            digest = hashlib.sha256(result.stdout).hexdigest()
            manifest_lines.append(f"{digest}  {len(result.stdout)}  {name}")

    status_lines.append(f"capture_finished_utc={utc_now()}")
    (capture_dir / "capture_status.txt").write_text("\n".join(status_lines) + "\n", encoding="utf-8")
    (capture_dir / "SHA256SUMS.txt").write_text("\n".join(manifest_lines) + ("\n" if manifest_lines else ""), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=int, default=600, help="Observation window (default: 600 seconds).")
    parser.add_argument("--output-base", type=Path, default=DEFAULT_BASE, help="Parent directory for a new timestamped run folder.")
    parser.add_argument("--candidate", default="C13-original", help="Candidate label stored in the run metadata (default: C13-original).")
    args = parser.parse_args()
    if args.seconds < 30 or args.seconds > 3600:
        parser.error("--seconds must be between 30 and 3600")
    if not ADB.is_file() or not FASTBOOT.is_file():
        print(f"Required local platform-tools are missing: {ADB} / {FASTBOOT}", file=sys.stderr)
        return 2

    run_dir = create_run_dir(args.output_base)
    started = time.monotonic()
    started_wall = utc_now()
    metadata = {
        "candidate": args.candidate,
        "observer_started_utc": started_wall,
        "serial": SERIAL,
        "observation_seconds": args.seconds,
        "run_dir": str(run_dir),
        "host_timezone": datetime.now().astimezone().tzname(),
    }
    (run_dir / "run_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    host_events_path = run_dir / "host_events.jsonl"
    append_host_event(host_events_path, "observer_started", candidate=args.candidate, serial=SERIAL)
    print(f"[INIT] Observer output: {run_dir}")
    print("[INIT] Read-only observer; it never boots, reboots, flashes, erases, or writes to the device.")
    print("[INFO] Wait for [ARMED] before the separately authorized startup command.")
    print("[INFO] If Recovery appears, do not confirm a wipe prompt; passive capture continues.")

    events_path = run_dir / "usb_adb_fastboot_timeline.csv"
    logcat_path = run_dir / "logcat_all_monotonic.txt"
    logcat_error_path = run_dir / "logcat_client_stderr.txt"
    previous = (None, None)
    next_snapshot = 0.0
    snapshot_index = 0
    pstore_capture_index = 0
    armed_written = False
    logcat_process: subprocess.Popen[bytes] | None = None
    snapshot_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="c13-readonly-snapshot")
    snapshot_future: Future[None] | None = None
    logcat_stdout = logcat_path.open("ab")
    logcat_stderr = logcat_error_path.open("ab")

    try:
        with events_path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow((
                "sample_started_utc", "sample_finished_utc", "elapsed_seconds",
                "adb_state", "fastboot_state", "adb_query_ms", "fastboot_query_ms",
                "adb_output", "fastboot_output",
            ))
            stream.flush()
            while time.monotonic() - started < args.seconds:
                sample_started = time.monotonic()
                sample_started_utc = utc_now()
                if snapshot_future is not None and snapshot_future.done():
                    try:
                        snapshot_future.result()
                    except Exception as exc:
                        print(f"[WARN] Read-only snapshot failed: {exc!r}", flush=True)
                    snapshot_future = None
                try:
                    adb_query_started = time.monotonic()
                    adb = run_readonly([str(ADB), "devices", "-l"])
                    adb_query_ms = round((time.monotonic() - adb_query_started) * 1000, 1)
                    adb_state = matching_state(adb.stdout, SERIAL, "device")
                    adb_output = (adb.stdout + adb.stderr).strip().replace("\r", " ").replace("\n", " | ")
                except (OSError, subprocess.TimeoutExpired) as exc:
                    adb_query_ms = round((time.monotonic() - adb_query_started) * 1000, 1)
                    adb_state, adb_output = "query_error", repr(exc)
                try:
                    fastboot_query_started = time.monotonic()
                    fastboot = run_readonly([str(FASTBOOT), "devices", "-l"])
                    fastboot_query_ms = round((time.monotonic() - fastboot_query_started) * 1000, 1)
                    fastboot_state = matching_state(fastboot.stdout, SERIAL, "fastboot")
                    fastboot_output = (fastboot.stdout + fastboot.stderr).strip().replace("\r", " ").replace("\n", " | ")
                except (OSError, subprocess.TimeoutExpired) as exc:
                    fastboot_query_ms = round((time.monotonic() - fastboot_query_started) * 1000, 1)
                    fastboot_state, fastboot_output = "query_error", repr(exc)

                sample_finished = time.monotonic()
                sample_finished_utc = utc_now()
                elapsed = sample_finished - started
                state_changed = (adb_state, fastboot_state) != previous
                adb_became_online = adb_state in ADB_SHELL_STATES and previous[0] not in ADB_SHELL_STATES
                adb_entered_recovery = adb_state == "recovery" and previous[0] != "recovery"
                adb_entered_sideload = adb_state == "sideload" and previous[0] != "sideload"
                writer.writerow((
                    sample_started_utc, sample_finished_utc, f"{elapsed:.3f}",
                    adb_state, fastboot_state, adb_query_ms, fastboot_query_ms,
                    adb_output, fastboot_output,
                ))
                stream.flush()
                if not armed_written:
                    armed = {
                        "candidate": args.candidate,
                        "armed_utc": sample_finished_utc,
                        "elapsed_seconds": round(elapsed, 3),
                        "serial": SERIAL,
                        "adb_state": adb_state,
                        "fastboot_state": fastboot_state,
                        "run_dir": str(run_dir),
                    }
                    (run_dir / "observer_armed.json").write_text(
                        json.dumps(armed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                    )
                    append_host_event(
                        host_events_path, "observer_armed", elapsed_seconds=round(elapsed, 3),
                        candidate=args.candidate, adb_state=adb_state, fastboot_state=fastboot_state,
                    )
                    print(
                        f"[ARMED] ADB={adb_state}; Fastboot={fastboot_state}; "
                        f"UTC={sample_finished_utc}; run={run_dir}", flush=True,
                    )
                    armed_written = True
                if state_changed:
                    print(f"[{elapsed:7.1f}s] ADB={adb_state}; Fastboot={fastboot_state}", flush=True)
                    if previous[0] != adb_state:
                        append_host_event(
                            host_events_path, "adb_state_change", elapsed_seconds=round(elapsed, 3),
                            state=adb_state, output=adb_output,
                        )
                    if previous[1] != fastboot_state:
                        append_host_event(
                            host_events_path, "fastboot_state_change", elapsed_seconds=round(elapsed, 3),
                            state=fastboot_state, output=fastboot_output,
                        )
                    previous = (adb_state, fastboot_state)
                if adb_entered_recovery:
                    print("[STOP CONDITION] ADB reports Recovery. Do not confirm wipe; keep the phone and cable in place while passive capture continues.", flush=True)
                elif adb_entered_sideload:
                    print("[STOP CONDITION] ADB reports sideload/Recovery. Do not interact with wipe options; this state is recorded without shell access.", flush=True)

                if adb_state in ADB_SHELL_STATES:
                    if logcat_process is None or logcat_process.poll() is not None:
                        logcat_started_utc = utc_now()
                        logcat_process = subprocess.Popen(
                            [str(ADB), "-s", SERIAL, "logcat", "-b", "all", "-v", "monotonic"],
                            stdout=logcat_stdout,
                            stderr=logcat_stderr,
                        )
                        append_host_event(
                            host_events_path, "logcat_stream_started", elapsed_seconds=round(time.monotonic() - started, 3),
                            host_pid=logcat_process.pid, state=adb_state, started_utc=logcat_started_utc,
                        )
                    if adb_became_online or adb_entered_recovery:
                        pstore_capture_index += 1
                        append_host_event(
                            host_events_path, "adb_pstore_capture_started",
                            elapsed_seconds=round(time.monotonic() - started, 3), state=adb_state,
                            capture_index=pstore_capture_index,
                        )
                        try:
                            capture_pstore_from_adb(run_dir, pstore_capture_index)
                            append_host_event(
                                host_events_path, "adb_pstore_capture_finished",
                                elapsed_seconds=round(time.monotonic() - started, 3), state=adb_state,
                                capture_index=pstore_capture_index,
                                directory=f"adb_pstore/capture_{pstore_capture_index:02d}",
                            )
                        except (OSError, subprocess.TimeoutExpired) as exc:
                            append_host_event(
                                host_events_path, "adb_pstore_capture_failed",
                                elapsed_seconds=round(time.monotonic() - started, 3), state=adb_state,
                                capture_index=pstore_capture_index, error=repr(exc),
                            )
                            print(f"[WARN] Read-only ADB pstore capture failed: {exc!r}", flush=True)
                    if elapsed >= next_snapshot and snapshot_future is None:
                        snapshot_index += 1
                        snapshot_future = snapshot_executor.submit(
                            snapshot, run_dir, snapshot_index, include_dmesg=(snapshot_index == 1)
                        )
                        next_snapshot = elapsed + (5.0 if snapshot_index < 12 else 15.0)

                time.sleep(max(0.0, 1.0 - (time.monotonic() - sample_started)))
    except KeyboardInterrupt:
        print("\n[STOP] Local observer stopped by Ctrl-C; no device reboot or write was issued.")
        append_host_event(host_events_path, "observer_stopped_by_user", elapsed_seconds=round(time.monotonic() - started, 3))
    finally:
        if logcat_process is not None and logcat_process.poll() is None:
            append_host_event(
                host_events_path, "logcat_stream_stopping", elapsed_seconds=round(time.monotonic() - started, 3),
                host_pid=logcat_process.pid,
            )
            logcat_process.terminate()
            try:
                logcat_process.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                logcat_process.kill()
                logcat_process.wait(timeout=3.0)
        if snapshot_future is not None:
            snapshot_future.cancel()
        snapshot_executor.shutdown(wait=False, cancel_futures=True)
        logcat_stdout.close()
        logcat_stderr.close()

    if time.monotonic() - started >= args.seconds:
        append_host_event(host_events_path, "observer_window_completed", elapsed_seconds=round(time.monotonic() - started, 3))
    print(f"[DONE] Evidence saved under {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
