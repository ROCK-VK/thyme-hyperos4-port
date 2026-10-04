#!/usr/bin/env python3
"""Build a minimal C16 SELinux fix from the C15 ANGLE EGL experiment.

The sole C16 source change is granting the actual graphics allocator domain
the `read` permission denied by the C14 and C15 pstore AVCs.  C15's ANGLE
property and BPF bypass remain unchanged.  This script performs host-side
builds only; it never invokes adb or fastboot.
"""

from __future__ import annotations

import hashlib
import json
import shlex
import shutil
import subprocess
import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
C15_IMAGES = ROOT / "work/stage_e_thyme_os4_candidate_15_angle_egl_run1/images"
C16_DIR = ROOT / "work/stage_f_thyme_os4_candidate_16_graphics_allocator_ion_run1"
C16_IMAGES = C16_DIR / "images"

WSL_ROOT = "/path/to/thyme-os4-local"
WSL_C15_STAGE = "/path/to/thyme-os4-build/c15_angle_egl_20260926_run1"
WSL_C16_STAGE = "/path/to/thyme-os4-build/c16_graphics_allocator_ion_20260926_run1"
WSL_C1_BASE = "/path/to/thyme-os4-build/thyme_xiaomi15_os4_first_boot_candidate_1"
WSL_C15_IMAGES = f"{WSL_ROOT}/work/stage_e_thyme_os4_candidate_15_angle_egl_run1/images"
WSL_C16_IMAGES = f"{WSL_ROOT}/work/stage_f_thyme_os4_candidate_16_graphics_allocator_ion_run1/images"

MKFS = f"{WSL_ROOT}/tools/erofs-utils/wsl/mkfs.erofs"
FSCK = f"{WSL_ROOT}/tools/erofs-utils/wsl/fsck.erofs"
DUMP = f"{WSL_ROOT}/tools/erofs-utils/wsl/dump.erofs"
LPMAKE = f"{WSL_ROOT}/tools/android-tools-static/linux/android-tools-static/lpmake"
SIMG2IMG = f"{WSL_ROOT}/tools/android-tools-static/linux/android-tools-static/simg2img"
LPDUMP = f"{WSL_ROOT}/tools/android-tools-static/linux/android-tools-static/lpdump"
AVBTOOL = f"{WSL_ROOT}/tools/bootimg/avbtool.py"
BOOTIMG_PATH = f"{WSL_ROOT}/tools/bootimg"

DEVICE_SIZE = 9_126_805_504
ALIGNMENT = 1_048_576
SYSTEM_EXT_SIZE = 942_669_824
SALT = "c5ffc2c51fef1864ad27e6903e582f52611121819811b66eb40f6ea9b60350c5"
SYSTEM_EXT_UUID = "[REDACTED_DEVICE_ID]-9266-550f-9093-74a7abd8693f"
RULE = "(allow hal_graphics_allocator_default ion_device (chr_file (read)))"


def q(value: str) -> str:
    return shlex.quote(value)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def run_wsl(command: str) -> str:
    safe_print(f"[WSL] {command}")
    result = subprocess.run(
        ["wsl", "-d", "Ubuntu", "-e", "bash", "-lc", command],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    if result.stdout:
        safe_print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
    if result.stderr:
        safe_print(result.stderr, end="" if result.stderr.endswith("\n") else "\n")
    if result.returncode:
        raise RuntimeError(f"WSL command failed ({result.returncode})")
    return result.stdout


def safe_print(value: str, end: str = "\n") -> None:
    encoding = sys.stdout.encoding or "utf-8"
    printable = value.encode(encoding, errors="backslashreplace").decode(encoding, errors="strict")
    print(printable, end=end)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="resume only this interrupted C16 build if no final manifest exists",
    )
    args = parser.parse_args()
    required = (
        "boot.img",
        "vendor_boot.img",
        "dtbo.img",
        "vbmeta.img",
        "vbmeta_system.img",
        "super.img",
    )
    for name in required:
        if not (C15_IMAGES / name).is_file():
            raise FileNotFoundError(C15_IMAGES / name)
    if C16_DIR.exists():
        if not args.resume:
            raise FileExistsError(f"Refusing to overwrite existing C16 directory: {C16_DIR}; use --resume only for an incomplete build")
        if (C16_IMAGES / "BUILD_MANIFEST.json").exists():
            raise FileExistsError("A completed C16 manifest exists; refusing to rebuild or overwrite it.")
        for name in required:
            if not (C16_IMAGES / name).is_file() or sha256(C15_IMAGES / name) != sha256(C16_IMAGES / name):
                raise RuntimeError(f"Incomplete C16 output is not an untouched C15 copy: {name}; refusing resume")
    else:
        if args.resume:
            raise FileNotFoundError("--resume was requested but the C16 output directory does not exist")
        C16_DIR.mkdir(parents=True, exist_ok=False)
        C16_IMAGES.mkdir()
        for name in required:
            shutil.copy2(C15_IMAGES / name, C16_IMAGES / name)
            if sha256(C15_IMAGES / name) != sha256(C16_IMAGES / name):
                raise RuntimeError(f"C15 inheritance copy mismatch: {name}")

    c16_stage = q(WSL_C16_STAGE)
    c15_stage = q(WSL_C15_STAGE)
    c15_images = q(WSL_C15_IMAGES)
    c16_images = q(WSL_C16_IMAGES)
    setup = f"""
set -euo pipefail
test -f {c15_stage}/system_tree/system/build.prop
test -f {c15_stage}/system_ext_tree/etc/selinux/system_ext_sepolicy.cil
test -f {c15_stage}/system_c15.img
mkdir -p {c16_stage}
if ! test -d {c16_stage}/system_ext_tree; then
  cp -a {c15_stage}/system_ext_tree {c16_stage}/system_ext_tree
fi
cil={c16_stage}/system_ext_tree/etc/selinux/system_ext_sepolicy.cil
python3 - <<'PY'
from pathlib import Path
source = Path({WSL_C15_STAGE + '/system_ext_tree/etc/selinux/system_ext_sepolicy.cil'!r}).read_text(encoding='utf-8')
target = Path({WSL_C16_STAGE + '/system_ext_tree/etc/selinux/system_ext_sepolicy.cil'!r})
current = target.read_text(encoding='utf-8')
suffix = '\\n; Candidate 16: fix observed graphics allocator read denial on ion_device.\\n{RULE}\\n'
if current == source:
    target.write_text(source + suffix, encoding='utf-8', newline='\\n')
elif current != source + suffix:
    raise SystemExit('C16 policy tree differs from C15 by unexpected content; refusing resume')
assert target.read_text(encoding='utf-8').count('{RULE}') == 1
print('C16 policy delta is exactly one graphics allocator read rule.')
PY
test "$(grep -Fc {q(RULE)} "$cil")" = 1
grep -F 'allow hal_keymaster ion_device' "$cil"
grep -F 'allow hal_gatekeeper ion_device' "$cil"
grep -Fx {q(RULE)} "$cil"
test -f {c15_stage}/system_tree/system/lib64/libEGL_angle.so
test -f {c15_stage}/system_tree/system/lib64/libGLESv2_angle.so
grep -Fx 'persist.graphics.egl=angle' {c15_stage}/build.prop.c15.txt
"""
    run_wsl(setup)

    raw_ext = q(f"{WSL_C16_STAGE}/system_ext_c16.raw.erofs")
    avb_ext = q(f"{WSL_C16_STAGE}/system_ext_c16.img")
    ext_tree = q(f"{WSL_C16_STAGE}/system_ext_tree")
    configs = f"{WSL_C1_BASE}/configs_retained/system_ext"
    ext_fs_config = q(f"{configs}/fs_config")
    ext_file_contexts = q(f"{configs}/file_contexts")
    build_ext = f"""
set -euo pipefail
{q(MKFS)} -zlz4hc -T 0 -U {SYSTEM_EXT_UUID} --mount-point=/system_ext \\
  --fs-config-file={ext_fs_config} --file-contexts={ext_file_contexts} {raw_ext} {ext_tree} > {q(WSL_C16_STAGE + '/mkfs_system_ext_c16.log')} 2>&1
{q(FSCK)} -d0 {raw_ext} > {q(WSL_C16_STAGE + '/fsck_system_ext_c16.log')} 2>&1
{q(DUMP)} --cat --path=/etc/selinux/system_ext_sepolicy.cil {raw_ext} > {q(WSL_C16_STAGE + '/system_ext_sepolicy.c16.cil')}
grep -Fx {q(RULE)} {q(WSL_C16_STAGE + '/system_ext_sepolicy.c16.cil')}
grep -F 'allow hal_keymaster ion_device' {q(WSL_C16_STAGE + '/system_ext_sepolicy.c16.cil')}
grep -F 'allow hal_gatekeeper ion_device' {q(WSL_C16_STAGE + '/system_ext_sepolicy.c16.cil')}
{q(DUMP)} --cat --path=/etc/selinux/system_ext_file_contexts {raw_ext} | grep -F '/dev/ion' | grep -F 'ion_device:s0'
cp {raw_ext} {avb_ext}
python3 {q(AVBTOOL)} add_hashtree_footer --image {avb_ext} --partition_size {SYSTEM_EXT_SIZE} \\
  --partition_name system_ext --hash_algorithm sha256 --salt {SALT} --algorithm NONE --do_not_generate_fec
test "$(stat -c %s {avb_ext})" = {SYSTEM_EXT_SIZE}
"""
    run_wsl(build_ext)

    vbmeta_code = f"""
set -euo pipefail
PYTHONPATH={q(BOOTIMG_PATH)} python3 - <<'PY'
from pathlib import Path
from avbtool import Avb, ImageHandler, AvbHashtreeDescriptor

avb = Avb()
base = Path({WSL_C15_IMAGES + '/vbmeta_system.img'!r})
system_ext = Path({WSL_C16_STAGE + '/system_ext_c16.img'!r})
out = Path({WSL_C16_IMAGES + '/vbmeta_system.img'!r})
_, _, base_descs, _ = avb._parse_image(ImageHandler(str(base)))
_, _, ext_descs, _ = avb._parse_image(ImageHandler(str(system_ext)))
new_ext = next(x for x in ext_descs if isinstance(x, AvbHashtreeDescriptor) and x.partition_name == 'system_ext')
descs = [new_ext if isinstance(x, AvbHashtreeDescriptor) and x.partition_name == 'system_ext' else x for x in base_descs]
blob = avb._generate_vbmeta_blob(
    algorithm_name='NONE', key_path=None, public_key_metadata_path=None,
    descriptors=descs, chain_partitions_use_ab=None, chain_partitions_do_not_use_ab=None,
    rollback_index=0, flags=2, rollback_index_location=2, props=None,
    props_from_file=None, kernel_cmdlines=None, setup_rootfs_from_kernel=None,
    ht_desc_to_setup=None, include_descriptors_from_image=None, signing_helper=None,
    signing_helper_with_files=None, release_string=None, append_to_release_string=None,
    required_libavb_version_minor=0)
assert len(blob) <= 131072
out.write_bytes(blob + b'\\0' * (131072 - len(blob)))
_, _, check_descs, _ = avb._parse_image(ImageHandler(str(out)))
by_name = {{x.partition_name: x for x in check_descs if isinstance(x, AvbHashtreeDescriptor)}}
assert {{'product', 'system', 'system_ext'}} <= set(by_name)
assert by_name['system_ext'].root_digest == new_ext.root_digest
_, _, old_descs, _ = avb._parse_image(ImageHandler(str(base)))
old_by_name = {{x.partition_name: x for x in old_descs if isinstance(x, AvbHashtreeDescriptor)}}
assert by_name['system'].root_digest == old_by_name['system'].root_digest
assert by_name['product'].root_digest == old_by_name['product'].root_digest
for name in ('product', 'system', 'system_ext'):
    print(name, by_name[name].image_size, by_name[name].root_digest.hex())
PY
"""
    run_wsl(vbmeta_code)

    super_sparse = q(f"{WSL_C16_STAGE}/super_c16_sparse.img")
    super_raw = q(f"{WSL_C16_STAGE}/super_c16_raw.img")
    system_image = q(f"{WSL_C15_STAGE}/system_c15.img")
    lpmake = f"""
set -euo pipefail
{q(LPMAKE)} --metadata-size 65536 --metadata-slots 3 --device-size {DEVICE_SIZE} \\
  --block-size 4096 --alignment {ALIGNMENT} --virtual-ab --sparse --super-name super \\
  --group qti_dynamic_partitions_a:{DEVICE_SIZE} --group qti_dynamic_partitions_b:{DEVICE_SIZE} \\
  --partition mi_ext_a:readonly:202375168:qti_dynamic_partitions_a --partition mi_ext_b:none:0:qti_dynamic_partitions_b \\
  --partition odm_a:readonly:36700160:qti_dynamic_partitions_a --partition odm_b:none:0:qti_dynamic_partitions_b \\
  --partition product_a:readonly:4387241984:qti_dynamic_partitions_a --partition product_b:none:0:qti_dynamic_partitions_b \\
  --partition system_a:readonly:1092616192:qti_dynamic_partitions_a --partition system_b:none:0:qti_dynamic_partitions_b \\
  --partition system_ext_a:readonly:{SYSTEM_EXT_SIZE}:qti_dynamic_partitions_a --partition system_ext_b:none:0:qti_dynamic_partitions_b \\
  --partition vendor_a:readonly:1510998016:qti_dynamic_partitions_a --partition vendor_b:none:0:qti_dynamic_partitions_b \\
  --image mi_ext_a={q(WSL_C1_BASE + '/super/avb_images/mi_ext.img')} \\
  --image odm_a={q(WSL_C1_BASE + '/provider_images/odm.img')} \\
  --image product_a={q(WSL_C1_BASE + '/super/avb_images/product.img')} \\
  --image system_a={system_image} --image system_ext_a={avb_ext} \\
  --image vendor_a={q(WSL_C1_BASE + '/provider_images/vendor.img')} --output {super_sparse}
{q(SIMG2IMG)} {super_sparse} {super_raw}
{q(LPDUMP)} {super_raw} > {q(WSL_C16_STAGE + '/lpdump_c16.txt')}
grep -q 'system_a' {q(WSL_C16_STAGE + '/lpdump_c16.txt')}
grep -q 'system_ext_a' {q(WSL_C16_STAGE + '/lpdump_c16.txt')}
grep -q 'product_a' {q(WSL_C16_STAGE + '/lpdump_c16.txt')}
grep -q 'vendor_a' {q(WSL_C16_STAGE + '/lpdump_c16.txt')}
cp {super_sparse} {c16_images}/super.img
"""
    run_wsl(lpmake)

    manifest = {
        "candidate": "Candidate 16 graphics allocator ion_device read fix",
        "base": "Candidate 15 ANGLE EGL run1",
        "changes": [
            "system_ext/etc/selinux/system_ext_sepolicy.cil: allow hal_graphics_allocator_default to read ion_device, matching the exact C14/C15 AVC denial",
        ],
        "retained_from_c15": [
            "C14 BPF bootstrap bypass",
            "system/build.prop persist.graphics.egl=angle",
            "C13 Keymaster/Gatekeeper ion_device allow rules",
            "thyme boot/vendor_boot/dtbo/vbmeta and existing product/vendor/odm/mi_ext content",
        ],
        "flash_scope_prepared": ["vbmeta_system_a", "super"],
        "limits": [
            "C15 showed the graphics allocator AVC after the first SurfaceFlinger EGLConfig abort; the permission is a directly observed defect but is not yet proven to be the sole EGLConfig cause.",
            "C15 ANGLE runtime selection is not proven by pstore; the system property and ANGLE libraries are present in the built image.",
            "No device operation is performed by this script.",
        ],
        "images": {},
    }
    for path in sorted(C16_IMAGES.iterdir()):
        if path.is_file():
            manifest["images"][path.name] = {"bytes": path.stat().st_size, "sha256": sha256(path)}
    (C16_IMAGES / "BUILD_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
