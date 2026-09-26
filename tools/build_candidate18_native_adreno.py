#!/usr/bin/env python3
"""Build C18 to route EGL through thyme's native Adreno vendor driver.

The source is the already-tested C17 image set. The only runtime change is the
system EGL driver route: persist.graphics.egl becomes the target vendor's
ro.hardware.egl value (adreno). A property trigger reapplies it after Android
loads /data persistent properties, so an old ANGLE value cannot silently win.
This script performs host-side builds only and never calls adb or fastboot.
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
C17_IMAGES = ROOT / "work/stage_g_thyme_os4_candidate_17_graphics_allocator_open_run1/images"
C18_DIR = ROOT / "work/stage_h_thyme_os4_candidate_18_native_adreno_run1"
C18_IMAGES = C18_DIR / "images"

if ROOT.drive:
    WSL_ROOT = f"/mnt/{ROOT.drive[0].lower()}/{ROOT.as_posix()[3:]}"
else:
    WSL_ROOT = ROOT.as_posix()
WSL_BUILD_ROOT = "[LOCAL_WSL_USER]
WSL_C1_BASE = f"{WSL_BUILD_ROOT}/thyme_xiaomi15_os4_first_boot_candidate_1"
WSL_C15_STAGE = f"{WSL_BUILD_ROOT}/c15_angle_egl_20260926_run1"
WSL_C17_STAGE = f"{WSL_BUILD_ROOT}/c17_graphics_allocator_open_20260926_run1"
WSL_C18_STAGE = f"{WSL_BUILD_ROOT}/c18_native_adreno_egl_20260926_run1"
WSL_C17_IMAGES = f"{WSL_ROOT}/work/stage_g_thyme_os4_candidate_17_graphics_allocator_open_run1/images"
WSL_C18_IMAGES = f"{WSL_ROOT}/work/stage_h_thyme_os4_candidate_18_native_adreno_run1/images"

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
SYSTEM_PARTITION_SIZE = 1_092_616_192
SYSTEM_EXT_PARTITION_SIZE = 942_669_824
SALT = "c5ffc2c51fef1864ad27e6903e582f52611121819811b66eb40f6ea9b60350c5"
SYSTEM_UUID = "[REDACTED_DEVICE_ID]-8f73-4e28-aefe-8ee48d2d8b41"
REQUIRED_IMAGES = ("boot.img", "vendor_boot.img", "dtbo.img", "vbmeta.img", "vbmeta_system.img", "super.img")
SOURCE_CANDIDATE = "Candidate 17 graphics allocator ion_device open fix"
CANDIDATE = "Candidate 18 native Adreno EGL selection"


def q(value: str) -> str:
    return shlex.quote(value)


def safe_print(value: str) -> None:
    try:
        print(value, end="" if value.endswith("\n") else "\n")
    except UnicodeEncodeError:
        encoding = sys.stdout.encoding or "utf-8"
        print(value.encode(encoding, errors="backslashreplace").decode(encoding, errors="replace"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def run_wsl(command: str) -> str:
    result = subprocess.run(
        ["wsl.exe", "-d", "Ubuntu", "--", "bash", "-lc", command],
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
        raise subprocess.CalledProcessError(result.returncode, command, result.stdout, result.stderr)
    return result.stdout


def main() -> None:
    resume = sys.argv[1:] == ["--resume"]
    if len(sys.argv) > 1 and not resume:
        raise SystemExit("Usage: build_candidate18_native_adreno.py [--resume]")
    source_manifest_path = C17_IMAGES / "BUILD_MANIFEST.json"
    if not source_manifest_path.is_file():
        raise FileNotFoundError(source_manifest_path)
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    if source_manifest.get("candidate") != SOURCE_CANDIDATE:
        raise RuntimeError("Source manifest is not the expected C17 build.")
    source_names = set(source_manifest.get("images", {}))
    if source_names != set(REQUIRED_IMAGES):
        raise RuntimeError(f"C17 manifest has an unexpected image set: {sorted(source_names)}")
    for name in REQUIRED_IMAGES:
        source = C17_IMAGES / name
        if not source.is_file():
            raise FileNotFoundError(source)
        if source.stat().st_size != int(source_manifest["images"][name]["bytes"]):
            raise RuntimeError(f"C17 image size differs from its existing manifest: {name}")
    if C18_DIR.exists() and not resume:
        raise FileExistsError(f"Refusing to overwrite an existing C18 directory: {C18_DIR}")
    if not C18_DIR.exists():
        C18_DIR.mkdir(parents=True, exist_ok=False)
    C18_IMAGES.mkdir(exist_ok=True)
    for name in REQUIRED_IMAGES:
        destination = C18_IMAGES / name
        source = C17_IMAGES / name
        if destination.exists():
            if destination.stat().st_size != source_manifest["images"][name]["bytes"]:
                raise RuntimeError(f"Existing C18 staging image has an unexpected size: {destination}")
            if sha256(destination) != source_manifest["images"][name]["sha256"].upper():
                raise RuntimeError(f"Existing C18 staging image is neither untouched C17 nor safe to resume: {destination}")
        else:
            shutil.copy2(source, destination)

    wsl_stage = q(WSL_C18_STAGE)
    wsl_system_tree = q(f"{WSL_C18_STAGE}/system_tree")
    wsl_source_system_tree = q(f"{WSL_C15_STAGE}/system_tree")
    wsl_vendor = q(f"{WSL_C1_BASE}/provider_images/vendor.img")

    setup = f"""
set -euo pipefail
if test -e {wsl_stage} && [ {1 if resume else 0} -ne 1 ]; then
  echo 'C18 WSL stage already exists; refusing to overwrite it without --resume.' >&2
  exit 2
fi
test -f {wsl_source_system_tree}/system/build.prop
test -f {wsl_source_system_tree}/system/etc/init/surfaceflinger.rc
mkdir -p {wsl_stage}
if [ ! -d {wsl_system_tree} ]; then
  cp -a {wsl_source_system_tree} {wsl_system_tree}
fi
debugfs -R 'cat /build.prop' {wsl_vendor} 2>/dev/null | grep -Fx 'ro.hardware.egl=adreno'
debugfs -R 'cat /build.prop' {wsl_vendor} 2>/dev/null | grep -Fx 'ro.hardware.vulkan=adreno'
debugfs -R 'ls -l /lib64/egl' {wsl_vendor} 2>/dev/null | grep -F 'libEGL_adreno.so'
debugfs -R 'ls -l /lib64/egl' {wsl_vendor} 2>/dev/null | grep -F 'libGLESv2_adreno.so'
python3 - <<'PY'
from pathlib import Path

prop = Path({(WSL_C18_STAGE + '/system_tree/system/build.prop')!r})
old_comment = '# Candidate 15: exercise the Android 17 system ANGLE EGL implementation.\\n'
old_property = 'persist.graphics.egl=angle\\n'
new_comment = '# Candidate 18: use thyme native EGL matching vendor ro.hardware.egl=adreno.\\n'
new_property = 'persist.graphics.egl=adreno\\n'
text = prop.read_text(encoding='utf-8')
old_block = old_comment + old_property
if text.count(old_block) == 1:
    text = text.replace(old_block, new_comment + new_property, 1)
elif text.count(new_comment + new_property) != 1:
    raise AssertionError('Expected one C15 ANGLE block or one already-applied C18 native block.')
prop.write_text(text, encoding='utf-8', newline='\\n')
assert text.count(new_property) == 1
assert 'persist.graphics.egl=angle' not in text

rc = Path({(WSL_C18_STAGE + '/system_tree/system/etc/init/surfaceflinger.rc')!r})
rc_text = rc.read_text(encoding='utf-8')
trigger = (
    '# Candidate 18: reapply the target-native EGL route after /data properties load.\\n'
    'on property:ro.persistent_properties.ready=true\\n'
    '    setprop persist.graphics.egl adreno\\n\\n'
)
trigger_count = rc_text.count('on property:ro.persistent_properties.ready=true')
setprop_count = rc_text.count('setprop persist.graphics.egl adreno')
if trigger_count == 0 and setprop_count == 0:
    rc_text = trigger + rc_text
else:
    assert trigger_count == 1 and setprop_count == 1, 'Unexpected partial or duplicate C18 init trigger.'
rc.write_text(rc_text, encoding='utf-8', newline='\\n')
assert rc.read_text(encoding='utf-8').count('on property:ro.persistent_properties.ready=true') == 1
assert '    setprop persist.graphics.egl adreno\\n' in rc.read_text(encoding='utf-8')

contexts = Path({(WSL_C18_STAGE + '/system_tree/system/etc/selinux/plat_property_contexts')!r}).read_text(encoding='utf-8')
assert 'persist.graphics.egl' in contexts and 'graphics_config_writable_prop' in contexts
print('C18 changes are limited to native Adreno EGL routing and its post-persistent-properties override.')
PY
"""
    run_wsl(setup)

    system_tree = q(f"{WSL_C18_STAGE}/system_tree")
    system_fs_config = q(f"{WSL_C15_STAGE}/system_fs_config_c15")
    system_contexts = q(f"{WSL_C1_BASE}/configs_retained/system/file_contexts")
    system_raw = q(f"{WSL_C18_STAGE}/system_c18.raw.erofs")
    system_image = q(f"{WSL_C18_STAGE}/system_c18.img")
    build_system = f"""
set -euo pipefail
{q(MKFS)} -zlz4hc -T 0 -U {SYSTEM_UUID} --mount-point=/system \\
  --fs-config-file={system_fs_config} --file-contexts={system_contexts} {system_raw} {system_tree} \\
  > {q(WSL_C18_STAGE + '/mkfs_system_c18.log')} 2>&1
{q(FSCK)} -d0 {system_raw} > {q(WSL_C18_STAGE + '/fsck_system_c18.log')} 2>&1
cp {system_raw} {system_image}
python3 {q(AVBTOOL)} add_hashtree_footer --image {system_image} --partition_size {SYSTEM_PARTITION_SIZE} \\
  --partition_name system --hash_algorithm sha256 --salt {SALT} --algorithm NONE --do_not_generate_fec
{q(FSCK)} -d0 {system_raw} > {q(WSL_C18_STAGE + '/fsck_system_c18.log')} 2>&1
{q(DUMP)} --cat --path=/system/build.prop {system_raw} > {q(WSL_C18_STAGE + '/build.prop.c18.txt')}
grep -Fx 'persist.graphics.egl=adreno' {q(WSL_C18_STAGE + '/build.prop.c18.txt')}
! grep -Fx 'persist.graphics.egl=angle' {q(WSL_C18_STAGE + '/build.prop.c18.txt')}
{q(DUMP)} --cat --path=/system/etc/init/surfaceflinger.rc {system_raw} > {q(WSL_C18_STAGE + '/surfaceflinger.c18.rc')}
grep -Fx 'on property:ro.persistent_properties.ready=true' {q(WSL_C18_STAGE + '/surfaceflinger.c18.rc')}
grep -Fx '    setprop persist.graphics.egl adreno' {q(WSL_C18_STAGE + '/surfaceflinger.c18.rc')}
python3 - <<'PY'
from pathlib import Path
image = Path({(WSL_C18_STAGE + '/system_c18.img')!r})
assert image.stat().st_size == {SYSTEM_PARTITION_SIZE}, image.stat().st_size
PY
"""
    run_wsl(build_system)

    vbmeta_code = f"""
set -euo pipefail
PYTHONPATH={q(BOOTIMG_PATH)} python3 - <<'PY'
from pathlib import Path
from avbtool import Avb, ImageHandler, AvbHashtreeDescriptor

avb = Avb()
base = Path({(WSL_C17_IMAGES + '/vbmeta_system.img')!r})
system = Path({(WSL_C18_STAGE + '/system_c18.img')!r})
out = Path({(WSL_C18_IMAGES + '/vbmeta_system.img')!r})
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
_, _, check_descs, _ = avb._parse_image(ImageHandler(str(out)))
by_name = {{x.partition_name: x for x in check_descs if isinstance(x, AvbHashtreeDescriptor)}}
old_by_name = {{x.partition_name: x for x in base_descs if isinstance(x, AvbHashtreeDescriptor)}}
assert {{'product', 'system', 'system_ext'}} <= set(by_name)
assert by_name['system'].root_digest == new_system.root_digest
for name in ('product', 'system_ext'):
    assert by_name[name].root_digest == old_by_name[name].root_digest
    assert by_name[name].image_size == old_by_name[name].image_size
for name in ('product', 'system', 'system_ext'):
    print(name, by_name[name].image_size, by_name[name].root_digest.hex())
PY
"""
    run_wsl(vbmeta_code)

    c18_sparse = q(f"{WSL_C18_STAGE}/super_c18_sparse.img")
    c18_raw_super = q(f"{WSL_C18_STAGE}/super_c18_raw.img")
    super_build = f"""
set -euo pipefail
{q(LPMAKE)} --metadata-size 65536 --metadata-slots 3 --device-size {DEVICE_SIZE} \\
  --block-size 4096 --alignment {ALIGNMENT} --virtual-ab --sparse --super-name super \\
  --group qti_dynamic_partitions_a:{DEVICE_SIZE} --group qti_dynamic_partitions_b:{DEVICE_SIZE} \\
  --partition mi_ext_a:readonly:202375168:qti_dynamic_partitions_a --partition mi_ext_b:none:0:qti_dynamic_partitions_b \\
  --partition odm_a:readonly:36700160:qti_dynamic_partitions_a --partition odm_b:none:0:qti_dynamic_partitions_b \\
  --partition product_a:readonly:4387241984:qti_dynamic_partitions_a --partition product_b:none:0:qti_dynamic_partitions_b \\
  --partition system_a:readonly:{SYSTEM_PARTITION_SIZE}:qti_dynamic_partitions_a --partition system_b:none:0:qti_dynamic_partitions_b \\
  --partition system_ext_a:readonly:{SYSTEM_EXT_PARTITION_SIZE}:qti_dynamic_partitions_a --partition system_ext_b:none:0:qti_dynamic_partitions_b \\
  --partition vendor_a:readonly:1510998016:qti_dynamic_partitions_a --partition vendor_b:none:0:qti_dynamic_partitions_b \\
  --image mi_ext_a={q(WSL_C1_BASE + '/super/avb_images/mi_ext.img')} \\
  --image odm_a={q(WSL_C1_BASE + '/provider_images/odm.img')} \\
  --image product_a={q(WSL_C1_BASE + '/super/avb_images/product.img')} \\
  --image system_a={q(WSL_C18_STAGE + '/system_c18.img')} \\
  --image system_ext_a={q(WSL_C17_STAGE + '/system_ext_c17.img')} \\
  --image vendor_a={q(WSL_C1_BASE + '/provider_images/vendor.img')} --output {c18_sparse}
{q(SIMG2IMG)} {c18_sparse} {c18_raw_super}
{q(LPDUMP)} {c18_raw_super} > {q(WSL_C18_STAGE + '/lpdump_c18.txt')}
for name in mi_ext_a odm_a product_a system_a system_ext_a vendor_a; do grep -q "$name" {q(WSL_C18_STAGE + '/lpdump_c18.txt')}; done
cp {c18_sparse} {q(WSL_C18_IMAGES + '/super.img')}
"""
    run_wsl(super_build)

    images: dict[str, dict[str, object]] = {}
    for name in REQUIRED_IMAGES:
        if name in ("super.img", "vbmeta_system.img"):
            path = C18_IMAGES / name
            images[name] = {"bytes": path.stat().st_size, "sha256": sha256(path)}
        else:
            images[name] = source_manifest["images"][name]
    manifest = {
        "candidate": CANDIDATE,
        "base": SOURCE_CANDIDATE,
        "changes": [
            "system/build.prop: change persist.graphics.egl from angle to adreno, matching the exact thyme vendor ro.hardware.egl=adreno.",
            "system/etc/init/surfaceflinger.rc: after ro.persistent_properties.ready=true, set persist.graphics.egl=adreno so a stale /data persistent ANGLE value cannot override this test route.",
        ],
        "retained_from_c17": [
            "C14 BPF bootstrap bypass.",
            "C13 Keymaster/Gatekeeper ion_device rules.",
            "C17 hal_graphics_allocator_default ion_device open/read rule.",
            "C13 fstab, metadata encryption and /data path.",
            "thyme boot, vendor_boot, dtbo, vbmeta, product, vendor, odm and mi_ext inputs.",
            "C17 system_ext image and policy; no kernel or hardware HAL replacement.",
        ],
        "flash_scope_prepared": ["vbmeta_system_a", "super"],
        "evidence_basis": [
            "C17 has 24 identical SurfaceFlinger chooseEglConfig abort stacks; ANGLE runtime loading is not proven.",
            "C17 graphicsengine independently SIGSEGVs in vkEnumeratePhysicalDevices+4 shortly before the first SurfaceFlinger abort; causality is unproven.",
            "C17 target vendor image declares ro.hardware.egl=adreno and contains 64-bit libEGL_adreno.so and libGLESv2_adreno.so.",
            "The K40 Snapdragon 870 success package uses ro.hardware.egl=adreno.",
        ],
        "limits": [
            "C18 tests the native Adreno route; it does not prove the prior Vulkan SIGSEGV caused the EGLConfig failure.",
            "If SurfaceFlinger still rejects EGLConfig, the next target is the actual EGLConfig/HWC/Gralloc format contract.",
            "No userdata or metadata wipe is included.",
            "Build script is host-only; flashing is handled by a separate restricted script and this script never reboots the device.",
        ],
        "checks": [
            "system EROFS fsck and property/init-script readback.",
            "vbmeta_system system descriptor matches the new system image; product and system_ext descriptors remain inherited from C17.",
            "LP dump includes all active A partitions with the C17 layout.",
        ],
        "images": images,
    }
    (C18_IMAGES / "BUILD_MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    if set(path.name for path in C18_IMAGES.glob("*.img")) != set(REQUIRED_IMAGES):
        raise RuntimeError("C18 output image set is incomplete or unexpected.")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
