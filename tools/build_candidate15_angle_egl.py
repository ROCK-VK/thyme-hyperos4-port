#!/usr/bin/env python3
"""Build a minimal C15 EGL-loader diagnostic variant from verified C14.

The only system-tree change is persist.graphics.egl=angle.  C14's BPF
bootstrap bypass and all target hardware partitions/configuration are retained.
This script performs host-side builds only and never calls adb or fastboot.
"""

from __future__ import annotations

import hashlib
import json
import shlex
import shutil
import subprocess
import sys
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
C14_IMAGES = ROOT / "work/stage_d_thyme_os4_candidate_14_bpf_bootstrap_bypass_run5/images"
C15_DIR = ROOT / "work/stage_e_thyme_os4_candidate_15_angle_egl_run1"
C15_IMAGES = C15_DIR / "images"

WSL_ROOT = "/path/to/thyme-os4-local"
WSL_C14_STAGE = "[LOCAL_WSL_USER]/c14_bpf_bootstrap_20260926_run5"
WSL_C15_STAGE = "[LOCAL_WSL_USER]/c15_angle_egl_20260926_run1"
WSL_C14_IMAGES = f"{WSL_ROOT}/work/stage_d_thyme_os4_candidate_14_bpf_bootstrap_bypass_run5/images"
WSL_C15_IMAGES = f"{WSL_ROOT}/work/stage_e_thyme_os4_candidate_15_angle_egl_run1/images"
WSL_C1_BASE = "[LOCAL_WSL_USER]/thyme_xiaomi15_os4_first_boot_candidate_1"

FSCK = f"{WSL_ROOT}/tools/erofs-utils/wsl/fsck.erofs"
DUMP = f"{WSL_ROOT}/tools/erofs-utils/wsl/dump.erofs"
MKFS = f"{WSL_ROOT}/tools/erofs-utils/wsl/mkfs.erofs"
LPMAKE = f"{WSL_ROOT}/tools/android-tools-static/linux/android-tools-static/lpmake"
SIMG2IMG = f"{WSL_ROOT}/tools/android-tools-static/linux/android-tools-static/simg2img"
LPDUMP = f"{WSL_ROOT}/tools/android-tools-static/linux/android-tools-static/lpdump"
AVBTOOL = f"{WSL_ROOT}/tools/bootimg/avbtool.py"

DEVICE_SIZE = 9_126_805_504
ALIGNMENT = 1_048_576
SYSTEM_PARTITION_SIZE = 1_092_616_192
SYSTEM_EXT_PARTITION_SIZE = 942_669_824
SALT = "c5ffc2c51fef1864ad27e6903e582f52611121819811b66eb40f6ea9b60350c5"
SYSTEM_UUID = "[REDACTED_DEVICE_ID]-8f73-4e28-aefe-8ee48d2d8b41"


def q(value: str) -> str:
    return shlex.quote(value)


def safe_print(value: str) -> None:
    try:
        print(value, end="" if value.endswith("\n") else "\n")
    except UnicodeEncodeError:
        encoding = sys.stdout.encoding or "utf-8"
        print(value.encode(encoding, errors="backslashreplace").decode(encoding, errors="replace"))


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
        safe_print(result.stdout)
    if result.stderr:
        safe_print(result.stderr)
    if result.returncode:
        raise RuntimeError(f"WSL command failed ({result.returncode}): {command}")
    return result.stdout


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resume", action="store_true", help="resume this exact incomplete C15 build after validating partial outputs")
    args = parser.parse_args()
    required = ("boot.img", "vendor_boot.img", "dtbo.img", "vbmeta.img", "vbmeta_system.img", "super.img")
    for name in required:
        if not (C14_IMAGES / name).is_file():
            raise FileNotFoundError(C14_IMAGES / name)

    if C15_DIR.exists():
        if not args.resume:
            raise FileExistsError(f"Refusing to overwrite existing Candidate 15 directory: {C15_DIR}; use --resume only for this interrupted build")
        for name in required:
            partial = C15_IMAGES / name
            if not partial.is_file() or sha256(partial) != sha256(C14_IMAGES / name):
                raise RuntimeError(f"Partial C15 output differs from the unchanged C14 seed: {name}; refusing resume")
    else:
        if args.resume:
            raise FileNotFoundError("--resume was requested but the Candidate 15 output directory does not exist")
        C15_DIR.mkdir(parents=True, exist_ok=False)
        C15_IMAGES.mkdir()
        for name in required:
            shutil.copy2(C14_IMAGES / name, C15_IMAGES / name)
            if sha256(C14_IMAGES / name) != sha256(C15_IMAGES / name):
                raise RuntimeError(f"C14 inheritance copy mismatch: {name}")

    stage = q(WSL_C15_STAGE)
    c14_stage = q(WSL_C14_STAGE)
    c15_images = q(WSL_C15_IMAGES)
    setup = f"""
set -euo pipefail
if test "{int(args.resume)}" = 1; then
  test -f {stage}/system_tree/system/build.prop
  test -f {stage}/system_ext_tree/etc/selinux/system_ext_sepolicy.cil
  test -f {stage}/system_fs_config_c15
  grep -Fx 'persist.graphics.egl=angle' {stage}/system_tree/system/build.prop
else
  test ! -e {stage}
  test -f {c14_stage}/system_tree/system/build.prop
  test -f {c14_stage}/system_ext_tree/etc/selinux/system_ext_sepolicy.cil
  test -f {c14_stage}/system_fs_config_c14
  mkdir -p {stage}
  cp -a {c14_stage}/system_tree {stage}/system_tree
  cp -a {c14_stage}/system_ext_tree {stage}/system_ext_tree
  cp {c14_stage}/system_fs_config_c14 {stage}/system_fs_config_c15
python3 - <<'PY'
from pathlib import Path

prop = Path({WSL_C15_STAGE!r}) / 'system_tree/system/build.prop'
text = prop.read_text(encoding='utf-8')
key = 'persist.graphics.egl='
assert key not in text, 'C14 unexpectedly already selects a persist.graphics.egl driver'
needle = 'persist.sys.force_sw_gles=1\\n'
assert text.count(needle) == 1, 'Unexpected C14 force_sw_gles property baseline'
text = text.replace(needle, needle + '# Candidate 15: exercise the Android 17 system ANGLE EGL implementation.\\n' + key + 'angle\\n')
prop.write_text(text, encoding='utf-8', newline='\\n')
assert text.count(key + 'angle') == 1
print('Added exactly one property: persist.graphics.egl=angle')
PY
fi
"""
    if not args.resume:
        run_wsl(setup)

    system_tree = q(f"{WSL_C15_STAGE}/system_tree")
    system_fs_config = q(f"{WSL_C15_STAGE}/system_fs_config_c15")
    system_contexts = q(f"{WSL_C1_BASE}/configs_retained/system/file_contexts")
    system_raw = q(f"{WSL_C15_STAGE}/system_c15.raw.erofs")
    system_image = q(f"{WSL_C15_STAGE}/system_c15.img")
    build_system = f"""
set -euo pipefail
if test "{int(args.resume)}" = 0 || ! test -f {system_image}; then
  {q(MKFS)} -zlz4hc -T 0 -U {SYSTEM_UUID} --mount-point=/system \\
    --fs-config-file={system_fs_config} --file-contexts={q(system_contexts)} {system_raw} {system_tree} > {q(WSL_C15_STAGE + '/mkfs_c15.log')} 2>&1
  {q(FSCK)} -d0 {system_raw} > {q(WSL_C15_STAGE + '/fsck_system_c15.log')} 2>&1
  cp {system_raw} {system_image}
  python3 {q(AVBTOOL)} add_hashtree_footer --image {system_image} --partition_size {SYSTEM_PARTITION_SIZE} \\
    --partition_name system --hash_algorithm sha256 --salt {SALT} --algorithm NONE --do_not_generate_fec
fi
{q(FSCK)} -d0 {system_raw} > {q(WSL_C15_STAGE + '/fsck_system_c15.log')} 2>&1
{q(DUMP)} --cat --path=/system/build.prop {system_raw} > {q(WSL_C15_STAGE + '/build.prop.c15.txt')}
grep -Fx 'persist.graphics.egl=angle' {q(WSL_C15_STAGE + '/build.prop.c15.txt')}
{q(DUMP)} --cat --path=/system/etc/init/netbpfload.rc {system_raw} > {q(WSL_C15_STAGE + '/netbpfload.c15.rc')}
grep -F 'setprop bpf.progs_loaded 1' {q(WSL_C15_STAGE + '/netbpfload.c15.rc')}
! grep -E 'exec_start bpfloader|wait_for_prop bpf.progs_loaded 1|exec_start netd1shot' {q(WSL_C15_STAGE + '/netbpfload.c15.rc')}
test "$(stat -c %s {system_image})" = {SYSTEM_PARTITION_SIZE}
"""
    if not args.resume or not (C15_DIR / "images" / "BUILD_MANIFEST.json").exists():
        run_wsl(build_system)

    vbmeta_code = f"""
set -euo pipefail
PYTHONPATH={q(WSL_ROOT + '/tools/bootimg')} python3 - <<'PY'
from pathlib import Path
from avbtool import Avb, ImageHandler, AvbHashtreeDescriptor

avb = Avb()
base = Path({WSL_C14_IMAGES + '/vbmeta_system.img'!r})
system = Path({WSL_C15_STAGE + '/system_c15.img'!r})
out = Path({WSL_C15_IMAGES + '/vbmeta_system.img'!r})
_, _, base_descs, _ = avb._parse_image(ImageHandler(str(base)))
_, _, system_descs, _ = avb._parse_image(ImageHandler(str(system)))
new_system = next(x for x in system_descs if isinstance(x, AvbHashtreeDescriptor) and x.partition_name == 'system')
old_system = next(x for x in base_descs if isinstance(x, AvbHashtreeDescriptor) and x.partition_name == 'system')
assert new_system.image_size == old_system.image_size
descs = [new_system if isinstance(x, AvbHashtreeDescriptor) and x.partition_name == 'system' else x for x in base_descs]
blob = avb._generate_vbmeta_blob(
    algorithm_name='NONE', key_path=None, public_key_metadata_path=None,
    descriptors=descs, chain_partitions_use_ab=None, chain_partitions_do_not_use_ab=None,
    rollback_index=0, flags=2, rollback_index_location=2, props=None, props_from_file=None,
    kernel_cmdlines=None, setup_rootfs_from_kernel=None, ht_desc_to_setup=None,
    include_descriptors_from_image=None, signing_helper=None, signing_helper_with_files=None,
    release_string=None, append_to_release_string=None, required_libavb_version_minor=0)
assert len(blob) <= 131072
out.write_bytes(blob + b'\\0' * (131072 - len(blob)))
_, _, check, _ = avb._parse_image(ImageHandler(str(out)))
descs = [x for x in check if isinstance(x, AvbHashtreeDescriptor)]
by_name = {{x.partition_name: x for x in descs}}
assert {{'product', 'system', 'system_ext'}} <= set(by_name)
assert by_name['system'].root_digest == new_system.root_digest
assert by_name['system_ext'].root_digest == next(x for x in base_descs if isinstance(x, AvbHashtreeDescriptor) and x.partition_name == 'system_ext').root_digest
print('C15 vbmeta_system descriptors verified; only system digest changed from C14.')
for name in ('product', 'system', 'system_ext'):
    print(name, by_name[name].image_size, by_name[name].root_digest.hex())
PY
"""
    run_wsl(vbmeta_code)

    super_sparse = q(f"{WSL_C15_STAGE}/super_c15_sparse.img")
    super_raw = q(f"{WSL_C15_STAGE}/super_c15_raw.img")
    system_ext_image = q(f"{WSL_C14_STAGE}/system_ext_c14.img")
    super_build = f"""
set -euo pipefail
{q(LPMAKE)} --metadata-size 65536 --metadata-slots 3 --device-size {DEVICE_SIZE} \\
  --block-size 4096 --alignment {ALIGNMENT} --virtual-ab --sparse --super-name super \\
  --group qti_dynamic_partitions_a:{DEVICE_SIZE} --group qti_dynamic_partitions_b:{DEVICE_SIZE} \\
  --partition mi_ext_a:readonly:202375168:qti_dynamic_partitions_a --partition mi_ext_b:none:0:qti_dynamic_partitions_b \\
  --partition odm_a:readonly:[REDACTED_DEVICE_ID]:qti_dynamic_partitions_a --partition odm_b:none:0:qti_dynamic_partitions_b \\
  --partition product_a:readonly:4387241984:qti_dynamic_partitions_a --partition product_b:none:0:qti_dynamic_partitions_b \\
  --partition system_a:readonly:1092616192:qti_dynamic_partitions_a --partition system_b:none:0:qti_dynamic_partitions_b \\
  --partition system_ext_a:readonly:942669824:qti_dynamic_partitions_a --partition system_ext_b:none:0:qti_dynamic_partitions_b \\
  --partition vendor_a:readonly:1510998016:qti_dynamic_partitions_a --partition vendor_b:none:0:qti_dynamic_partitions_b \\
  --image mi_ext_a={q(WSL_C1_BASE + '/super/avb_images/mi_ext.img')} \\
  --image odm_a={q(WSL_C1_BASE + '/provider_images/odm.img')} \\
  --image product_a={q(WSL_C1_BASE + '/super/avb_images/product.img')} \\
  --image system_a={system_image} --image system_ext_a={system_ext_image} \\
  --image vendor_a={q(WSL_C1_BASE + '/provider_images/vendor.img')} --output {super_sparse}
{q(SIMG2IMG)} {super_sparse} {super_raw}
{q(LPDUMP)} {super_raw} > {q(WSL_C15_STAGE + '/lpdump_c15.txt')}
grep -q 'system_a' {q(WSL_C15_STAGE + '/lpdump_c15.txt')}
grep -q 'system_ext_a' {q(WSL_C15_STAGE + '/lpdump_c15.txt')}
grep -q 'vendor_a' {q(WSL_C15_STAGE + '/lpdump_c15.txt')}
cp {super_sparse} {c15_images}/super.img
"""
    run_wsl(super_build)

    manifest = {
        "candidate": "Candidate 15 ANGLE EGL diagnostic",
        "base": "Candidate 14 BPF bootstrap bypass run5",
        "changes": [
            "system/build.prop: add persist.graphics.egl=angle to select the Android 17 system ANGLE EGL implementation",
        ],
        "retained_from_c14": [
            "C14 BPF bootstrap bypass",
            "C13 SELinux policy, fstab, APEX and encryption configuration",
            "thyme boot, vendor_boot, dtbo, vbmeta and vendor/odm/product/mi_ext logical partitions",
        ],
        "flash_scope_prepared": ["vbmeta_system_a", "super"],
        "diagnostic_limits": [
            "ANGLE may depend on the current Vulkan driver; graphicsengine had a separate Vulkan-related crash in C14, so EGL recovery is unverified.",
            "This is a host-built experiment only; no device write or boot was performed by this script.",
        ],
        "images": {},
    }
    for path in sorted(C15_IMAGES.iterdir()):
        if path.is_file() and path.name != "BUILD_MANIFEST.json":
            manifest["images"][path.name] = {"bytes": path.stat().st_size, "sha256": sha256(path)}
    if sorted(manifest["images"]) != sorted(required):
        raise RuntimeError("Candidate 15 image set is incomplete or unexpected")
    (C15_IMAGES / "BUILD_MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
