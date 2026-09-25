import os
import sys
import time
import shutil
import hashlib
import subprocess

REPO_ROOT = "[LOCAL_PROJECT_ROOT]"
EXPORT_DIR = os.path.join(REPO_ROOT, "work", "reports", "20260924_CANDIDATE11_LOG_SALVAGE")
DIAG_BOOT = os.path.join(REPO_ROOT, "work", "standalone_diag", "standalone_diag_boot.img")
os.makedirs(EXPORT_DIR, exist_ok=True)

def get_drive_letters():
    drives = []
    for c in "FGHIJKLMNOPQRSTUVWXYZ":
        d = f"{c}:\\"
        if os.path.exists(d):
            drives.append(d)
    return drives

print("=== CANDIDATE 11 STANDALONE DIAG SALVAGE ===")

# Step 1: Verify Fastboot
res = subprocess.run(["fastboot", "devices"], capture_output=True, text=True)
if "[REDACTED_DEVICE_ID]" not in res.stdout and "fastboot" not in res.stdout:
    print("[ERROR] Device not found in fastboot mode!")
    sys.exit(1)
print(f"[FASTBOOT] Device detected: {res.stdout.strip()}")

# Step 2: Boot Standalone Diag
initial_drives = set(get_drive_letters())
print(f"[BOOT] Booting Standalone Diag into RAM: {DIAG_BOOT}")
boot_res = subprocess.run(["fastboot", "-s", "[REDACTED_DEVICE_ID]", "boot", DIAG_BOOT], capture_output=True, text=True)
print("Boot stdout:", boot_res.stdout)
print("Boot stderr:", boot_res.stderr)

if boot_res.returncode != 0:
    print("[ERROR] fastboot boot failed!")
    sys.exit(1)

# Step 3: Wait for USB Mass Storage drive THYME_DIAG
print("Waiting for THYME_DIAG USB Mass Storage disk to appear...")
target_drive = None
start_time = time.time()
timeout = 180

while time.time() - start_time < timeout:
    try:
        cmd = ["powershell", "-NoProfile", "-Command", "Get-Volume | Where-Object { $_.FileSystemLabel -eq 'THYME_DIAG' } | Select-Object -ExpandProperty DriveLetter"]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        dl = r.stdout.strip()
        if dl and len(dl) == 1 and dl.isalpha():
            target_drive = f"{dl}:\\"
            print(f"\n[DETECTED] Found THYME_DIAG at {target_drive}")
            break
    except Exception as e:
        pass

    current = set(get_drive_letters())
    diff = current - initial_drives
    if diff:
        target_drive = list(diff)[0]
        print(f"\n[DETECTED] New drive appeared: {target_drive}")
        break

    sys.stdout.write(".")
    sys.stdout.flush()
    time.sleep(2)

if not target_drive:
    print("\n[TIMEOUT] THYME_DIAG drive did not appear within 180s!")
    sys.exit(1)

# Step 4: Copy files
print(f"\n[EXPORT] Copying files from {target_drive} to {EXPORT_DIR}...")
time.sleep(3)

found_files = []
for root, dirs, files in os.walk(target_drive):
    for f in files:
        full_path = os.path.join(root, f)
        rel_path = os.path.relpath(full_path, target_drive)
        dest_path = os.path.join(EXPORT_DIR, rel_path)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        try:
            shutil.copy2(full_path, dest_path)
            sz = os.path.getsize(dest_path)
            with open(dest_path, "rb") as fp:
                sha = hashlib.sha256(fp.read()).hexdigest()
            print(f"  [SAVED] {rel_path:35s} ({sz:10,d} bytes) SHA256={sha[:16]}...")
            found_files.append((rel_path, sz, sha))
        except Exception as e:
            print(f"  [ERR] Failed to copy {rel_path}: {e}")

print(f"\n[SUMMARY] Total {len(found_files)} files copied.")

# Step 5: Quick Analysis
dmesg_path = os.path.join(EXPORT_DIR, "dmesg_diag_boot.txt")
if os.path.exists(dmesg_path):
    print("\n--- OBJECTIVE A: PMIC POWER-ON REASON INSPECTION ---")
    with open(dmesg_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if "Power-on reason" in line or "power-on" in line.lower() or "pmic" in line.lower() and "reason" in line.lower():
                print("  ", line.strip())
            elif "reboot_mode" in line or "warm" in line.lower() and "reset" in line.lower():
                print("  ", line.strip())

ramoops_path = os.path.join(EXPORT_DIR, "pstore", "console-ramoops-0")
if os.path.exists(ramoops_path):
    sz = os.path.getsize(ramoops_path)
    print(f"\n--- OBJECTIVE B: CONSOLE-RAMOOPS-0 FOUND ({sz} bytes) ---")
    with open(ramoops_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
        print(f"Total lines: {len(lines)}")
        print("Last 30 lines:")
        for l in lines[-30:]:
            print("  ", l.rstrip())
else:
    print("\n[NOTE] pstore/console-ramoops-0 not found in export.")

status_path = os.path.join(EXPORT_DIR, "diag_status.log")
if os.path.exists(status_path):
    print("\n--- DIAG STATUS LOG ---")
    with open(status_path, "r", encoding="utf-8", errors="ignore") as f:
        print(f.read())
