#!/usr/bin/env python3
"""Build the C22 K40 Android 17 Vulkan UMD compatibility experiment.

Run inside the project's Ubuntu WSL distribution:
  python3 /mnt/e/RVK/10S_OS4/tools/build_candidate22_k40_vulkan_umd.py

Only a private copy of the C1 vendor ext4 image is modified. The C21 EGL/GLES
libraries remain in place; the K40 Vulkan ICD gets isolated SONAMEs for its
GSL/Adreno support libraries. No device is contacted by this script.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path("/mnt/e/RVK/10S_OS4")
C21_DIR = ROOT / "work/stage_k_thyme_os4_candidate_21_k40_vk_renderengine_run1"
C21_IMAGES = C21_DIR / "images"
C22_DIR = ROOT / "work/stage_l_thyme_os4_candidate_22_k40_vk_umd_run5"
C22_IMAGES = C22_DIR / "images"

WSL_BUILD_ROOT = Path("/root/10s_os4_build")
C1_BASE = WSL_BUILD_ROOT / "thyme_xiaomi15_os4_first_boot_candidate_1"
C1_VENDOR = C1_BASE / "provider_images/vendor.img"
C21_STAGE = WSL_BUILD_ROOT / "c21_k40_vk_renderengine_20260927_run1"
C21_SYSTEM_EXT = WSL_BUILD_ROOT / "c22_k40_vulkan_migration_20260927/c21_system_ext_a_from_super_20260927/system_ext_a.img"
C22_STAGE = WSL_BUILD_ROOT / "c22_k40_vulkan_umd_20260927_run5"
K40_DEPS = WSL_BUILD_ROOT / "c22_k40_vulkan_migration_20260927/k40_graphics_deps"

TOOLS = ROOT / "tools"
AVBTOOL = TOOLS / "bootimg/avbtool.py"
LPMAKE = TOOLS / "android-tools-static/linux/android-tools-static/lpmake"
SIMG2IMG = TOOLS / "android-tools-static/linux/android-tools-static/simg2img"
LPDUMP = TOOLS / "android-tools-static/linux/android-tools-static/lpdump"

DEVICE_SIZE = 9_126_805_504
ALIGNMENT = 1_048_576
SYSTEM_SIZE = 1_092_616_192
SYSTEM_EXT_SIZE = 942_669_824
VENDOR_SIZE = 1_510_998_016
VENDOR_FS_SIZE = 1_486_426_112
VENDOR_SALT = "869fbe2b06434e545491b0977ea070676ec7307609884d646234d592793f777f"

IMAGE_NAMES = (
    "boot.img",
    "vendor_boot.img",
    "dtbo.img",
    "vbmeta.img",
    "vbmeta_system.img",
    "super.img",
)
EXPECTED_C21 = "Candidate 21 K40 Skia Vulkan RenderEngine profile"
EXPECTED_C20 = "Candidate 20 ANGLE EGL route and runtime diagnostics"
CANDIDATE = "Candidate 22 K40 Android 17 Vulkan UMD ABI compatibility stack"

# Every copied object is from the cached K40 OS4.0.0.8 Android 17 package.
# libllvm-qgl.so is retained under its canonical name because K40 glnext loads
# it with dlopen("libllvm-qgl.so"); C21's vendor image does not contain it.
K40_FILE_MAP = {
    "vulkan.adreno.so": "/lib64/hw/vulkan.adreno.so",
    "libgsl.so": "/lib64/libgsl_k40.so",
    "libadreno_utils.so": "/lib64/libadreno_utils_k40.so",
    "libllvm-glnext.so": "/lib64/libllvm-glnext_k40.so",
    "libllvm-qgl.so": "/lib64/libllvm-qgl.so",
}
RENAMES = {
    "libgsl.so": "libgsl_k40.so",
    "libadreno_utils.so": "libadreno_utils_k40.so",
    "libllvm-glnext.so": "libllvm-glnext_k40.so",
}
LABEL = "u:object_r:same_process_hal_file:s0"
VULKAN_SHA256 = "F7D5C94AF03895AFC72C6A03BB837C08E4B1515AEFAEF8CACB355F386A0E9DB8"


def say(message: str) -> None:
    print(message, flush=True)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def run(args: list[str | os.PathLike[str]], *, log: Path | None = None,
        allow_codes: tuple[int, ...] = (0,)) -> str:
    cmd = [os.fspath(arg) for arg in args]
    result = subprocess.run(cmd, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, errors="replace")
    output = result.stdout or ""
    if log is not None:
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(output, encoding="utf-8", newline="\n")
    if result.returncode not in allow_codes:
        say(f"FAILED ({result.returncode}): {' '.join(cmd)}")
        if output:
            say(output[-12000:])
        raise subprocess.CalledProcessError(result.returncode, cmd, output)
    return output


def require_file(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(path)


def debugfs(image: Path, command: str) -> str:
    return run(["/usr/sbin/debugfs", "-R", command, image])


def debugfs_exists(image: Path, path: str) -> bool:
    output = debugfs(image, f"stat {path}")
    return "File not found" not in output and "No such file" not in output


def elf_header(path: Path) -> str:
    return run(["readelf", "-h", path])


def needed(path: Path) -> list[str]:
    return run(["patchelf", "--print-needed", path]).splitlines()


def verify_c21_inputs() -> dict[str, dict[str, object]]:
    manifest_path = C21_IMAGES / "BUILD_MANIFEST.json"
    require_file(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("candidate") != EXPECTED_C21 or manifest.get("base") != EXPECTED_C20:
        raise RuntimeError("C21 image manifest is not the expected baseline.")
    if set(manifest.get("images", {})) != set(IMAGE_NAMES):
        raise RuntimeError("C21 manifest does not describe exactly the six expected images.")
    # super.img is deliberately not reused as an input; C22 rebuilds it from
    # the same C1/C21/C17 logical image sources while replacing only vendor_a.
    for name in ("boot.img", "vendor_boot.img", "dtbo.img", "vbmeta.img", "vbmeta_system.img"):
        path = C21_IMAGES / name
        require_file(path)
        expected = manifest["images"][name]
        if path.stat().st_size != int(expected["bytes"]) or sha256(path) != expected["sha256"].upper():
            raise RuntimeError(f"C21 baseline image differs from its manifest: {name}")
    return manifest


def canonical_descriptor(desc: object) -> str:
    def normalize(value: object) -> object:
        if isinstance(value, bytes):
            return {"bytes_hex": value.hex()}
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        if isinstance(value, (tuple, list)):
            return [normalize(item) for item in value]
        if isinstance(value, dict):
            return {str(key): normalize(item) for key, item in value.items()}
        return repr(value)

    return json.dumps({"type": type(desc).__name__, "fields": normalize(vars(desc))},
                      sort_keys=True, separators=(",", ":"))


def prepare_vendor(c1_vendor: Path, work: Path) -> tuple[Path, dict[str, object]]:
    k40_sources: dict[str, Path] = {}
    expected_files = tuple(K40_FILE_MAP)
    for name in expected_files:
        source = K40_DEPS / name
        require_file(source)
        if "Machine:                           AArch64" not in elf_header(source):
            raise RuntimeError(f"K40 library is not AArch64: {name}")
        k40_sources[name] = source
    if sha256(k40_sources["vulkan.adreno.so"]) != VULKAN_SHA256:
        raise RuntimeError("Cached K40 Vulkan ICD SHA-256 differs from the previously audited Android 17 asset.")
    if b"libllvm-qgl.so" not in k40_sources["libllvm-glnext.so"].read_bytes():
        raise RuntimeError("K40 glnext no longer contains its expected libllvm-qgl.so runtime loader name.")

    # Validate actual source filesystem and preserve the existing file label.
    label_output = debugfs(c1_vendor, "stat /lib64/libgsl.so")
    label_match = re.search(r'security\.selinux \(\d+\) = "([^"\\]+)', label_output)
    if not label_match or label_match.group(1) != LABEL:
        raise RuntimeError("Could not confirm the existing vendor HAL library SELinux label.")
    if not debugfs_exists(c1_vendor, "/lib64/hw/vulkan.adreno.so"):
        raise RuntimeError("C1 vendor source is missing its expected Vulkan ICD target.")
    if debugfs_exists(c1_vendor, "/lib64/libllvm-qgl.so"):
        raise RuntimeError("C1 vendor already has libllvm-qgl.so; refusing to replace an unreviewed library.")
    for relpath in K40_FILE_MAP.values():
        if relpath == "/lib64/hw/vulkan.adreno.so":
            continue
        if debugfs_exists(c1_vendor, relpath):
            raise RuntimeError(f"C1 vendor already contains a C22 addition target: {relpath}")

    # Validate all non-platform NEEDED names from the exact K40 ICD against the
    # C1 vendor and C21 system files. Bionic runtime libraries resolve from the
    # Android runtime APEX and are explicitly treated as platform-provided.
    platform_runtime = {"libc.so", "libm.so", "libdl.so"}
    c21_system = C21_STAGE / "system_tree/system/lib64"
    missing: list[str] = []
    for name in needed(k40_sources["vulkan.adreno.so"]):
        if name in RENAMES or name in platform_runtime:
            continue
        if name == "libllvm-qgl.so":
            continue
        if debugfs_exists(c1_vendor, f"/lib64/{name}"):
            continue
        if (c21_system / name).is_file():
            continue
        missing.append(name)
    # New K40 GSL's added dependencies are also checked against C21 system.
    for name in needed(k40_sources["libgsl.so"]):
        if name in RENAMES or name in platform_runtime:
            continue
        if debugfs_exists(c1_vendor, f"/lib64/{name}") or (c21_system / name).is_file():
            continue
        missing.append(name)
    if missing:
        raise RuntimeError("K40 Vulkan dependencies absent from C1 vendor/C21 system: " + ", ".join(sorted(set(missing))))

    vendor = work / "vendor_c22.img"
    shutil.copy2(c1_vendor, vendor)
    source_bytes = vendor.stat().st_size
    source_hash = sha256(vendor)
    if source_bytes != 1_510_342_656:
        raise RuntimeError(f"Unexpected C1 provider vendor.img size: {source_bytes}")
    run(["python3", AVBTOOL, "erase_footer", "--image", vendor],
        log=work / "avb_vendor_erase_footer.log")
    if vendor.stat().st_size != VENDOR_FS_SIZE:
        raise RuntimeError(f"AVB footer removal did not restore the expected ext4 image length: {vendor.stat().st_size}")

    # Rewrite only staged K40 copies. Keep the three C21 libraries that the old
    # thyme EGL/GLES stack uses untouched under their original SONAMEs.
    staged_sources = work / "k40_patched"
    staged_sources.mkdir()
    for name, source in k40_sources.items():
        target_name = Path(K40_FILE_MAP[name]).name
        target = staged_sources / target_name
        shutil.copy2(source, target)
        if name in RENAMES:
            new_soname = RENAMES[name]
            run(["patchelf", "--set-soname", new_soname, target])
        for old, new in RENAMES.items():
            if old in needed(target):
                run(["patchelf", "--replace-needed", old, new, target])
        if name == "vulkan.adreno.so":
            for old, new in RENAMES.items():
                if old in needed(target):
                    run(["patchelf", "--replace-needed", old, new, target])

    # The K40 Vulkan ICD itself must not retain dependencies on the old C21
    # GSL/Adreno/LLVM objects. qgl remains canonical for the explicit dlopen.
    patched_icd = staged_sources / "vulkan.adreno.so"
    final_needed = needed(patched_icd)
    if any(name in final_needed for name in RENAMES):
        raise RuntimeError("K40 Vulkan ICD still references an unisolated C21 SONAME.")
    expected_renamed = {RENAMES[name] for name in RENAMES}
    if not expected_renamed.issubset(set(final_needed)):
        raise RuntimeError("K40 Vulkan ICD did not retain all three patched K40 support-library dependencies.")

    xattr_file = work / "same_process_hal_file.label"
    xattr_file.write_bytes(LABEL.encode("ascii") + b"\0")
    command_file = work / "debugfs_c22_vendor.commands"
    commands: list[str] = []
    for name, relpath in K40_FILE_MAP.items():
        src = staged_sources / Path(relpath).name
        if name == "vulkan.adreno.so":
            commands.append(f"rm {relpath}")
        commands.append(f"write {src} {relpath}")
        commands.append(f"set_inode_field {relpath} uid 0")
        commands.append(f"set_inode_field {relpath} gid 0")
        commands.append(f"set_inode_field {relpath} mode 0100644")
        commands.append(f"ea_set -f {xattr_file} {relpath} security.selinux")
    command_file.write_text("\n".join(commands) + "\n", encoding="utf-8", newline="\n")
    debug_output = run(["/usr/sbin/debugfs", "-w", "-f", command_file, vendor],
                       log=work / "debugfs_vendor_patch.log")
    if "Command not found" in debug_output or "File not found" in debug_output or "Could not" in debug_output:
        raise RuntimeError("debugfs reported a failed vendor file operation; see debugfs_vendor_patch.log")

    metadata: dict[str, object] = {
        "c1_provider_vendor": {
            "path": str(c1_vendor),
            "source_bytes": source_bytes,
            "source_sha256": source_hash,
            "ext4_bytes_before_avb": VENDOR_FS_SIZE,
        },
        "k40_source_dir": str(K40_DEPS),
        "k40_libraries": {},
        "vendor_additions": {},
    }
    for name, source in k40_sources.items():
        metadata["k40_libraries"][name] = {  # type: ignore[index]
            "bytes": source.stat().st_size,
            "sha256": sha256(source),
            "needed": needed(source),
        }
    for relpath in K40_FILE_MAP.values():
        stat = debugfs(vendor, f"stat {relpath}")
        for marker in ("Mode:  0644", "User:     0", "Group:     0", f'"{LABEL}\\000"'):
            if marker not in stat:
                raise RuntimeError(f"Vendor metadata/xattr mismatch for {relpath}: missing {marker!r}")
        size_match = re.search(r"Size:\s+(\d+)", stat)
        if not size_match:
            raise RuntimeError(f"Could not read ext4 file size for {relpath}")
        metadata["vendor_additions"][relpath] = {  # type: ignore[index]
            "bytes": int(size_match.group(1)),
            "selinux": LABEL,
            "uid": 0,
            "gid": 0,
            "mode": "0644",
        }

    if vendor.stat().st_size != VENDOR_FS_SIZE:
        raise RuntimeError(f"Unexpected ext4 size after AVB footer removal: {vendor.stat().st_size}")
    fsck_log = work / "e2fsck_vendor_readonly.log"
    run(["/usr/sbin/e2fsck", "-f", "-n", vendor], log=fsck_log)
    metadata["vendor_ext4_check"] = "e2fsck -f -n passed before rebuilding the AVB hashtree footer"

    avb_cmd = [
        "python3", AVBTOOL, "add_hashtree_footer", "--image", vendor,
        "--partition_size", str(VENDOR_SIZE), "--partition_name", "vendor",
        "--hash_algorithm", "sha256", "--salt", VENDOR_SALT,
        "--algorithm", "NONE", "--do_not_generate_fec",
    ]
    avb_output = run(avb_cmd, log=work / "avb_vendor_footer.log")
    if vendor.stat().st_size != VENDOR_SIZE:
        raise RuntimeError(f"Vendor AVB image does not fill the expected LP partition: {vendor.stat().st_size}")
    if "Image size" not in avb_output and "hashtree" not in avb_output.lower():
        # avbtool versions differ in summary wording; descriptor parse below is
        # authoritative, so this is deliberately informational only.
        say("avbtool returned success; its summary wording is version-specific.")
    metadata["avb_vendor_footer"] = {
        "partition_name": "vendor",
        "partition_size": VENDOR_SIZE,
        "salt": VENDOR_SALT,
        "fec": "disabled to match the existing C21 root-vbmeta vendor descriptor",
    }
    return vendor, metadata


def build_root_vbmeta(vendor: Path, base: Path, output: Path,
                      work: Path) -> dict[str, object]:
    sys.path.insert(0, str(ROOT / "tools/bootimg"))
    from avbtool import Avb, AvbHashtreeDescriptor, ImageHandler  # type: ignore[import-not-found]

    avb = Avb()
    _, base_header, base_descs, _ = avb._parse_image(ImageHandler(str(base)))
    _, _, vendor_descs, _ = avb._parse_image(ImageHandler(str(vendor)))
    old = [d for d in base_descs if isinstance(d, AvbHashtreeDescriptor) and d.partition_name == "vendor"]
    new = [d for d in vendor_descs if isinstance(d, AvbHashtreeDescriptor) and d.partition_name == "vendor"]
    if len(old) != 1 or len(new) != 1:
        raise RuntimeError(f"Expected one vendor hashtree descriptor in both images; found base={len(old)} new={len(new)}")
    old_desc, new_desc = old[0], new[0]
    if old_desc.image_size != VENDOR_FS_SIZE or new_desc.image_size != VENDOR_FS_SIZE:
        raise RuntimeError(f"Vendor AVB image_size changed unexpectedly: base={old_desc.image_size} new={new_desc.image_size}")
    if old_desc.salt.hex() != VENDOR_SALT or new_desc.salt.hex() != VENDOR_SALT:
        raise RuntimeError("Vendor AVB salt differs from the C21 root descriptor baseline.")
    if new_desc.fec_num_roots != 0:
        raise RuntimeError("C22 vendor descriptor unexpectedly generated FEC data.")
    updated = [new_desc if desc is old_desc else desc for desc in base_descs]
    before_other = [canonical_descriptor(desc) for desc in base_descs if desc is not old_desc]

    if base_header.algorithm_type != 0:
        raise RuntimeError("C21 root vbmeta is not the expected unsigned development AVB image.")
    if base_header.flags != 3:
        raise RuntimeError(f"C21 root vbmeta flags changed from the expected development baseline: {base_header.flags}")
    blob = avb._generate_vbmeta_blob(
        algorithm_name="NONE",
        key_path=None,
        public_key_metadata_path=None,
        descriptors=updated,
        chain_partitions_use_ab=None,
        chain_partitions_do_not_use_ab=None,
        rollback_index=base_header.rollback_index,
        flags=base_header.flags,
        rollback_index_location=base_header.rollback_index_location,
        props=None,
        props_from_file=None,
        kernel_cmdlines=None,
        setup_rootfs_from_kernel=None,
        ht_desc_to_setup=None,
        include_descriptors_from_image=None,
        signing_helper=None,
        signing_helper_with_files=None,
        release_string=base_header.release_string,
        append_to_release_string=None,
        required_libavb_version_minor=base_header.required_libavb_version_minor,
    )
    if len(blob) > 131_072:
        raise RuntimeError(f"New root vbmeta does not fit the 128 KiB partition: {len(blob)}")
    output.write_bytes(blob + b"\0" * (131_072 - len(blob)))
    _, new_header, new_descs, _ = avb._parse_image(ImageHandler(str(output)))
    out_vendor = [d for d in new_descs if isinstance(d, AvbHashtreeDescriptor) and d.partition_name == "vendor"]
    if len(out_vendor) != 1 or canonical_descriptor(out_vendor[0]) != canonical_descriptor(new_desc):
        raise RuntimeError("Generated root vbmeta does not contain the new vendor descriptor.")
    after_other = [canonical_descriptor(desc) for desc in new_descs if not (isinstance(desc, AvbHashtreeDescriptor) and desc.partition_name == "vendor")]
    if before_other != after_other:
        raise RuntimeError("A non-vendor root vbmeta descriptor changed during regeneration.")
    if (new_header.flags, new_header.rollback_index, new_header.rollback_index_location,
            new_header.release_string) != (base_header.flags, base_header.rollback_index,
            base_header.rollback_index_location, base_header.release_string):
        raise RuntimeError("Root vbmeta header metadata changed outside the vendor descriptor update.")
    run(["python3", AVBTOOL, "info_image", "--image", output], log=work / "vbmeta_c22_info.txt")
    return {
        "base_flags": base_header.flags,
        "base_rollback_index": base_header.rollback_index,
        "base_rollback_index_location": base_header.rollback_index_location,
        "release_string": base_header.release_string,
        "vendor_before_root_digest": old_desc.root_digest.hex(),
        "vendor_after_root_digest": new_desc.root_digest.hex(),
        "vendor_image_size": new_desc.image_size,
        "vendor_tree_size": new_desc.tree_size,
        "vendor_fec_num_roots": new_desc.fec_num_roots,
        "other_root_descriptors_unchanged": True,
    }


def build_super(vendor: Path, work: Path) -> Path:
    sparse = work / "super_c22_sparse.img"
    raw = work / "super_c22_raw.tmp.img"
    lpdump_log = work / "lpdump_c22.txt"
    system_img = C21_STAGE / "system_c21.img"
    system_ext_img = C21_SYSTEM_EXT
    mi_ext_img = C1_BASE / "super/avb_images/mi_ext.img"
    odm_img = C1_BASE / "provider_images/odm.img"
    product_img = C1_BASE / "super/avb_images/product.img"
    for path in (system_img, system_ext_img, mi_ext_img, odm_img, product_img):
        require_file(path)
    if system_img.stat().st_size != SYSTEM_SIZE:
        raise RuntimeError(f"C21 system_a image size changed: {system_img.stat().st_size}")
    if system_ext_img.stat().st_size != SYSTEM_EXT_SIZE:
        raise RuntimeError(f"C21 system_ext_a image size changed: {system_ext_img.stat().st_size}")

    args = [
        str(LPMAKE), "--metadata-size", "65536", "--metadata-slots", "3",
        "--device-size", str(DEVICE_SIZE), "--block-size", "4096",
        "--alignment", str(ALIGNMENT), "--virtual-ab", "--sparse",
        "--super-name", "super",
        "--group", f"qti_dynamic_partitions_a:{DEVICE_SIZE}",
        "--group", f"qti_dynamic_partitions_b:{DEVICE_SIZE}",
        "--partition", "mi_ext_a:readonly:202375168:qti_dynamic_partitions_a",
        "--partition", "mi_ext_b:none:0:qti_dynamic_partitions_b",
        "--partition", "odm_a:readonly:36700160:qti_dynamic_partitions_a",
        "--partition", "odm_b:none:0:qti_dynamic_partitions_b",
        "--partition", "product_a:readonly:4387241984:qti_dynamic_partitions_a",
        "--partition", "product_b:none:0:qti_dynamic_partitions_b",
        "--partition", f"system_a:readonly:{SYSTEM_SIZE}:qti_dynamic_partitions_a",
        "--partition", "system_b:none:0:qti_dynamic_partitions_b",
        "--partition", f"system_ext_a:readonly:{SYSTEM_EXT_SIZE}:qti_dynamic_partitions_a",
        "--partition", "system_ext_b:none:0:qti_dynamic_partitions_b",
        "--partition", f"vendor_a:readonly:{VENDOR_SIZE}:qti_dynamic_partitions_a",
        "--partition", "vendor_b:none:0:qti_dynamic_partitions_b",
        "--image", f"mi_ext_a={mi_ext_img}",
        "--image", f"odm_a={odm_img}",
        "--image", f"product_a={product_img}",
        "--image", f"system_a={system_img}",
        "--image", f"system_ext_a={system_ext_img}",
        "--image", f"vendor_a={vendor}",
        "--output", str(sparse),
    ]
    run(args, log=work / "lpmake_c22.log")
    if not sparse.is_file() or sparse.stat().st_size < 5_000_000_000:
        raise RuntimeError("C22 sparse super output is missing or unexpectedly small.")
    run([str(SIMG2IMG), sparse, raw], log=work / "simg2img_c22.log")
    run([str(LPDUMP), raw], log=lpdump_log)
    lp_text = lpdump_log.read_text(encoding="utf-8", errors="replace")
    for expected in ("mi_ext_a", "odm_a", "product_a", "system_a", "system_ext_a", "vendor_a"):
        if expected not in lp_text:
            raise RuntimeError(f"C22 LP metadata missing expected partition {expected}.")
    vendor_block_match = re.search(
        r"(?ms)^  Name: vendor_a\n  Group: (?P<group>[^\n]+)\n"
        r"  Attributes: (?P<attributes>[^\n]+)\n  Extents:\n(?P<extents>(?:    .*\n)*)",
        lp_text,
    )
    if not vendor_block_match or vendor_block_match.group("group") != "qti_dynamic_partitions_a":
        raise RuntimeError("C22 LP metadata does not show vendor_a in the expected A group.")
    extent_match = re.search(
        r"^    0 \.\. (\d+) linear super (\d+)$",
        vendor_block_match.group("extents"),
        re.MULTILINE,
    )
    if not extent_match or (int(extent_match.group(1)) + 1) * 512 != VENDOR_SIZE:
        raise RuntimeError("C22 LP metadata does not show the expected vendor_a size.")
    # The raw conversion is a temporary validation intermediate, not an image
    # required for flashing. Remove only this script-created copy after lpdump.
    raw.unlink()
    return sparse


def main() -> None:
    if not Path("/proc/sys/kernel/osrelease").read_text().lower().find("microsoft") >= 0:
        raise RuntimeError("Run this builder inside WSL Ubuntu, not Windows Python.")
    if not ROOT.is_dir():
        raise FileNotFoundError(ROOT)
    if C22_DIR.exists() or C22_STAGE.exists():
        raise FileExistsError("C22 run1 output already exists; refusing to overwrite it.")
    if not all(path.is_file() for path in (LPMAKE, SIMG2IMG, LPDUMP, AVBTOOL)):
        raise FileNotFoundError("Required project LP/AVB build tools are unavailable.")
    if shutil.which("patchelf") is None or shutil.which("debugfs") is None or shutil.which("e2fsck") is None:
        raise RuntimeError("Required WSL tools (patchelf, debugfs, e2fsck) are unavailable.")
    require_file(C1_VENDOR)
    require_file(K40_DEPS / "vulkan.adreno.so")
    c21_manifest = verify_c21_inputs()
    C22_DIR.mkdir(parents=True, exist_ok=False)
    C22_IMAGES.mkdir(parents=True, exist_ok=False)
    C22_STAGE.mkdir(parents=True, exist_ok=False)

    say("[C22] Private vendor copy and isolated K40 Vulkan UMD preparation")
    vendor, vendor_metadata = prepare_vendor(C1_VENDOR, C22_STAGE)

    say("[C22] Regenerating only the root vbmeta vendor hashtree descriptor")
    vbmeta_out = C22_IMAGES / "vbmeta.img"
    vbmeta_metadata = build_root_vbmeta(vendor, C21_IMAGES / "vbmeta.img", vbmeta_out, C22_STAGE)

    say("[C22] Repacking the same A-slot LP inputs with the patched vendor_a")
    sparse_super = build_super(vendor, C22_STAGE)
    super_out = C22_IMAGES / "super.img"
    shutil.copy2(sparse_super, super_out)

    # These images are intentionally byte-identical to C21.
    inherited = ("boot.img", "vendor_boot.img", "dtbo.img", "vbmeta_system.img")
    for name in inherited:
        shutil.copy2(C21_IMAGES / name, C22_IMAGES / name)
        expected = c21_manifest["images"][name]
        if sha256(C22_IMAGES / name) != expected["sha256"].upper():
            raise RuntimeError(f"C22 inherited image changed unexpectedly: {name}")

    image_entries: dict[str, dict[str, object]] = {}
    for name in IMAGE_NAMES:
        path = C22_IMAGES / name
        require_file(path)
        image_entries[name] = {"bytes": path.stat().st_size, "sha256": sha256(path)}

    manifest = {
        "candidate": CANDIDATE,
        "base": EXPECTED_C21,
        "changes": [
            "Replace vendor_a's Vulkan ICD with the cached K40 OS4.0.0.8 Android 17 vulkan.adreno.so.",
            "Add K40 Vulkan-only GSL, Adreno Utils, glnext, and qgl libraries; rename GSL/Adreno/glnext SONAMEs and patch only K40 Vulkan DT_NEEDED references.",
            "Keep the original thyme/C1 libgsl.so, libadreno_utils.so, libllvm-glnext.so, EGL, GLES, Gralloc, HWC, kernel, and device-specific boot assets unchanged.",
            "Regenerate the vendor AVB hashtree without FEC and replace only the vendor descriptor in root vbmeta.img; retain vbmeta_system.img.",
        ],
        "evidence_basis": [
            "C21 pmsg shows repeated SurfaceFlinger SkiaVk RenderEngine initialization fatal.",
            "C21 actual provider vendor Vulkan ICD imports GSL APIs missing from its actual provider libgsl.so.",
            "K40 Android 17 Vulkan ICD has a matching GSL/LLVM UMD set; same-name replacement would remove exports used by C21 EGL/GLES, so C22 isolates SONAMEs.",
        ],
        "limits": [
            "This is a host-built compatibility experiment; K40 Vulkan UMD operation on thyme Linux 4.19/KGSL is unverified.",
            "The adjacent graphicsengine Vulkan crash is not claimed to be the SurfaceFlinger cause.",
            "No SELinux, EGL routing, fstab, encryption, system, userdata, metadata, or bootloader change is included.",
        ],
        "flash_scope_prepared": ["super", "vbmeta_a"],
        "inherited_from_c21": list(inherited) + ["system_a", "system_ext_a", "mi_ext_a", "odm_a", "product_a"],
        "images": image_entries,
        "vendor_input_and_patch": vendor_metadata,
        "root_vbmeta_update": vbmeta_metadata,
        "lp_layout": {
            "super_device_size": DEVICE_SIZE,
            "alignment": ALIGNMENT,
            "vendor_a_size": VENDOR_SIZE,
        "layout_source": "Candidate 21 lpmake geometry; exact system_ext_a extracted from C21 super, unchanged logical inputs except vendor_a",
            "lpdump": str(C22_STAGE / "lpdump_c22.txt"),
        },
        "note": "Candidate 22 is not flashed by the build script. The paired flash script only writes super and vbmeta_a and never reboots.",
    }
    manifest_path = C22_IMAGES / "BUILD_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                             encoding="utf-8", newline="\n")

    report_lines = [
        "# Candidate 22 build result",
        "",
        f"- Candidate: {CANDIDATE}",
        f"- Base: {EXPECTED_C21}",
        "- Device operations: none; host build only.",
        "- Flash scope prepared: `super`, `vbmeta_a`.",
        "- C21 EGL/GLES and hardware-specific boot assets retained.",
        "- C22 replaces the Vulkan ICD/support set with isolated K40 Android 17 UMD libraries.",
        "- Vendor ext4 check: e2fsck read-only passed.",
        "- Vendor metadata: root:root, mode 0644, same_process_hal_file xattr verified.",
        "- Vendor AVB: regenerated with same partition size/salt and no FEC.",
        "- Root vbmeta: only vendor hashtree descriptor changed; all other descriptors and header flags/index preserved.",
        "- LP: same geometry and A-slot logical partition layout; lpdump passed.",
        "",
        "| Image | Bytes | SHA-256 |",
        "|---|---:|---|",
    ]
    for name in IMAGE_NAMES:
        entry = image_entries[name]
        report_lines.append(f"| `{name}` | {entry['bytes']} | `{entry['sha256']}` |")
    (C22_DIR / "BUILD_REPORT.md").write_text("\n".join(report_lines) + "\n",
                                           encoding="utf-8", newline="\n")
    say(f"[C22] Build complete: {C22_IMAGES}")
    for name in IMAGE_NAMES:
        say(f"  {name}: {image_entries[name]['bytes']} bytes SHA256={image_entries[name]['sha256']}")
    say(f"[C22] Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
