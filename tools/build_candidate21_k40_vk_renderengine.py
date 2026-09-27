#!/usr/bin/env python3
"""Build C21 by applying the K40 OS4 Skia Vulkan RenderEngine profile to C20.

This is a host-only build. It does not communicate with or modify a device.
It keeps the C20 ANGLE route, RGBX composition format, thyme hardware stack,
SELinux policy, fstab, kernel, and all other logical partitions unchanged.
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
C20_DIR = ROOT / "work/stage_j_thyme_os4_candidate_20_angle_route_diag_run1"
C20_IMAGES = C20_DIR / "images"
C21_DIR = ROOT / "work/stage_k_thyme_os4_candidate_21_k40_vk_renderengine_run1"
C21_IMAGES = C21_DIR / "images"

WSL_ROOT = f"/mnt/{ROOT.drive[0].lower()}/{ROOT.as_posix()[3:]}" if ROOT.drive else ROOT.as_posix()
WSL_BUILD_ROOT = "/root/10s_os4_build"
WSL_C1_BASE = f"{WSL_BUILD_ROOT}/thyme_xiaomi15_os4_first_boot_candidate_1"
WSL_C15_STAGE = f"{WSL_BUILD_ROOT}/c15_angle_egl_20260926_run1"
WSL_C17_STAGE = f"{WSL_BUILD_ROOT}/c17_graphics_allocator_open_20260926_run1"
WSL_C20_STAGE = f"{WSL_BUILD_ROOT}/c20_angle_diag_20260927_run1"
WSL_C21_STAGE = f"{WSL_BUILD_ROOT}/c21_k40_vk_renderengine_20260927_run1"
WSL_C20_IMAGES = f"{WSL_ROOT}/work/stage_j_thyme_os4_candidate_20_angle_route_diag_run1/images"
WSL_C21_IMAGES = f"{WSL_ROOT}/work/stage_k_thyme_os4_candidate_21_k40_vk_renderengine_run1/images"

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
SOURCE_CANDIDATE = "Candidate 20 ANGLE EGL route and runtime diagnostics"
CANDIDATE = "Candidate 21 K40 Skia Vulkan RenderEngine profile"
K40_PROPERTIES = (
    "debug.renderengine.vulkan=true",
    "debug.hwui.renderer=skiavk",
    "debug.renderengine.backend=skiavkthreaded",
)
PIXEL_FORMAT_PROPERTY = "ro.surface_flinger.default_composition_pixel_format=2"
ANGLE_PROPERTY = "persist.graphics.egl=angle"


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
    if len(sys.argv) != 1:
        raise SystemExit("Usage: build_candidate21_k40_vk_renderengine.py")
    if C21_DIR.exists():
        raise FileExistsError(f"Refusing to overwrite an existing C21 directory: {C21_DIR}")
    source_manifest_path = C20_IMAGES / "BUILD_MANIFEST.json"
    if not source_manifest_path.is_file():
        raise FileNotFoundError(source_manifest_path)
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    if source_manifest.get("candidate") != SOURCE_CANDIDATE:
        raise RuntimeError("Source manifest is not the expected C20 build.")
    if set(source_manifest.get("images", {})) != set(IMAGE_NAMES):
        raise RuntimeError("C20 manifest does not contain exactly the six expected images.")

    C21_DIR.mkdir(parents=True, exist_ok=False)
    C21_IMAGES.mkdir(exist_ok=False)
    for name in IMAGE_NAMES:
        source = C20_IMAGES / name
        if not source.is_file():
            raise FileNotFoundError(source)
        expected = source_manifest["images"][name]
        if source.stat().st_size != int(expected["bytes"]):
            raise RuntimeError(f"C20 input size differs from manifest: {name}")
        if name not in ("super.img", "vbmeta_system.img") and sha256(source) != expected["sha256"].upper():
            raise RuntimeError(f"C20 inherited image differs from manifest: {name}")
        if name not in ("super.img", "vbmeta_system.img"):
            shutil.copy2(source, C21_IMAGES / name)

    wsl_c20_tree = q(f"{WSL_C20_STAGE}/system_tree")
    wsl_c21_tree = q(f"{WSL_C21_STAGE}/system_tree")
    setup = f"""
set -euo pipefail
if test -e {q(WSL_C21_STAGE)}; then
  echo 'C21 WSL stage already exists; refusing to overwrite it.' >&2
  exit 2
fi
test -f {wsl_c20_tree}/system/build.prop
mkdir -p {q(WSL_C21_STAGE)}
cp -a {wsl_c20_tree} {wsl_c21_tree}
python3 - <<'PY'
from pathlib import Path
tree = Path({(WSL_C21_STAGE + '/system_tree')!r})
prop = tree / 'system/build.prop'
text = prop.read_text(encoding='utf-8')
assert text.count({ANGLE_PROPERTY!r}) == 1, 'C20 ANGLE route is missing or duplicated.'
assert text.count({PIXEL_FORMAT_PROPERTY!r}) == 1, 'C20 RGBX=2 property is missing or duplicated.'
for line in {K40_PROPERTIES!r}:
    key = line.split('=', 1)[0]
    assert not any(existing.startswith(key + '=') for existing in text.splitlines()), f'Property already exists: {{key}}'
    text = text.rstrip('\\n') + '\\n' + line + '\\n'
prop.write_text(text, encoding='utf-8', newline='\\n')
rc = tree / 'system/etc/init/surfaceflinger.rc'
rc_text = rc.read_text(encoding='utf-8')
assert rc_text.count('    setprop persist.graphics.egl angle') == 1, 'C20 post-persistent ANGLE action changed.'
print('Added the K40 RenderEngine Vulkan flag/backend and HWUI renderer; retained C20 ANGLE and RGBX=2.')
PY
"""
    run_wsl(setup)

    wsl_tree = q(f"{WSL_C21_STAGE}/system_tree")
    wsl_fs_config = q(f"{WSL_C15_STAGE}/system_fs_config_c15")
    wsl_contexts = q(f"{WSL_C1_BASE}/configs_retained/system/file_contexts")
    wsl_system_raw = q(f"{WSL_C21_STAGE}/system_c21.raw.erofs")
    wsl_system_image = q(f"{WSL_C21_STAGE}/system_c21.img")
    build_system = f"""
set -euo pipefail
{q(MKFS)} -zlz4hc -T 0 -U {SYSTEM_UUID} --mount-point=/system \\
  --fs-config-file={wsl_fs_config} --file-contexts={wsl_contexts} {wsl_system_raw} {wsl_tree} \\
  > {q(WSL_C21_STAGE + '/mkfs_system_c21.log')} 2>&1
{q(FSCK)} -d0 {wsl_system_raw} > {q(WSL_C21_STAGE + '/fsck_system_c21.log')} 2>&1
cp {wsl_system_raw} {wsl_system_image}
python3 {q(AVBTOOL)} add_hashtree_footer --image {wsl_system_image} --partition_size {SYSTEM_PARTITION_SIZE} \\
  --partition_name system --hash_algorithm sha256 --salt {SALT} --algorithm NONE --do_not_generate_fec
{q(FSCK)} -d0 {wsl_system_raw} > {q(WSL_C21_STAGE + '/fsck_system_c21.log')} 2>&1
{q(DUMP)} --cat --path=/system/build.prop {wsl_system_raw} > {q(WSL_C21_STAGE + '/build.prop.c21.txt')}
for property in {q(K40_PROPERTIES[0])} {q(K40_PROPERTIES[1])} {q(K40_PROPERTIES[2])} {q(ANGLE_PROPERTY)} {q(PIXEL_FORMAT_PROPERTY)}; do
  grep -Fx "$property" {q(WSL_C21_STAGE + '/build.prop.c21.txt')}
done
{q(DUMP)} --cat --path=/system/etc/init/surfaceflinger.rc {wsl_system_raw} > {q(WSL_C21_STAGE + '/surfaceflinger.rc.c21.txt')}
grep -Fx '    setprop persist.graphics.egl angle' {q(WSL_C21_STAGE + '/surfaceflinger.rc.c21.txt')}
python3 - <<'PY'
from pathlib import Path
image = Path({(WSL_C21_STAGE + '/system_c21.img')!r})
assert image.stat().st_size == {SYSTEM_PARTITION_SIZE}, image.stat().st_size
print('C21 system image bytes:', image.stat().st_size)
PY
"""
    run_wsl(build_system)

    wsl_vbmeta = f"""
set -euo pipefail
PYTHONPATH={q(BOOTIMG_PATH)} python3 - <<'PY'
from pathlib import Path
from avbtool import Avb, ImageHandler, AvbHashtreeDescriptor

avb = Avb()
base = Path({(WSL_C20_IMAGES + '/vbmeta_system.img')!r})
system = Path({(WSL_C21_STAGE + '/system_c21.img')!r})
out = Path({(WSL_C21_IMAGES + '/vbmeta_system.img')!r})
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
n = 131072
assert len(blob) <= n
out.write_bytes(blob + b'\\0' * (n - len(blob)))
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

    c21_sparse = q(f"{WSL_C21_STAGE}/super_c21_sparse.img")
    c21_raw = q(f"{WSL_C21_STAGE}/super_c21_raw.img")
    c21_super_out = q(f"{WSL_C21_IMAGES}/super.img")
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
  --image system_a={q(WSL_C21_STAGE + '/system_c21.img')} \\
  --image system_ext_a={q(WSL_C17_STAGE + '/system_ext_c17.img')} \\
  --image vendor_a={q(WSL_C1_BASE + '/provider_images/vendor.img')} --output {c21_sparse}
{q(SIMG2IMG)} {c21_sparse} {c21_raw}
{q(LPDUMP)} {c21_raw} > {q(WSL_C21_STAGE + '/lpdump_c21.txt')}
for name in mi_ext_a odm_a product_a system_a system_ext_a vendor_a; do grep -q "$name" {q(WSL_C21_STAGE + '/lpdump_c21.txt')}; done
cp {c21_sparse} {c21_super_out}
"""
    run_wsl(super_build)

    images: dict[str, dict[str, object]] = {}
    for name in IMAGE_NAMES:
        path = C21_IMAGES / name
        if name == "super.img":
            if not path.is_file():
                raise FileNotFoundError(path)
        elif name == "vbmeta_system.img":
            if not path.is_file():
                raise FileNotFoundError(path)
        expected = source_manifest["images"].get(name)
        images[name] = {"bytes": path.stat().st_size, "sha256": sha256(path)}
        if name not in ("super.img", "vbmeta_system.img") and expected:
            if images[name]["bytes"] != int(expected["bytes"]) or images[name]["sha256"] != expected["sha256"].upper():
                raise RuntimeError(f"C21 inherited image differs from C20: {name}")
    manifest = {
        "candidate": CANDIDATE,
        "base": SOURCE_CANDIDATE,
        "changes": [
            "system/build.prop: add K40 OS4's debug.renderengine.vulkan=true, debug.renderengine.backend=skiavkthreaded, and debug.hwui.renderer=skiavk.",
            "Retain C20 persist.graphics.egl=angle and post-persistent-property ANGLE action, plus RGBX format=2.",
        ],
        "retained_from_c20": [
            "C13-C19 validated boot, policy, BPF, ION, storage, and data-encryption changes.",
            "Thyme kernel, vendor, odm, product, vendor_boot, dtbo, and vbmeta images.",
            "No K40 hardware-specific vendor library, HWC, gralloc, Vulkan binary, kernel, or device firmware copied.",
            "No userdata/metadata wipe and no hardware-identity partition change.",
        ],
        "evidence_basis": [
            "C20 pmsg proves SurfaceFlinger instantiated SkiaGLRenderEngine and aborted in chooseEglConfig with format 2; EGL reported the generic Android META-EGL frontend and did not provide a concrete vendor driver identity.",
            "The cached K40 Android 17 OS4.0.0.8 product build.prop selects debug.renderengine.backend=skiavkthreaded, debug.renderengine.vulkan=true, and debug.hwui.renderer=skiavk.",
            "K40, Xiaomi 15 donor, and C20 system SurfaceFlinger/RenderEngine libraries are byte-identical; C20's SurfaceFlinger library contains the RenderEngine backend property and SkiaVk implementation strings.",
            "The target's graphicsengine Vulkan pipeline-cache builder separately crashes at vkEnumeratePhysicalDevices after a null/failed Vulkan-instance path; that does not prove SurfaceFlinger SkiaVk fails, but is a concrete risk to test.",
        ],
        "limits": [
            "C21 uses K40's framework RenderEngine Vulkan route to bypass the failing EGLConfig path; it does not enumerate EGLConfig counts or repair the underlying EGL driver.",
            "Only debug properties are set in system/build.prop. ro.hwui.use_vulkan=true is omitted because the thyme vendor property is explicitly empty and system properties have lower precedence than vendor/product properties; debug.hwui.renderer=skiavk is the direct HWUI override.",
            "The K40 product profile is not proof that thyme's distinct Adreno/Vulkan vendor binaries initialize successfully.",
            "C21 has not been booted on device until a separate onsite confirmation is given after flashing.",
        ],
        "checks": [
            "C20 manifest checked; inherited boot/vendor_boot/dtbo/vbmeta sizes and SHA-256 preserved.",
            "Final system EROFS fsck passed and the three C21 routing properties plus the retained ANGLE/RGBX properties were read back from the built image.",
            "vbmeta_system contains the new system hashtree descriptor while product/system_ext descriptors remain unchanged.",
            "LP dump lists the expected active A logical partitions and the original geometry.",
        ],
        "flash_scope_prepared": ["super", "vbmeta_system_a"],
        "images": images,
    }
    (C21_IMAGES / "BUILD_MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    if {path.name for path in C21_IMAGES.glob("*.img")} != set(IMAGE_NAMES):
        raise RuntimeError("C21 output image set is incomplete or unexpected.")
    safe_print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
