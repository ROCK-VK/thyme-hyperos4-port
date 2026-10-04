#!/usr/bin/env python3
"""Build Candidate 17 by adding only the observed graphics allocator open permission.

Input is the already-built C16 image and cached C16/C15 logical image inputs.
This script is host-side only; it never calls adb or fastboot.
"""

from __future__ import annotations

import hashlib
import json
import shlex
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
C16_DIR = ROOT / "work/stage_f_thyme_os4_candidate_16_graphics_allocator_ion_run1"
C16_IMAGES = C16_DIR / "images"
C17_DIR = ROOT / "work/stage_g_thyme_os4_candidate_17_graphics_allocator_open_run1"
C17_IMAGES = C17_DIR / "images"

WSL_ROOT = "/path/to/thyme-os4-local"
WSL_C1_BASE = "/path/to/thyme-os4-build/thyme_xiaomi15_os4_first_boot_candidate_1"
WSL_C15_STAGE = "/path/to/thyme-os4-build/c15_angle_egl_20260926_run1"
WSL_C16_STAGE = "/path/to/thyme-os4-build/c16_graphics_allocator_ion_20260926_run1"
WSL_C17_STAGE = "/path/to/thyme-os4-build/c17_graphics_allocator_open_20260926_run1"
WSL_C16_IMAGES = f"{WSL_ROOT}/work/stage_f_thyme_os4_candidate_16_graphics_allocator_ion_run1/images"
WSL_C17_IMAGES = f"{WSL_ROOT}/work/stage_g_thyme_os4_candidate_17_graphics_allocator_open_run1/images"

TOOLS = f"{WSL_ROOT}/tools"
MKFS = f"{TOOLS}/erofs-utils/wsl/mkfs.erofs"
FSCK = f"{TOOLS}/erofs-utils/wsl/fsck.erofs"
DUMP = f"{TOOLS}/erofs-utils/wsl/dump.erofs"
LPMAKE = f"{TOOLS}/android-tools-static/linux/android-tools-static/lpmake"
SIMG2IMG = f"{TOOLS}/android-tools-static/linux/android-tools-static/simg2img"
LPDUMP = f"{TOOLS}/android-tools-static/linux/android-tools-static/lpdump"
AVBTOOL = f"{TOOLS}/bootimg/avbtool.py"
BOOTIMG_PATH = f"{TOOLS}/bootimg"

DEVICE_SIZE = 9_126_805_504
ALIGNMENT = 1_048_576
SYSTEM_EXT_SIZE = 942_669_824
SALT = "c5ffc2c51fef1864ad27e6903e582f52611121819811b66eb40f6ea9b60350c5"
SYSTEM_EXT_UUID = "[REDACTED_DEVICE_ID]-9266-550f-9093-74a7abd8693f"
C16_RULE = "(allow hal_graphics_allocator_default ion_device (chr_file (read)))"
C17_RULE = "(allow hal_graphics_allocator_default ion_device (chr_file (open read)))"


def q(value: str) -> str:
    return shlex.quote(value)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def safe_print(value: str, end: str = "\n") -> None:
    encoding = sys.stdout.encoding or "utf-8"
    print(value.encode(encoding, errors="backslashreplace").decode(encoding), end=end)


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


def main() -> None:
    required = ("boot.img", "vendor_boot.img", "dtbo.img", "vbmeta.img", "vbmeta_system.img", "super.img")
    source_manifest_path = C16_IMAGES / "BUILD_MANIFEST.json"
    if not source_manifest_path.is_file():
        raise FileNotFoundError(source_manifest_path)
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    if source_manifest.get("candidate") != "Candidate 16 graphics allocator ion_device read fix":
        raise RuntimeError("Source manifest is not the expected C16 build.")
    for name in required:
        source = C16_IMAGES / name
        if not source.is_file():
            raise FileNotFoundError(source)
        expected = source_manifest["images"][name]
        if source.stat().st_size != expected["bytes"] or sha256(source) != expected["sha256"]:
            raise RuntimeError(f"C16 source image does not match its manifest: {name}")

    if C17_DIR.exists():
        if (C17_IMAGES / "BUILD_MANIFEST.json").exists():
            raise FileExistsError(f"A completed C17 build already exists: {C17_IMAGES}")
        if not C17_IMAGES.is_dir():
            raise FileNotFoundError(f"Incomplete C17 output directory is missing: {C17_IMAGES}")
        for name in required:
            output = C17_IMAGES / name
            if output.exists() and sha256(output) != sha256(C16_IMAGES / name):
                raise RuntimeError(f"Incomplete C17 output contains an unexpected image; refusing resume: {name}")
    else:
        C17_DIR.mkdir(parents=True, exist_ok=False)
        C17_IMAGES.mkdir()
    for name in required:
        if not (C17_IMAGES / name).exists():
            shutil.copy2(C16_IMAGES / name, C17_IMAGES / name)
        if sha256(C16_IMAGES / name) != sha256(C17_IMAGES / name):
            raise RuntimeError(f"C16-to-C17 inheritance copy mismatch: {name}")

    c16_tree = f"{WSL_C16_STAGE}/system_ext_tree"
    c17_tree = f"{WSL_C17_STAGE}/system_ext_tree"
    c16_cil = f"{c16_tree}/etc/selinux/system_ext_sepolicy.cil"
    c17_cil = f"{c17_tree}/etc/selinux/system_ext_sepolicy.cil"
    c17_raw = f"{WSL_C17_STAGE}/system_ext_c17.raw.erofs"
    c17_ext = f"{WSL_C17_STAGE}/system_ext_c17.img"
    c17_vbmeta = f"{WSL_C17_IMAGES}/vbmeta_system.img"
    c17_sparse = f"{WSL_C17_STAGE}/super_c17_sparse.img"
    c17_raw_super = f"{WSL_C17_STAGE}/super_c17_raw.img"

    setup = f"""
set -euo pipefail
test -f {q(c16_cil)}
test -d {q(c16_tree)}
mkdir -p {q(WSL_C17_STAGE)}
if ! test -e {q(c17_tree)}; then cp -a {q(c16_tree)} {q(c17_tree)}; fi
python3 - <<'PY'
from pathlib import Path
source_rule = {C16_RULE!r}
target_rule = {C17_RULE!r}
path = Path({c17_cil!r})
text = path.read_text(encoding='utf-8')
if text.count(target_rule) == 1 and source_rule not in text:
    print('C17 policy delta already present; continuing this incomplete build.')
elif text.count(source_rule) == 1 and target_rule not in text:
    text = text.replace(source_rule, target_rule, 1)
    comment = '; Candidate 16: fix observed graphics allocator read denial on ion_device.'
    if comment in text:
        text = text.replace(comment, '; Candidate 17: retain C16 read access and add observed ion_device open access.', 1)
    path.write_text(text, encoding='utf-8', newline='\\n')
else:
    raise SystemExit('C17 tree has an unexpected C16/C17 SELinux rule state; refusing policy rewrite')
assert path.read_text(encoding='utf-8').count(target_rule) == 1
print('C17 delta is exactly read -> open read for hal_graphics_allocator_default on ion_device.')
PY
test "$(grep -Fc {q(C17_RULE)} {q(c17_cil)})" = 1
grep -F 'allow hal_keymaster ion_device' {q(c17_cil)}
grep -F 'allow hal_gatekeeper ion_device' {q(c17_cil)}
"""
    run_wsl(setup)

    # Compile the actual active CIL set with the C17 system_ext input and assert
    # the runtime-observed HAL domain's exact permissions. -N is retained from
    # the project's existing host check and disables neverallow checking.
    policy_test = f"{WSL_C17_STAGE}/policy_test"
    policy_cils = f"""
set -euo pipefail
sys=/path/to/thyme-os4-build/thyme_xiaomi15_os4_first_boot_candidate_1/rootlike_stage/system/etc/selinux
prod=/path/to/thyme-os4-build/thyme_native_base_1/selinux_migration_1/inputs/product/etc/selinux
audit=/path/to/thyme-os4-build/c13_audit
ext={q(c17_tree)}/etc/selinux
mkdir -p {q(WSL_C17_STAGE + '/policy_test')}
python3 - <<'PY'
from pathlib import Path
src = Path('/path/to/thyme-os4-build/thyme_xiaomi15_os4_first_boot_candidate_1/rootlike_stage/system/etc/selinux/plat_sepolicy.cil')
dst = Path({(WSL_C17_STAGE + '/policy_test/plat_sepolicy.cil')!r})
text = src.read_text(encoding='utf-8')
dst.write_text(text.replace('(policycap functionfs_seclabel)', '; (policycap functionfs_seclabel)'), encoding='utf-8')
PY
test -f "$sys/plat_sepolicy.cil"
test -f "$sys/mapping/202604.cil"
test -f "$sys/plat_sepolicy_genfs_202604.cil"
test -f "$ext/system_ext_sepolicy.cil"
test -f "$ext/mapping/202604.cil"
test -f "$prod/product_sepolicy.cil"
test -f "$prod/mapping/202604.cil"
test -f "$audit/plat_pub_versioned.cil"
test -f "$audit/vendor_sepolicy.cil"
test -f "$audit/odm_sepolicy.cil"
secilc -m -M true -G -c 30 -N \\
  {q(WSL_C17_STAGE + '/policy_test/plat_sepolicy.cil')} \\
  "$sys/mapping/202604.cil" "$sys/plat_sepolicy_genfs_202604.cil" \\
  "$ext/system_ext_sepolicy.cil" "$ext/mapping/202604.cil" \\
  "$prod/product_sepolicy.cil" "$prod/mapping/202604.cil" \\
  "$audit/plat_pub_versioned.cil" "$audit/vendor_sepolicy.cil" "$audit/odm_sepolicy.cil" \\
  -o {q(policy_test + '/sepolicy')} -f /dev/null
sesearch -A -s hal_graphics_allocator_default -t ion_device -c chr_file {q(policy_test + '/sepolicy')} | tee {q(policy_test + '/graphics_allocator_ion_device.txt')}
grep -q 'open' {q(policy_test + '/graphics_allocator_ion_device.txt')}
grep -q 'read' {q(policy_test + '/graphics_allocator_ion_device.txt')}
"""
    run_wsl(policy_cils)

    c17_ext_fs = f"""
set -euo pipefail
{q(MKFS)} -zlz4hc -T 0 -U {SYSTEM_EXT_UUID} --mount-point=/system_ext \\
  --fs-config-file={q(WSL_C1_BASE + '/configs_retained/system_ext/fs_config')} \\
  --file-contexts={q(WSL_C1_BASE + '/configs_retained/system_ext/file_contexts')} \\
  {q(c17_raw)} {q(c17_tree)} > {q(WSL_C17_STAGE + '/mkfs_system_ext_c17.log')} 2>&1
{q(FSCK)} -d0 {q(c17_raw)} > {q(WSL_C17_STAGE + '/fsck_system_ext_c17.log')} 2>&1
{q(DUMP)} --cat --path=/etc/selinux/system_ext_sepolicy.cil {q(c17_raw)} > {q(WSL_C17_STAGE + '/system_ext_sepolicy.c17.cil')}
grep -Fx {q(C17_RULE)} {q(WSL_C17_STAGE + '/system_ext_sepolicy.c17.cil')}
grep -F 'allow hal_keymaster ion_device' {q(WSL_C17_STAGE + '/system_ext_sepolicy.c17.cil')}
grep -F 'allow hal_gatekeeper ion_device' {q(WSL_C17_STAGE + '/system_ext_sepolicy.c17.cil')}
{q(DUMP)} --cat --path=/etc/selinux/system_ext_file_contexts {q(c17_raw)} | grep -F '/dev/ion' | grep -F 'ion_device:s0'
cp {q(c17_raw)} {q(c17_ext)}
python3 {q(AVBTOOL)} add_hashtree_footer --image {q(c17_ext)} --partition_size {SYSTEM_EXT_SIZE} \\
  --partition_name system_ext --hash_algorithm sha256 --salt {SALT} --algorithm NONE --do_not_generate_fec
test "$(stat -c %s {q(c17_ext)})" = {SYSTEM_EXT_SIZE}
"""
    run_wsl(c17_ext_fs)

    vbmeta_code = f"""
set -euo pipefail
PYTHONPATH={q(BOOTIMG_PATH)} python3 - <<'PY'
from pathlib import Path
from avbtool import Avb, ImageHandler, AvbHashtreeDescriptor

avb = Avb()
base = Path({WSL_C16_IMAGES + '/vbmeta_system.img'!r})
system_ext = Path({c17_ext!r})
out = Path({c17_vbmeta!r})
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
for name in ('product', 'system'):
    assert by_name[name].root_digest == old_by_name[name].root_digest
    assert by_name[name].image_size == old_by_name[name].image_size
for name in ('product', 'system', 'system_ext'):
    print(name, by_name[name].image_size, by_name[name].root_digest.hex())
PY
"""
    run_wsl(vbmeta_code)

    super_build = f"""
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
  --image system_a={q(WSL_C15_STAGE + '/system_c15.img')} --image system_ext_a={q(c17_ext)} \\
  --image vendor_a={q(WSL_C1_BASE + '/provider_images/vendor.img')} --output {q(c17_sparse)}
{q(SIMG2IMG)} {q(c17_sparse)} {q(c17_raw_super)}
{q(LPDUMP)} {q(c17_raw_super)} > {q(WSL_C17_STAGE + '/lpdump_c17.txt')}
for name in mi_ext_a odm_a product_a system_a system_ext_a vendor_a; do grep -q "$name" {q(WSL_C17_STAGE + '/lpdump_c17.txt')}; done
cp {q(c17_sparse)} {q(WSL_C17_IMAGES + '/super.img')}
"""
    run_wsl(super_build)

    manifest = {
        "candidate": "Candidate 17 graphics allocator ion_device open fix",
        "base": "Candidate 16 graphics allocator ion_device read fix",
        "changes": [
            "system_ext/etc/selinux/system_ext_sepolicy.cil: retain hal_graphics_allocator_default read access and add only open on ion_device, matching the C16 enforcing AVC that precedes the first EGLConfig abort",
        ],
        "retained_from_c16": [
            "C14 BPF bootstrap bypass",
            "system/build.prop persist.graphics.egl=angle and system ANGLE libraries",
            "C13 Keymaster/Gatekeeper ion_device rules",
            "C16 hal_graphics_allocator_default ion_device read permission",
            "thyme boot/vendor_boot/dtbo/vbmeta and existing product/vendor/odm/mi_ext content",
        ],
        "flash_scope_prepared": ["vbmeta_system_a", "super"],
        "limits": [
            "C16 still had 31 SurfaceFlinger EGLConfig aborts and one graphicsengine SIGSEGV in vkEnumeratePhysicalDevices; this single SELinux change does not prove either is its sole cause.",
            "C16 runtime ANGLE selection was not directly logged. Android 17 EGL's Android META-EGL strings are wrapper strings, not driver identity.",
            "The host secilc assertion uses -N, matching the existing project check; this disables neverallow checking.",
            "No device operation is performed by the build script.",
        ],
        "images": {},
    }
    for path in sorted(C17_IMAGES.iterdir()):
        if path.is_file():
            manifest["images"][path.name] = {"bytes": path.stat().st_size, "sha256": sha256(path)}
    if set(manifest["images"]) != set(required):
        raise RuntimeError(f"Unexpected C17 image set: {sorted(manifest['images'])}")
    (C17_IMAGES / "BUILD_MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    safe_print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
