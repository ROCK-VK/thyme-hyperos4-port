#!/usr/bin/env python3
"""
tools/build_candidate10_warm_dtb.py

Build Candidate 10-WarmDtb diagnostic assets:
1. Baseline: Candidate 9-InitFatalPanic (work/stage_c_thyme_os4_candidate_9_init_fatal_panic/images/)
2. Target Directory: work/stage_c_thyme_os4_candidate_10_warm_dtb/images/
3. Modification:
   - vendor_boot.img: Inject qcom,force-warm-reboot; into all 3 FDTs in restart@c264000 node
   - Keep Candidate 9 cmdline (reboot=panic_warm, androidboot.init_fatal_panic=true)
   - Add AVB Hash Footer to vendor_boot.img
   - Generate updated vbmeta.img (flags=3)
   - boot.img, dtbo.img, super.img, vbmeta_system.img: 100% identical to Candidate 9
"""

import os
import sys
import shutil
import struct
import hashlib
import subprocess
from pathlib import Path

ROOT = Path("[LOCAL_PROJECT_ROOT]")
sys.path.append(str(ROOT / "tools/bootimg"))
from avbtool import Avb, ImageHandler, AvbHashDescriptor

C9_DIR = ROOT / "work/stage_c_thyme_os4_candidate_9_init_fatal_panic/images"
OUT_DIR = ROOT / "work/stage_c_thyme_os4_candidate_10_warm_dtb/images"
OUT_DIR.mkdir(parents=True, exist_ok=True)
SCRATCH_DIR = ROOT / "work/scratch_c10_warm_dtb"
SCRATCH_DIR.mkdir(parents=True, exist_ok=True)

print(f"[INIT] Candidate 10-WarmDtb Build Starting...")
print(f"  Baseline: {C9_DIR}")
print(f"  Target:   {OUT_DIR}")

# 1. Hardlink unchanged assets from Candidate 9
unchanged_assets = ["boot.img", "dtbo.img", "super.img", "vbmeta_system.img"]
for name in unchanged_assets:
    src = C9_DIR / name
    dst = OUT_DIR / name
    if dst.exists():
        dst.unlink()
    try:
        os.link(src, dst)
        print(f"  [UNCHANGED - Hardlinked] {name}")
    except Exception:
        shutil.copy2(src, dst)
        print(f"  [UNCHANGED - Copied]     {name}")

# Verify identity of unchanged assets
for name in unchanged_assets:
    src_sha = hashlib.sha256((C9_DIR / name).read_bytes()).hexdigest()
    dst_sha = hashlib.sha256((OUT_DIR / name).read_bytes()).hexdigest()
    assert src_sha == dst_sha, f"Hash mismatch on asset {name}!"
    print(f"  -> {name} SHA256 verified identical: {src_sha[:16]}...")

# 2. Extract and modify 3 FDTs from Candidate 9 vendor_boot.img
c9_vendor_boot = C9_DIR / "vendor_boot.img"
with open(c9_vendor_boot, "rb") as f:
    orig_payload = f.read([REDACTED_DEVICE_ID])

# Verify v3 header
hdr = orig_payload[:2112]
magic, ver, page_sz, k_addr, rd_addr, rd_sz = struct.unpack('<8sIIIII', hdr[:28])
assert magic == b'VNDRBOOT', "Magic mismatch!"
assert ver == 3, "Version mismatch!"
assert page_sz == 4096, "Page size mismatch!"
assert rd_sz == [REDACTED_DEVICE_ID], f"Ramdisk size unexpected: {rd_sz}"

cmdline_bytes = hdr[28:28+2048]
orig_cmdline = cmdline_bytes.split(b"\x00")[0].decode("utf-8").strip()
print(f"\n[CMDLINE] Candidate 9 vendor_cmdline:\n  {orig_cmdline}")
assert "androidboot.init_fatal_panic=true" in orig_cmdline, "init_fatal_panic missing!"
assert "reboot=panic_warm" in orig_cmdline, "reboot=panic_warm missing!"
assert "reboot=w,panic_w" not in orig_cmdline, "Invalid C10 cmdline present in baseline!"

tags_addr, name, hdr_sz, dtb_sz, dtb_addr = struct.unpack('<I16sIIQ', hdr[2076:2112])
assert dtb_sz == 1424196, f"DTB size unexpected: {dtb_sz}"
assert dtb_addr == 0x1f00000, f"DTB addr unexpected: {hex(dtb_addr)}"

# Read 3 FDT slices
fdt_sizes = [477098, 477094, 470004]
dtb_start = [REDACTED_DEVICE_ID]
raw_dtb = orig_payload[dtb_start : dtb_start + dtb_sz]

fdt_blobs = [
    raw_dtb[0 : 477098],
    raw_dtb[477098 : 477098 + 477094],
    raw_dtb[477098 + 477094 : 1424196]
]

mod_fdt_blobs = []
target_anchor = 'reg-names = "pshold-base", "tcsr-boot-misc-detect";\n\t\t};'
replacement_str = 'reg-names = "pshold-base", "tcsr-boot-misc-detect";\n\t\t\tqcom,force-warm-reboot;\n\t\t};'

print("\n[FDT INJECTION] Modifying 3 FDTs with qcom,force-warm-reboot;...")
for i, blob in enumerate(fdt_blobs):
    in_dtb = SCRATCH_DIR / f"fdt{i}_orig.dtb"
    out_dts = SCRATCH_DIR / f"fdt{i}_orig.dts"
    mod_dts = SCRATCH_DIR / f"fdt{i}_mod.dts"
    out_dtb = SCRATCH_DIR / f"fdt{i}_mod.dtb"
    
    in_dtb.write_bytes(blob)
    
    # Decompile to DTS
    cmd_decomp = ["wsl", "dtc", "-I", "dtb", "-O", "dts", 
                  f"/mnt/e/RVK/10S_OS4/work/scratch_c10_warm_dtb/fdt{i}_orig.dtb", 
                  "-o", f"/mnt/e/RVK/10S_OS4/work/scratch_c10_warm_dtb/fdt{i}_orig.dts"]
    subprocess.run(cmd_decomp, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    
    dts_text = out_dts.read_text(encoding="utf-8")
    assert "restart@c264000" in dts_text, f"restart@c264000 missing in FDT #{i}!"
    assert target_anchor in dts_text, f"target_anchor missing in FDT #{i}!"
    
    # Inject property
    mod_text = dts_text.replace(target_anchor, replacement_str, 1)
    assert "qcom,force-warm-reboot;" in mod_text, f"Injection failed in FDT #{i}!"
    mod_dts.write_text(mod_text, encoding="utf-8")
    
    # Recompile to DTB
    cmd_comp = ["wsl", "dtc", "-I", "dts", "-O", "dtb", 
                f"/mnt/e/RVK/10S_OS4/work/scratch_c10_warm_dtb/fdt{i}_mod.dts", 
                "-o", f"/mnt/e/RVK/10S_OS4/work/scratch_c10_warm_dtb/fdt{i}_mod.dtb"]
    subprocess.run(cmd_comp, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    
    mod_blob = out_dtb.read_bytes()
    mod_magic, mod_totalsize = struct.unpack('>II', mod_blob[:8])
    assert mod_magic == 0xd00dfeed, f"Invalid FDT magic in FDT #{i}!"
    assert mod_totalsize == len(mod_blob), f"Size mismatch in FDT #{i}!"
    print(f"  -> FDT #{i}: orig={len(blob)} B, mod={len(mod_blob)} B (magic={hex(mod_magic)}, totalsize={mod_totalsize})")
    mod_fdt_blobs.append(mod_blob)

# Concatenate modified FDTs
new_dtb_blob = b"".join(mod_fdt_blobs)
new_dtb_size = len(new_dtb_blob)
print(f"\n[DTB BUNDLE] New DTB concatenated size: {new_dtb_size} bytes (delta: +{new_dtb_size - dtb_sz})")

# Check page alignment boundary
# DTB starts at [REDACTED_DEVICE_ID]. Next page boundary is [REDACTED_DEVICE_ID] (1425408 bytes allocated for DTB).
assert new_dtb_size <= 1425408, f"New DTB size {new_dtb_size} exceeds allocated page boundary 1425408!"
dtb_padding = b"\x00" * (1425408 - new_dtb_size)

# Update header with new dtb_size
# Header format at 2076: tags_addr (4), name (16), hdr_sz (4), dtb_sz (4), dtb_addr (8)
new_hdr_tail = struct.pack('<I16sIIQ', tags_addr, name, hdr_sz, new_dtb_size, dtb_addr)
new_hdr = orig_payload[:2076] + new_hdr_tail + orig_payload[2112:4096]
assert len(new_hdr) == 4096, f"Header size mismatch: {len(new_hdr)}"

# Ramdisk chunk (4096 to [REDACTED_DEVICE_ID])
ramdisk_chunk = orig_payload[4096:[REDACTED_DEVICE_ID]]
assert len(ramdisk_chunk) == [REDACTED_DEVICE_ID], f"Ramdisk chunk size mismatch: {len(ramdisk_chunk)}"

# Trailing data chunk ([REDACTED_DEVICE_ID] to [REDACTED_DEVICE_ID])
trailing_chunk = orig_payload[[REDACTED_DEVICE_ID]:[REDACTED_DEVICE_ID]]
assert len(trailing_chunk) == 4390912, f"Trailing chunk size mismatch: {len(trailing_chunk)}"

# Assemble new unpadded vendor_boot payload
new_payload = new_hdr + ramdisk_chunk + new_dtb_blob + dtb_padding + trailing_chunk
assert len(new_payload) == [REDACTED_DEVICE_ID], f"New payload size mismatch: {len(new_payload)} != [REDACTED_DEVICE_ID]"
print(f"[ASSEMBLY] New unpadded vendor_boot payload assembled: {len(new_payload)} bytes")

# Write unpadded vendor_boot
c10_vendor_boot = OUT_DIR / "vendor_boot.img"
if c10_vendor_boot.exists():
    c10_vendor_boot.unlink()
c10_vendor_boot.write_bytes(new_payload)

# 3. Add AVB Hash Footer to vendor_boot.img
avbtool_path = ROOT / "tools/bootimg/avbtool.py"
add_footer_cmd = [
    sys.executable, str(avbtool_path),
    "add_hash_footer",
    "--image", str(c10_vendor_boot),
    "--partition_size", "100663296",
    "--partition_name", "vendor_boot",
    "--algorithm", "NONE",
    "--salt", "c5ffc2c51fef1864ad27e6903e582f52611121819811b66eb40f6ea9b60350c5",
    "--prop", "com.android.build.vendor_boot.fingerprint:Xiaomi/custom_thyme/thyme:17/CP2A.260605.016/eng.androi:user/release-keys",
    "--prop", "com.android.build.vendor.os_version:17"
]
print("\n[AVB] Adding AVB hash footer to vendor_boot.img...")
subprocess.run(add_footer_cmd, check=True)
assert c10_vendor_boot.stat().st_size == 100663296, f"Padded vendor_boot size unexpected: {c10_vendor_boot.stat().st_size}"
print(f"  -> vendor_boot.img footered successfully: {c10_vendor_boot.stat().st_size} bytes")

# 4. Generate matching vbmeta.img
print("\n[AVB] Updating vbmeta.img with Candidate 10-WarmDtb descriptor...")
avb = Avb()
footer_vm, h_vm, descriptors, size_vm = avb._parse_image(ImageHandler(str(C9_DIR / "vbmeta.img")))
footer_vb, h_vb, desc_vb, size_vb = avb._parse_image(ImageHandler(str(c10_vendor_boot)))
new_vb_hash_desc = desc_vb[0]

new_descriptors = []
for d in descriptors:
    if isinstance(d, AvbHashDescriptor) and d.partition_name == "vendor_boot":
        new_descriptors.append(new_vb_hash_desc)
    else:
        new_descriptors.append(d)

c10_vbmeta = OUT_DIR / "vbmeta.img"
if c10_vbmeta.exists():
    c10_vbmeta.unlink()

blob = avb._generate_vbmeta_blob(
    algorithm_name="NONE",
    key_path=None,
    public_key_metadata_path=None,
    descriptors=new_descriptors,
    chain_partitions_use_ab=None,
    chain_partitions_do_not_use_ab=None,
    rollback_index=0,
    flags=3,
    rollback_index_location=0,
    props=None,
    props_from_file=None,
    kernel_cmdlines=None,
    setup_rootfs_from_kernel=None,
    ht_desc_to_setup=None,
    include_descriptors_from_image=None,
    signing_helper=None,
    signing_helper_with_files=None,
    release_string=None,
    append_to_release_string=None,
    required_libavb_version_minor=0
)

padding_size = 131072
if len(blob) < padding_size:
    blob += b"\0" * (padding_size - len(blob))

c10_vbmeta.write_bytes(blob)
assert c10_vbmeta.stat().st_size == 131072, f"vbmeta size unexpected: {c10_vbmeta.stat().st_size}"
print(f"  -> vbmeta.img generated successfully: {c10_vbmeta.stat().st_size} bytes (flags=3)")

# 5. Readback Verification
print("\n[VERIFY] AVB Image Info Verification...")
subprocess.run([sys.executable, str(avbtool_path), "info_image", "--image", str(c10_vbmeta)], check=True)
subprocess.run([sys.executable, str(avbtool_path), "info_image", "--image", str(c10_vendor_boot)], check=True)

print("\n=== Candidate 10-WarmDtb Image Manifest ===")
for p in sorted(OUT_DIR.glob("*.img")):
    sz = p.stat().st_size
    sha = hashlib.sha256(p.read_bytes()).hexdigest().upper()
    print(f"  {p.name:20s}: {sz:10d} B, SHA256={sha}")

print(f"\n[DONE] Candidate 10-WarmDtb Build Completed Successfully!")
