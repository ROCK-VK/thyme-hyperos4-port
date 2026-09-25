#!/usr/bin/env python3
import os
import hashlib

log_path = r"work\reports\20260923_CANDIDATE5_PANIC0_LOG_SALVAGE\pstore\console-ramoops-0"
sz = os.path.getsize(log_path)
with open(log_path, "rb") as f:
    sha = hashlib.sha256(f.read()).hexdigest().upper()

print("=" * 70)
print("=== CANDIDATE 5 CONSOLE-RAMOOPS-0 DEEP AUDIT ===")
print("=" * 70)
print(f"File Path: {log_path}")
print(f"Size:      {sz} bytes")
print(f"SHA-256:   {sha}")

with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
    lines = f.readlines()

content = "".join(lines)
print(f"Total Lines: {len(lines)}")

print("\n--- 1. KERNEL VERSION & BUILD IDENTITY ---")
for l in lines[:10]:
    if "Linux version" in l or "Machine model" in l or "Command line" in l or "Kernel command line" in l:
        print("  " + l.strip())

print("\n--- 2. FIRST-STAGE INIT & MOUNT EVENTS ---")
for l in lines:
    if any(k in l for k in ["init:", "Switching root", "metadata", "e2fsck", "erofs", "dm-"]):
        print("  " + l.strip())

print("\n--- 3. THE SMOKING-GUN PANIC CONTEXT (LINES 1815-1845) ---")
for i in range(1810, min(len(lines), 1845)):
    print(f"  [{i:4d}] {lines[i].strip()}")

print("\n--- 4. FULL CALL TRACE OF PANICKING CPU (PID 1 INIT) ---")
panic_idx = -1
for i, l in enumerate(lines):
    if "Attempted to kill init" in l:
        panic_idx = i
        break

if panic_idx != -1:
    for i in range(panic_idx, min(len(lines), panic_idx + 35)):
        print(f"  {lines[i].strip()}")

print("\n--- 5. CHECK SPECIFIC ERROR PATTERNS ---")
patterns = {
    "Kernel panic - not syncing": "Kernel panic - not syncing" in content,
    "Attempted to kill init": "Attempted to kill init" in content,
    "Failed to mount required partitions early": "Failed to mount required partitions early" in content,
    "execv(\"/system/bin/init\") failed": 'execv("/system/bin/init") failed' in content,
    "Unrecognized mount option barrier=1": "barrier=1" in content,
    "AVB / verity error": "verity" in content and "corrupted" in content,
    "dm-linear error": "dm-linear" in content,
    "EROFS mount failure": "erofs_parse_options" in content,
}

for k, v in patterns.items():
    print(f"  {k:45s}: {v}")

print("=" * 70)
