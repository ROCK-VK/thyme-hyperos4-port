#!/usr/bin/env python3
"""
tools/build_candidate13.py
Constructs Candidate 13 (Treble SELinux Minimal Fix Candidate):
1. Baseline: Candidate 12 (work/stage_c_thyme_os4_candidate_12_ion_fix/images/)
2. Target Directory: work/stage_c_thyme_os4_candidate_13_treble_ion_fix/images/
3. Core Modification:
   - Copies system_ext_tree from c12_build_stage to c13_build_stage.
   - Appends surgical Treble SELinux allow rules to system_ext_tree/etc/selinux/system_ext_sepolicy.cil:
       (allow hal_keymaster ion_device (chr_file (ioctl read getattr lock map open watch watch_reads)))
       (allow hal_gatekeeper ion_device (chr_file (ioctl read getattr lock map open watch watch_reads)))
   - Strictly preserves Candidate 12's /dev/ion -> ion_device mapping in system_ext_file_contexts.
   - Strictly preserves Candidate 9's PropertyContexts fix (lines 278-282 deduplicated).
   - Strictly preserves Candidate 11's system_ext inode metadata fixes (/apex mode 0755, uid/gid 0, security.selinux).
   - Re-packs system_ext_c13.raw.erofs via mkfs.erofs with:
     --fs-config-file=/path/to/thyme-os4-build/thyme_xiaomi15_os4_first_boot_candidate_1/configs_retained/system_ext/fs_config
     --file-contexts=/path/to/thyme-os4-build/thyme_xiaomi15_os4_first_boot_candidate_1/configs_retained/system_ext/file_contexts
   - Injects AVB hashtree footer to system_ext_c13.img (size 942,669,824 bytes).
   - Updates vbmeta_system.img with the new system_ext hashtree descriptor.
   - Re-assembles super.img via lpmake preserving all other 5 partition images.
4. Strictly Preserved Assets (Zero Mutation):
   - boot.img: 100% identical to Candidate 12 (A5 Kernel, panic=0)
   - vendor_boot.img: 100% identical to Candidate 12 (WarmDtb, qcom,force-warm-reboot, androidboot.init_fatal_panic=true)
   - dtbo.img: 100% identical to Candidate 12 (hardware DTBO idx 10)
   - vbmeta.img: 100% identical to Candidate 12 (flags=3, dev chain)
"""

import os
import sys
import shutil
import subprocess
import hashlib
from pathlib import Path

ROOT = Path("[LOCAL_PROJECT_ROOT]")
WSL_ROOT = "/path/to/thyme-os4-local"
sys.path.append(str(ROOT / "tools/bootimg"))
from avbtool import Avb, ImageHandler, AvbHashtreeDescriptor

C12_DIR = ROOT / "work/stage_c_thyme_os4_candidate_12_ion_fix/images"
C13_DIR = ROOT / "work/stage_c_thyme_os4_candidate_13_treble_ion_fix/images"
C13_DIR.mkdir(parents=True, exist_ok=True)

print("=" * 72)
print("=== BUILDING THYME-OS4 CANDIDATE 13 (TREBLE SELINUX MINIMAL FIX) ===")
print("=" * 72)
print(f"Source Baseline: {C12_DIR}")
print(f"Target Directory: {C13_DIR}")

def run_wsl(cmd_str: str) -> subprocess.CompletedProcess:
    full_cmd = ["wsl", "-d", "Ubuntu", "-e", "bash", "-c", cmd_str]
    print(f"[WSL CMD] {cmd_str[:120]}..." if len(cmd_str) > 120 else f"[WSL CMD] {cmd_str}")
    res = subprocess.run(full_cmd, capture_output=True, encoding="utf-8", errors="replace")
    if res.returncode != 0:
        print(f"[WSL ERROR returncode={res.returncode}]")
        print(f"STDOUT:\n{res.stdout}")
        print(f"STDERR:\n{res.stderr}")
        raise RuntimeError(f"WSL command failed: {cmd_str}")
    return res

def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest().upper()

# 1. Copy unchanged boot, vendor_boot, dtbo, vbmeta from Candidate 12
unchanged = ["boot.img", "vendor_boot.img", "dtbo.img", "vbmeta.img"]
for name in unchanged:
    src = C12_DIR / name
    dst = C13_DIR / name
    if dst.exists():
        dst.unlink()
    shutil.copy2(src, dst)
    src_sha = sha256_file(src)
    dst_sha = sha256_file(dst)
    assert src_sha == dst_sha, f"Hash mismatch on {name}!"
    print(f"[UNCHANGED] {name:20s}: {dst.stat().st_size:,} bytes, SHA256={dst_sha}")

# 2. Prepare C13 staging in WSL
wsl_stage = "/path/to/thyme-os4-build/c13_build_stage"
wsl_src_tree = "/path/to/thyme-os4-build/c12_build_stage/system_ext_tree"
wsl_tree = f"{wsl_stage}/system_ext_tree"
wsl_fs_cfg = "/path/to/thyme-os4-build/thyme_xiaomi15_os4_first_boot_candidate_1/configs_retained/system_ext/fs_config"
wsl_file_ctx = "/path/to/thyme-os4-build/thyme_xiaomi15_os4_first_boot_candidate_1/configs_retained/system_ext/file_contexts"
wsl_raw_erofs = f"{wsl_stage}/system_ext_c13.raw.erofs"
wsl_avb_img = f"{wsl_stage}/system_ext_c13.img"
wsl_mkfs = f"{WSL_ROOT}/tools/erofs-utils/wsl/mkfs.erofs"
wsl_fsck = f"{WSL_ROOT}/tools/erofs-utils/wsl/fsck.erofs"
wsl_dump = f"{WSL_ROOT}/tools/erofs-utils/wsl/dump.erofs"
wsl_avbtool = f"{WSL_ROOT}/tools/bootimg/avbtool.py"
wsl_c1_base = "/path/to/thyme-os4-build/thyme_xiaomi15_os4_first_boot_candidate_1"

print("\n[Step 1] Preparing isolated C13 system_ext_tree...")
run_wsl(f"mkdir -p {wsl_stage}")
# Copy isolated system_ext_tree if not already copied
res = run_wsl(f"[ -d {wsl_tree} ] && echo 'EXISTS' || echo 'NOT_EXISTS'")
if "NOT_EXISTS" in res.stdout:
    print("  Copying system_ext_tree to C13 stage...")
    run_wsl(f"cp -a {wsl_src_tree} {wsl_tree}")
    print("  system_ext_tree isolated copy created.")
else:
    print("  Isolated system_ext_tree already exists in C13 stage.")

# 3. Apply Minimal Fix: Append surgical allow rules to system_ext_sepolicy.cil
print("\n[Step 2] Applying minimal fix to system_ext_sepolicy.cil...")
target_cil = f"{wsl_tree}/etc/selinux/system_ext_sepolicy.cil"

# Check if rules already present
res_cil = run_wsl(f"grep 'allow hal_keymaster ion_device' {target_cil} || true")
if "allow hal_keymaster ion_device" in res_cil.stdout:
    print(f"  Rules already present in system_ext_sepolicy.cil:\n{res_cil.stdout.strip()}")
else:
    print("  Appending surgical rules to system_ext_sepolicy.cil...")
    fix_rules_sh = (
        f"echo '; Candidate 13 Minimal Fix: allow hal_keymaster and hal_gatekeeper to access ion_device' >> {target_cil} && "
        f"echo '(allow hal_keymaster ion_device (chr_file (ioctl read getattr lock map open watch watch_reads)))' >> {target_cil} && "
        f"echo '(allow hal_gatekeeper ion_device (chr_file (ioctl read getattr lock map open watch watch_reads)))' >> {target_cil}"
    )
    run_wsl(fix_rules_sh)
    res_cil = run_wsl(f"tail -n 4 {target_cil}")
    print(f"  Appended successfully:\n{res_cil.stdout.strip()}")

# Verify Candidate 12 /dev/ion mapping in system_ext_file_contexts is intact
target_fc = f"{wsl_tree}/etc/selinux/system_ext_file_contexts"
res_fc = run_wsl(f"grep '/dev/ion' {target_fc}")
assert "/dev/ion" in res_fc.stdout and "ion_device:s0" in res_fc.stdout, "Candidate 12 /dev/ion fix missing from tree!"
print("  Candidate 12 /dev/ion file context fix intact.")

# Verify Candidate 9 PropertyContexts fix is intact
verify_prop_cmd = f"grep -n 'C9_FIX_DUPLICATE_PREFIX' {wsl_tree}/etc/selinux/system_ext_property_contexts"
res_prop = run_wsl(verify_prop_cmd)
assert "persist.radio.imei" in res_prop.stdout, "Candidate 9 property context fix missing from tree!"
print("  Candidate 9 property contexts fix intact.")

# 4. Build system_ext_c13.raw.erofs using mkfs.erofs with full metadata
print("\n[Step 3] Building system_ext_c13.raw.erofs with mkfs.erofs...")
mkfs_cmd = (
    f"{wsl_mkfs} -zlz4hc -T 0 -U [REDACTED_DEVICE_ID]-9266-550f-9093-74a7abd8693f --mount-point=/system_ext "
    f"--fs-config-file={wsl_fs_cfg} --file-contexts={wsl_file_ctx} "
    f"{wsl_raw_erofs} {wsl_tree}"
)
run_wsl(mkfs_cmd)
run_wsl(f"{wsl_fsck} -d0 {wsl_raw_erofs}")
print("  system_ext_c13.raw.erofs built and verified with fsck.erofs!")

# Verify xattrs on /apex and /etc/selinux/system_ext_property_contexts
print("\n[Step 4] Verifying inode xattr sizes in system_ext_c13...")
res_apex = run_wsl(f"{wsl_dump} --path=/apex {wsl_raw_erofs}")
for l in res_apex.stdout.splitlines():
    if "Inode size:" in l or "Uid:" in l:
        print("  /apex: " + l.strip())
assert "Xattr size: 16" in res_apex.stdout, "ERROR: /apex does not have Xattr size: 16!"

res_prop = run_wsl(f"{wsl_dump} --path=/etc/selinux/system_ext_property_contexts {wsl_raw_erofs}")
for l in res_prop.stdout.splitlines():
    if "Inode size:" in l or "Uid:" in l:
        print("  /etc/selinux/system_ext_property_contexts: " + l.strip())
assert "Xattr size: 60" in res_prop.stdout, "ERROR: property contexts does not have Xattr size: 60!"

# Verify that /etc/selinux/system_ext_sepolicy.cil inside raw image contains new rules
res_extract = run_wsl(f"{WSL_ROOT}/tools/erofs-utils/wsl/dump.erofs --cat --path=/etc/selinux/system_ext_sepolicy.cil {wsl_raw_erofs} | tail -n 4")
print(f"  Verified rules inside system_ext_c13.raw.erofs:\n{res_extract.stdout.strip()}")
assert "allow hal_keymaster ion_device" in res_extract.stdout, "ERROR: keymaster rule missing in raw.erofs!"
assert "allow hal_gatekeeper ion_device" in res_extract.stdout, "ERROR: gatekeeper rule missing in raw.erofs!"

# 5. Add AVB hashtree footer to system_ext_c13.img
print("\n[Step 5] Adding AVB hashtree footer to system_ext_c13.img...")
SALT = "c5ffc2c51fef1864ad27e6903e582f52611121819811b66eb40f6ea9b60350c5"
PARTITION_SIZE_SYSTEM_EXT = 942_669_824

avb_footer_cmd = (
    f"cp -f {wsl_raw_erofs} {wsl_avb_img} && "
    f"python3 {wsl_avbtool} add_hashtree_footer "
    f"--image {wsl_avb_img} "
    f"--partition_size {PARTITION_SIZE_SYSTEM_EXT} "
    f"--partition_name system_ext "
    f"--hash_algorithm sha256 "
    f"--salt {SALT} "
    f"--algorithm NONE "
    f"--do_not_generate_fec"
)
run_wsl(avb_footer_cmd)

# Verify avb size
res = run_wsl(f"stat -c %s {wsl_avb_img}")
actual_sz = int(res.stdout.strip())
assert actual_sz == PARTITION_SIZE_SYSTEM_EXT, f"Size mismatch: {actual_sz} != {PARTITION_SIZE_SYSTEM_EXT}"
print(f"  system_ext_c13.img size verified: {actual_sz:,} bytes (exact match).")

# 6. Extract new hashtree descriptor and update vbmeta_system.img
print("\n[Step 6] Updating vbmeta_system.img with Candidate 13 system_ext descriptor...")
wsl_c13_sys_ext_local = C13_DIR / "system_ext_c13.img"
run_wsl(f"cp -f {wsl_avb_img} {WSL_ROOT}/work/stage_c_thyme_os4_candidate_13_treble_ion_fix/images/system_ext_c13.img")

avb = Avb()
footer_vbs, h_vbs, desc_vbs, sz_vbs = avb._parse_image(ImageHandler(str(C12_DIR / "vbmeta_system.img")))
footer_se, h_se, desc_se, sz_se = avb._parse_image(ImageHandler(str(wsl_c13_sys_ext_local)))
new_se_desc = desc_se[0]

new_vbs_descriptors = []
for d in desc_vbs:
    if isinstance(d, AvbHashtreeDescriptor) and d.partition_name == "system_ext":
        new_vbs_descriptors.append(new_se_desc)
        print(f"  Replaced system_ext descriptor: root_digest={new_se_desc.root_digest.hex()[:16]}... size={new_se_desc.image_size}")
    else:
        new_vbs_descriptors.append(d)

vbs_blob = avb._generate_vbmeta_blob(
    algorithm_name="NONE",
    key_path=None,
    public_key_metadata_path=None,
    descriptors=new_vbs_descriptors,
    chain_partitions_use_ab=None,
    chain_partitions_do_not_use_ab=None,
    rollback_index=0,
    flags=2,
    rollback_index_location=2,
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
if len(vbs_blob) < padding_size:
    vbs_blob += b"\0" * (padding_size - len(vbs_blob))

c13_vbmeta_system = C13_DIR / "vbmeta_system.img"
with open(c13_vbmeta_system, "wb") as f:
    f.write(vbs_blob)
print(f"Saved vbmeta_system.img: {c13_vbmeta_system.stat().st_size} bytes")

# 7. Assemble Candidate 13 super.img with lpmake
print("\n[Step 7] Assembling Candidate 13 super.img with lpmake...")
wsl_lpmake = f"{WSL_ROOT}/tools/android-tools-static/linux/android-tools-static/lpmake"
wsl_simg2img = f"{WSL_ROOT}/tools/android-tools-static/linux/android-tools-static/simg2img"
wsl_lpdump = f"{WSL_ROOT}/tools/android-tools-static/linux/android-tools-static/lpdump"

DEVICE_SIZE = 9_126_805_504
GROUP_SIZE = DEVICE_SIZE
ALIGNMENT = 1_048_576

PARTITION_EXTENTS = {
    "mi_ext_a": 202_375_168,
    "odm_a": 36_700_160,
    "product_a": 4_387_241_984,
    "system_a": 1_092_616_192,
    "system_ext_a": 942_669_824,
    "vendor_a": 1_510_998_016,
}

wsl_super_sparse = f"{wsl_stage}/super_c13_sparse.img"
wsl_super_raw = f"{wsl_stage}/super_c13_raw.img"
wsl_system_sar_avb = "/path/to/thyme-os4-build/c7_stage/system_sar_avb.img"

lpmake_cmd = (
    f"{wsl_lpmake} --metadata-size 65536 --metadata-slots 3 --device-size {DEVICE_SIZE} "
    f"--block-size 4096 --alignment {ALIGNMENT} --virtual-ab --sparse --super-name super "
    f"--group qti_dynamic_partitions_a:{GROUP_SIZE} --group qti_dynamic_partitions_b:{GROUP_SIZE} "
    f"--partition mi_ext_a:readonly:{PARTITION_EXTENTS['mi_ext_a']}:qti_dynamic_partitions_a "
    f"--partition mi_ext_b:none:0:qti_dynamic_partitions_b "
    f"--partition odm_a:readonly:{PARTITION_EXTENTS['odm_a']}:qti_dynamic_partitions_a "
    f"--partition odm_b:none:0:qti_dynamic_partitions_b "
    f"--partition product_a:readonly:{PARTITION_EXTENTS['product_a']}:qti_dynamic_partitions_a "
    f"--partition product_b:none:0:qti_dynamic_partitions_b "
    f"--partition system_a:readonly:{PARTITION_EXTENTS['system_a']}:qti_dynamic_partitions_a "
    f"--partition system_b:none:0:qti_dynamic_partitions_b "
    f"--partition system_ext_a:readonly:{PARTITION_EXTENTS['system_ext_a']}:qti_dynamic_partitions_a "
    f"--partition system_ext_b:none:0:qti_dynamic_partitions_b "
    f"--partition vendor_a:readonly:{PARTITION_EXTENTS['vendor_a']}:qti_dynamic_partitions_a "
    f"--partition vendor_b:none:0:qti_dynamic_partitions_b "
    f"--image mi_ext_a={wsl_c1_base}/super/avb_images/mi_ext.img "
    f"--image odm_a={wsl_c1_base}/provider_images/odm.img "
    f"--image product_a={wsl_c1_base}/super/avb_images/product.img "
    f"--image system_a={wsl_system_sar_avb} "
    f"--image system_ext_a={wsl_avb_img} "
    f"--image vendor_a={wsl_c1_base}/provider_images/vendor.img "
    f"--output {wsl_super_sparse}"
)
run_wsl(lpmake_cmd)
print("  lpmake finished successfully.")

# 8. Verify super.img with simg2img and lpdump
print("\n[Step 8] Verifying super.img with simg2img and lpdump...")
run_wsl(f"{wsl_simg2img} {wsl_super_sparse} {wsl_super_raw}")
res_dump = run_wsl(f"{wsl_lpdump} {wsl_super_raw}")
print(f"lpdump output length: {len(res_dump.stdout)} chars")
assert "system_ext_a" in res_dump.stdout, "system_ext_a partition missing in super lpdump!"
run_wsl(f"rm -f {wsl_super_raw}")

# Copy super to local C13 dir
print(f"Copying super.img to {C13_DIR}...")
run_wsl(f"cp -f {wsl_super_sparse} {WSL_ROOT}/work/stage_c_thyme_os4_candidate_13_treble_ion_fix/images/super.img")

print("\n" + "=" * 72)
print("=== CANDIDATE 13 BUILD COMPLETE ===")
print("=" * 72)
for f in C13_DIR.glob("*"):
    print(f"  {f.name:25s}: {f.stat().st_size:,} bytes, SHA256={sha256_file(f)}")
