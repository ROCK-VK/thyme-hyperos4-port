#!/usr/bin/env python3
import os
import subprocess
import shutil
import hashlib

def run(cmd):
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return res.returncode, res.stdout, res.stderr

print("=== AUDITING CANDIDATE 8 PROPERTY CONTEXTS ACROSS ALL PARTITIONS ===")

wsl_images = {
    "system": "/path/to/thyme-os4-build/c7_stage/system_sar_avb.img",
    "system_ext": "/path/to/thyme-os4-build/thyme_xiaomi15_os4_first_boot_candidate_1/super/avb_images/system_ext.img",
    "product": "/path/to/thyme-os4-build/thyme_xiaomi15_os4_first_boot_candidate_1/super/avb_images/product.img",
    "vendor": "/path/to/thyme-os4-build/thyme_xiaomi15_os4_first_boot_candidate_1/provider_images/vendor.img",
    "odm": "/path/to/thyme-os4-build/thyme_xiaomi15_os4_first_boot_candidate_1/provider_images/odm.img",
    "mi_ext": "/path/to/thyme-os4-build/thyme_xiaomi15_os4_first_boot_candidate_1/super/avb_images/mi_ext.img",
}

stage_dir = "/path/to/thyme-os4-local/work/audit_c8_property_contexts"
shutil.rmtree(stage_dir, ignore_errors=True)
os.makedirs(stage_dir, exist_ok=True)

extracted_files = {}

for part, img_path in wsl_images.items():
    print(f"\nChecking partition: {part} ({img_path})...")
    
    part_mount = f"/tmp/mnt_{part}"
    os.makedirs(part_mount, exist_ok=True)
    
    run(f"umount -f {part_mount} 2>/dev/null")
    code, _, err = run(f"mount -o ro,loop {img_path} {part_mount}")
    if code != 0:
        run(f"7z x {img_path} -o{part_mount} etc/selinux/*property_contexts* system/etc/selinux/*property_contexts* -r -y >/dev/null")
    
    found = []
    for root, dirs, files in os.walk(part_mount):
        for f in files:
            if "property_contexts" in f:
                full_p = os.path.join(root, f)
                rel_p = os.path.relpath(full_p, part_mount)
                dst = os.path.join(stage_dir, f"{part}_{f}")
                shutil.copy2(full_p, dst)
                found.append((rel_p, dst))
                
    run(f"umount -f {part_mount} 2>/dev/null")
    shutil.rmtree(part_mount, ignore_errors=True)
    
    print(f"  Found {len(found)} property_contexts in {part}:")
    for rel_p, dst in found:
        sz = os.path.getsize(dst)
        sha = hashlib.sha256(open(dst, 'rb').read()).hexdigest().upper()
        lines = open(dst, 'r', errors='ignore').readlines()
        print(f"    - {rel_p}: {sz:,} bytes, {len(lines)} lines, SHA256: {sha}")
        extracted_files[f"{part}:{rel_p}"] = dst

print("\n=== EXTRACTED FILES PERMANENTLY SAVED ===")
for k, v in extracted_files.items():
    print(k, "->", v)
