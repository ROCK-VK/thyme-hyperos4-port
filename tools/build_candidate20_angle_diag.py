#!/usr/bin/env python3
"""Build C20: select system ANGLE and add scoped EGL/linker diagnostics on C19.

This host-only script never communicates with a device. It rebuilds system,
vbmeta_system, and super from the verified C19 tree and inputs.
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
C19_SOURCE_IMAGES = ROOT / "work/stage_i_thyme_os4_candidate_19_rgbx_egl_run1/images"
C20_DIR = ROOT / "work/stage_j_thyme_os4_candidate_20_angle_route_diag_run1"
C20_IMAGES = C20_DIR / "images"

if ROOT.drive:
    WSL_ROOT = f"/mnt/{ROOT.drive[0].lower()}/{ROOT.as_posix()[3:]}"
else:
    WSL_ROOT = ROOT.as_posix()
WSL_BUILD_ROOT = "/root/10s_os4_build"
WSL_C1_BASE = f"{WSL_BUILD_ROOT}/thyme_xiaomi15_os4_first_boot_candidate_1"
WSL_C15_STAGE = f"{WSL_BUILD_ROOT}/c15_angle_egl_20260926_run1"
WSL_C17_STAGE = f"{WSL_BUILD_ROOT}/c17_graphics_allocator_open_20260926_run1"
WSL_C19_SOURCE_STAGE = f"{WSL_BUILD_ROOT}/c19_rgbx_egl_20260927_run1"
WSL_C20_STAGE = f"{WSL_BUILD_ROOT}/c20_angle_diag_20260927_run1"
WSL_C19_SOURCE_IMAGES = f"{WSL_ROOT}/work/stage_i_thyme_os4_candidate_19_rgbx_egl_run1/images"
WSL_C20_IMAGES = f"{WSL_ROOT}/work/stage_j_thyme_os4_candidate_20_angle_route_diag_run1/images"

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
SYSTEM_UUID = "6f1b5f0e-8f73-4e28-aefe-8ee48d2d8b41"
IMAGE_NAMES = ("boot.img", "vendor_boot.img", "dtbo.img", "vbmeta.img", "vbmeta_system.img", "super.img")
SOURCE_CANDIDATE = "Candidate 19 RGBX EGLConfig compatibility experiment"
CANDIDATE = "Candidate 20 ANGLE EGL route and runtime diagnostics"
PIXEL_FORMAT_PROPERTY = "ro.surface_flinger.default_composition_pixel_format=2"
ANGLE_PROPERTY = "persist.graphics.egl=angle"
LINKER_PROPERTIES = (
    "debug.ld.app.surfaceflinger=dlerror,dlopen",
    "debug.ld.app.graphicsengine=dlerror,dlopen",
    "log.tag.linker=DEBUG",
)


def q(value: str) -> str:
    return shlex.quote(value)


def safe_print(value: str) -> None:
    try:
        print(value, end="" if value.endswith("\n") else "\n")
    except UnicodeEncodeError:
        encoding = sys.stdout.encoding or "utf-8"
        fallback = value.encode(encoding, errors="backslashreplace").decode(encoding, errors="replace")
        print(fallback, end="" if fallback.endswith("\n") else "\n")


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
        raise SystemExit("Usage: build_candidate20_angle_diag.py [--resume]")
    if C20_DIR.exists() and not resume:
        raise FileExistsError(f"Refusing to overwrite an existing C20 directory: {C20_DIR}")
    source_manifest_path = C19_SOURCE_IMAGES / "BUILD_MANIFEST.json"
    if not source_manifest_path.is_file():
        raise FileNotFoundError(source_manifest_path)
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    if source_manifest.get("candidate") != SOURCE_CANDIDATE:
        raise RuntimeError("Source manifest is not the expected C19 build.")
    if set(source_manifest.get("images", {})) != set(IMAGE_NAMES):
        raise RuntimeError("C20 manifest does not contain exactly the six expected images.")
    for name in IMAGE_NAMES:
        source = C19_SOURCE_IMAGES / name
        if not source.is_file():
            raise FileNotFoundError(source)
        if source.stat().st_size != int(source_manifest["images"][name]["bytes"]):
            raise RuntimeError(f"C20 image size differs from its manifest: {name}")
        if name != "super.img" and sha256(source) != source_manifest["images"][name]["sha256"].upper():
            raise RuntimeError(f"C20 image SHA-256 differs from its manifest: {name}")

    if not C20_DIR.exists():
        C20_DIR.mkdir(parents=True, exist_ok=False)
    if not C20_IMAGES.exists():
        C20_IMAGES.mkdir(exist_ok=False)
    for name in IMAGE_NAMES:
        if name not in ("super.img", "vbmeta_system.img"):
            destination = C20_IMAGES / name
            source = C19_SOURCE_IMAGES / name
            if destination.exists():
                if destination.stat().st_size != source_manifest["images"][name]["bytes"] or sha256(destination) != source_manifest["images"][name]["sha256"].upper():
                    raise RuntimeError(f"Existing C20 inherited image differs from C19: {name}")
            else:
                shutil.copy2(source, destination)

    wsl_stage = q(WSL_C20_STAGE)
    wsl_c19_tree = q(f"{WSL_C19_SOURCE_STAGE}/system_tree")
    wsl_c20_tree = q(f"{WSL_C20_STAGE}/system_tree")
    setup = f"""
set -euo pipefail
if test -e {wsl_stage} && [ {1 if resume else 0} -ne 1 ]; then
  echo 'C20 WSL stage already exists; refusing to overwrite it without --resume.' >&2
  exit 2
fi
test -f {wsl_c19_tree}/system/build.prop
mkdir -p {wsl_stage}
if [ ! -d {wsl_c20_tree} ]; then cp -a {wsl_c19_tree} {wsl_c20_tree}; fi
python3 - <<'PY'
from pathlib import Path
tree = Path({(WSL_C20_STAGE + '/system_tree')!r})
prop = tree / 'system/build.prop'
text = prop.read_text(encoding='utf-8')
old_angle = 'persist.graphics.egl=adreno'
assert text.count(old_angle) == 1, 'Expected one C19 Adreno default route.'
assert {ANGLE_PROPERTY!r} not in text, 'C19 source unexpectedly already contains the C20 route.'
text = text.replace(old_angle, {ANGLE_PROPERTY!r})
text = text.replace(
    '# Candidate 18: use thyme native EGL matching vendor ro.hardware.egl=adreno.',
    '# Candidate 20: select system ANGLE after persistent properties load.')
for line in {LINKER_PROPERTIES!r}:
    key = line.split('=', 1)[0]
    assert key + '=' not in text, f'Property already exists: {{key}}'
    text = text.rstrip('\\n') + '\\n' + line + '\\n'
pixel_line = {PIXEL_FORMAT_PROPERTY!r}
assert text.count(pixel_line) == 1, 'C19 RGBX=2 property was lost or duplicated.'
prop.write_text(text, encoding='utf-8', newline='\\n')

rc = tree / 'system/etc/init/surfaceflinger.rc'
rc_text = rc.read_text(encoding='utf-8')
old_action = '    setprop persist.graphics.egl adreno'
new_action = '    setprop persist.graphics.egl angle'
assert rc_text.count(old_action) == 1, 'Expected one C19 post-persistent-property Adreno override.'
rc_text = rc_text.replace(old_action, new_action)
rc_text = rc_text.replace(
    '# Candidate 18: reapply the target-native EGL route after /data properties load.',
    '# Candidate 20: apply the ANGLE route after /data properties load.')
assert rc_text.count(new_action) == 1 and old_action not in rc_text
rc.write_text(rc_text, encoding='utf-8', newline='\\n')
print('C20 changes the default and post-persistent EGL route to ANGLE, adds per-process linker tracing, and retains RGBX=2.')
PY
"""
    run_wsl(setup)

    wsl_tree = q(f"{WSL_C20_STAGE}/system_tree")
    wsl_fs_config = q(f"{WSL_C15_STAGE}/system_fs_config_c15")
    wsl_contexts = q(f"{WSL_C1_BASE}/configs_retained/system/file_contexts")
    wsl_system_raw = q(f"{WSL_C20_STAGE}/system_c20.raw.erofs")
    wsl_system_image = q(f"{WSL_C20_STAGE}/system_c20.img")
    build_system = f"""
set -euo pipefail
{q(MKFS)} -zlz4hc -T 0 -U {SYSTEM_UUID} --mount-point=/system \\
  --fs-config-file={wsl_fs_config} --file-contexts={wsl_contexts} {wsl_system_raw} {wsl_tree} \\
  > {q(WSL_C20_STAGE + '/mkfs_system_c20.log')} 2>&1
{q(FSCK)} -d0 {wsl_system_raw} > {q(WSL_C20_STAGE + '/fsck_system_c20.log')} 2>&1
cp {wsl_system_raw} {wsl_system_image}
python3 {q(AVBTOOL)} add_hashtree_footer --image {wsl_system_image} --partition_size {SYSTEM_PARTITION_SIZE} \\
  --partition_name system --hash_algorithm sha256 --salt {SALT} --algorithm NONE --do_not_generate_fec
{q(FSCK)} -d0 {wsl_system_raw} > {q(WSL_C20_STAGE + '/fsck_system_c20.log')} 2>&1
{q(DUMP)} --cat --path=/system/build.prop {wsl_system_raw} > {q(WSL_C20_STAGE + '/build.prop.c20.txt')}
grep -Fx '{ANGLE_PROPERTY}' {q(WSL_C20_STAGE + '/build.prop.c20.txt')}
grep -Fx '{PIXEL_FORMAT_PROPERTY}' {q(WSL_C20_STAGE + '/build.prop.c20.txt')}
grep -Fx 'debug.ld.app.surfaceflinger=dlerror,dlopen' {q(WSL_C20_STAGE + '/build.prop.c20.txt')}
grep -Fx 'debug.ld.app.graphicsengine=dlerror,dlopen' {q(WSL_C20_STAGE + '/build.prop.c20.txt')}
grep -Fx 'log.tag.linker=DEBUG' {q(WSL_C20_STAGE + '/build.prop.c20.txt')}
{q(DUMP)} --cat --path=/system/etc/init/surfaceflinger.rc {wsl_system_raw} > {q(WSL_C20_STAGE + '/surfaceflinger.rc.c20.txt')}
grep -Fx '    setprop persist.graphics.egl angle' {q(WSL_C20_STAGE + '/surfaceflinger.rc.c20.txt')}
if grep -Fx '    setprop persist.graphics.egl adreno' {q(WSL_C20_STAGE + '/surfaceflinger.rc.c20.txt')}; then
  echo 'Conflicting Adreno init override remains in C20 system image.' >&2
  exit 3
fi
python3 - <<'PY'
from pathlib import Path
image = Path({(WSL_C20_STAGE + '/system_c20.img')!r})
assert image.stat().st_size == {SYSTEM_PARTITION_SIZE}, image.stat().st_size
print('C20 system image bytes:', image.stat().st_size)
PY
"""
    run_wsl(build_system)

    wsl_vbmeta = f"""
set -euo pipefail
PYTHONPATH={q(BOOTIMG_PATH)} python3 - <<'PY'
from pathlib import Path
from avbtool import Avb, ImageHandler, AvbHashtreeDescriptor

avb = Avb()
base = Path({(WSL_C19_SOURCE_IMAGES + '/vbmeta_system.img')!r})
system = Path({(WSL_C20_STAGE + '/system_c20.img')!r})
out = Path({(WSL_C20_IMAGES + '/vbmeta_system.img')!r})
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
    run_wsl(wsl_vbmeta)

    c20_sparse = q(f"{WSL_C20_STAGE}/super_c20_sparse.img")
    c20_raw = q(f"{WSL_C20_STAGE}/super_c20_raw.img")
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
  --image system_a={q(WSL_C20_STAGE + '/system_c20.img')} \\
  --image system_ext_a={q(WSL_C17_STAGE + '/system_ext_c17.img')} \\
  --image vendor_a={q(WSL_C1_BASE + '/provider_images/vendor.img')} --output {c20_sparse}
{q(SIMG2IMG)} {c20_sparse} {c20_raw}
{q(LPDUMP)} {c20_raw} > {q(WSL_C20_STAGE + '/lpdump_c20.txt')}
for name in mi_ext_a odm_a product_a system_a system_ext_a vendor_a; do grep -q "$name" {q(WSL_C20_STAGE + '/lpdump_c20.txt')}; done
cp {c20_sparse} {q(WSL_C20_IMAGES + '/super.img')}
"""
    run_wsl(super_build)

    images: dict[str, dict[str, object]] = {}
    for name in IMAGE_NAMES:
        if name in ("super.img", "vbmeta_system.img"):
            path = C20_IMAGES / name
            images[name] = {"bytes": path.stat().st_size, "sha256": sha256(path)}
        else:
            images[name] = source_manifest["images"][name]
    manifest = {
        "candidate": CANDIDATE,
        "base": SOURCE_CANDIDATE,
        "changes": [
            "system/build.prop: change persist.graphics.egl from adreno to angle and add process-scoped linker diagnostics for surfaceflinger and graphicsengine.",
            "system/etc/init/surfaceflinger.rc: reapply persist.graphics.egl=angle after persistent /data properties load, removing the conflicting C19 Adreno override.",
            "Retain ro.surface_flinger.default_composition_pixel_format=2 (RGBX_8888) from C19.",
        ],
        "retained_from_c19": [
            "C14 BPF bootstrap bypass.",
            "C13 Keymaster/Gatekeeper ion_device rules.",
            "C17 graphics allocator ion_device open/read rule.",
            "C19 RGBX composition format and all prior C13-C19 validated fixes.",
            "C19 system_ext policy, fstab/data encryption path, and thyme kernel/vendor hardware stack.",
            "System ANGLE libraries already present in the C19 system tree; no GPU, Vulkan, or vendor library is replaced.",
            "No SELinux expansion, Vulkan/GPU library replacement, or userdata/metadata wipe.",
        ],
        "flash_scope_prepared": ["super", "vbmeta_system_a"],
        "evidence_basis": [
            "C19 pmsg recorded 43 SurfaceFlinger no suitable EGLConfig aborts, all with format: 2; the RGBX request reached SurfaceFlinger but did not resolve the failure.",
            "The C19 system libEGL binary contains ANGLE route selection and the fatal ANGLE-load failure string; the exact actual backend is not identified by prior pstore.",
            "C19 has 64-bit system ANGLE EGL/GLES binaries. Its libEGL binary lacks the ALOGV success-path strings, so log.tag.libEGL=VERBOSE would not reliably add driver-path evidence.",
            "C20 uses bionic per-process debug.ld.app.<process> linker tracing and log.tag.linker=DEBUG; trace availability depends on target process dumpability and is best-effort.",
        ],
        "limits": [
            "C20 tests explicit system ANGLE routing while preserving C19 RGBX=2; it is a targeted experiment, not a confirmed root-cause fix.",
            "If ANGLE is requested and fails to load, the Android 17 loader has a fatal branch. If it loads but EGLConfig still fails, linker logs, pstore, and any available ADB process maps are needed to confirm the backend.",
            "Per-process linker tracing can be suppressed for non-dumpable processes; absence of trace output alone does not prove no library was loaded.",
            "This does not enumerate every EGLConfig or change the SurfaceFlinger request, HWC/Gralloc, Vulkan, or GPU libraries.",
            "No boot, vendor_boot, dtbo, vbmeta, system_ext policy, kernel, data, or hardware identity partition changes.",
            "Build is host-only; separate flash script writes only super and vbmeta_system_a and never reboots.",
        ],
        "checks": [
            "C19 source manifest and input image sizes/hashes checked; C20 ANGLE route, linker properties, RGBX=2, and matching init override are read back from final system image; EROFS fsck passed.",
            "C20 system hashtree descriptor matches the built system; product/system_ext descriptors match C19.",
            "LP dump has the expected active A logical partitions and C19 geometry.",
        ],
        "images": images,
    }
    (C20_IMAGES / "BUILD_MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    if {path.name for path in C20_IMAGES.glob("*.img")} != set(IMAGE_NAMES):
        raise RuntimeError("C20 output image set is incomplete or unexpected.")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
