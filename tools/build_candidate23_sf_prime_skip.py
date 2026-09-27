#!/usr/bin/env python3
"""Build C23 by bypassing only SurfaceFlinger's optional shader-cache prime.

Run inside the Ubuntu WSL distribution. C23 inherits Candidate 22's vendor
Vulkan UMD and all logical partition inputs; it changes one system property:
service.sf.prime_shader_cache=0. It never communicates with a device.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WSL_BUILD = Path("/root/10s_os4_build")
C1 = WSL_BUILD / "thyme_xiaomi15_os4_first_boot_candidate_1"
C21 = WSL_BUILD / "c21_k40_vk_renderengine_20260927_run1"
C22 = WSL_BUILD / "c22_k40_vulkan_umd_20260927_run5"
C22_MIGRATION = WSL_BUILD / "c22_k40_vulkan_migration_20260927"
C23_WORK = WSL_BUILD / "c23_sf_prime_skip_20260927_run4"

C22_IMAGES = ROOT / "work/stage_l_thyme_os4_candidate_22_k40_vk_umd_run5/images"
C23_DIR = ROOT / "work/stage_m_thyme_os4_candidate_23_sf_prime_skip_run4"
C23_IMAGES = C23_DIR / "images"

MKFS = ROOT / "tools/erofs-utils/wsl/mkfs.erofs"
FSCK = ROOT / "tools/erofs-utils/wsl/fsck.erofs"
DUMP = ROOT / "tools/erofs-utils/wsl/dump.erofs"
LPMAKE = ROOT / "tools/android-tools-static/linux/android-tools-static/lpmake"
SIMG2IMG = ROOT / "tools/android-tools-static/linux/android-tools-static/simg2img"
LPDUMP = ROOT / "tools/android-tools-static/linux/android-tools-static/lpdump"
AVBTOOL = ROOT / "tools/bootimg/avbtool.py"

SYSTEM_SIZE = 1_092_616_192
SYSTEM_EXT_SIZE = 942_669_824
VENDOR_SIZE = 1_510_998_016
DEVICE_SIZE = 9_126_805_504
ALIGNMENT = 1_048_576
SYSTEM_UUID = "6f1b5f0e-8f73-4e28-aefe-8ee48d2d8b41"
SYSTEM_SALT = "c5ffc2c51fef1864ad27e6903e582f52611121819811b66eb40f6ea9b60350c5"
PROPERTY = "service.sf.prime_shader_cache=0"
EXPECTED_C22 = "Candidate 22 K40 Android 17 Vulkan UMD ABI compatibility stack"
EXPECTED_C21 = "Candidate 21 K40 Skia Vulkan RenderEngine profile"
CANDIDATE = "Candidate 23 SurfaceFlinger shader-cache prime bypass"
IMAGE_NAMES = ("boot.img", "vendor_boot.img", "dtbo.img", "vbmeta.img",
               "vbmeta_system.img", "super.img")


def say(message: str) -> None:
    print(message, flush=True)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest().upper()


def require_file(path: Path, expected_size: int | None = None) -> None:
    if not path.is_file():
        raise FileNotFoundError(path)
    if expected_size is not None and path.stat().st_size != expected_size:
        raise RuntimeError(f"Unexpected size for {path}: {path.stat().st_size}, expected {expected_size}")


def run(args: list[str | os.PathLike[str]], *, log: Path | None = None) -> str:
    cmd = [os.fspath(x) for x in args]
    result = subprocess.run(cmd, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, errors="replace")
    output = result.stdout or ""
    if log:
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(output, encoding="utf-8", newline="\n")
    if result.returncode:
        say(f"FAILED ({result.returncode}): {' '.join(cmd)}")
        if output:
            say(output[-12000:])
        raise subprocess.CalledProcessError(result.returncode, cmd, output)
    return output


def descriptor_json(desc: object) -> str:
    def norm(v: object) -> object:
        if isinstance(v, bytes):
            return {"bytes_hex": v.hex()}
        if isinstance(v, (str, int, float, bool)) or v is None:
            return v
        if isinstance(v, (tuple, list)):
            return [norm(x) for x in v]
        if isinstance(v, dict):
            return {str(k): norm(x) for k, x in v.items()}
        return repr(v)
    return json.dumps({"type": type(desc).__name__, "fields": norm(vars(desc))},
                      sort_keys=True, separators=(",", ":"))


def check_c22_manifest() -> dict[str, object]:
    manifest_path = C22_IMAGES / "BUILD_MANIFEST.json"
    require_file(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("candidate") != EXPECTED_C22 or manifest.get("base") != EXPECTED_C21:
        raise RuntimeError("C22 manifest is not the expected source baseline.")
    if set(manifest.get("images", {})) != set(IMAGE_NAMES):
        raise RuntimeError("C22 manifest does not describe the complete six-image set.")
    # Verify only the five directly inherited small images. The 7.7 GB C22
    # super is not read/rehash-verified; C23 reuses its audited source inputs.
    inherited: dict[str, dict[str, object]] = {}
    for name in ("boot.img", "vendor_boot.img", "dtbo.img", "vbmeta.img", "vbmeta_system.img"):
        path = C22_IMAGES / name
        require_file(path)
        entry = manifest["images"][name]
        got_hash = sha256(path)
        if path.stat().st_size != int(entry["bytes"]) or got_hash != str(entry["sha256"]).upper():
            raise RuntimeError(f"C22 inherited image does not match its manifest: {name}")
        inherited[name] = {"bytes": path.stat().st_size, "sha256": got_hash}
    require_file(C22_IMAGES / "super.img", int(manifest["images"]["super.img"]["bytes"]))
    return {"manifest": manifest, "inherited": inherited}


def build_system(tree: Path, stage: Path) -> Path:
    prop = tree / "system/build.prop"
    require_file(prop)
    text = prop.read_text(encoding="utf-8")
    key = PROPERTY.split("=", 1)[0]
    lines = text.splitlines()
    if any(line.split("=", 1)[0] == key for line in lines if "=" in line):
        raise RuntimeError(f"C22 system/build.prop already defines {key}; refusing duplicate/overwrite.")
    if key.encode() in (tree / "system/etc/init/surfaceflinger.rc").read_bytes():
        raise RuntimeError("Unexpected init action overrides the C23 shader-prime property.")
    prop.write_text(text.rstrip("\n") + "\n" + PROPERTY + "\n", encoding="utf-8", newline="\n")

    fs_config = stage / "system_fs_config_c23"
    file_contexts = C1 / "configs_retained/system/file_contexts"
    source_fs_config = C1 / "configs_retained/system/fs_config"
    require_file(source_fs_config)
    require_file(file_contexts)
    # Reproduce the C14/C15 fs_config derivation from the retained donor
    # mapping and this exact system tree. The old C15 scratch file was removed
    # by host cleanup, so do not substitute a similarly named file blindly.
    import stat
    source_lines = source_fs_config.read_text(encoding="utf-8").splitlines()
    rebased: list[str] = []
    for line in source_lines:
        fields = line.split(maxsplit=1)
        if not fields or fields[0] == "/":
            rebased.append(line)
        else:
            rebased.append("system/" + fields[0].lstrip("/") + (" " + fields[1] if len(fields) > 1 else ""))
    known = {line.split()[0].lstrip("/") for line in rebased
             if line.strip() and not line.lstrip().startswith("#")}
    added: list[str] = []
    for entry in sorted(tree.rglob("*"), key=lambda p: p.relative_to(tree).as_posix()):
        relative = "system/" + entry.relative_to(tree).as_posix()
        if relative in known:
            continue
        st = entry.lstat()
        added.append(f"{relative} {st.st_uid} {st.st_gid} {stat.S_IMODE(st.st_mode):04o}")
        known.add(relative)
    fs_config.write_text("\n".join(rebased + added) + "\n", encoding="utf-8", newline="\n")
    raw = stage / "system_c23.raw.erofs"
    image = stage / "system_c23.img"
    run([MKFS, "-zlz4hc", "-T", "0", "-U", SYSTEM_UUID, "--mount-point=/system",
         f"--fs-config-file={fs_config}", f"--file-contexts={file_contexts}", raw, tree],
        log=stage / "mkfs_system_c23.log")
    run([FSCK, "-d0", raw], log=stage / "fsck_system_c23.log")
    shutil.copy2(raw, image)
    run(["python3", AVBTOOL, "add_hashtree_footer", "--image", image,
         "--partition_size", str(SYSTEM_SIZE), "--partition_name", "system",
         "--hash_algorithm", "sha256", "--salt", SYSTEM_SALT,
         "--algorithm", "NONE", "--do_not_generate_fec"],
        log=stage / "avb_system_c23.log")
    require_file(image, SYSTEM_SIZE)
    prop_dump = stage / "build.prop.c23.txt"
    run([DUMP, "--cat", "--path=/system/build.prop", raw], log=prop_dump)
    dumped = prop_dump.read_text(encoding="utf-8", errors="replace").splitlines()
    if dumped.count(PROPERTY) != 1:
        raise RuntimeError("C23 property did not survive the final EROFS image exactly once.")
    for retained in ("debug.renderengine.vulkan=true", "debug.hwui.renderer=skiavk",
                     "debug.renderengine.backend=skiavkthreaded",
                     "persist.graphics.egl=angle",
                     "ro.surface_flinger.default_composition_pixel_format=2"):
        if dumped.count(retained) != 1:
            raise RuntimeError(f"C22 property was not preserved exactly once: {retained}")
    return image


def rebuild_vbmeta_system(system_image: Path, out: Path, stage: Path) -> dict[str, object]:
    import sys
    sys.path.insert(0, str(ROOT / "tools/bootimg"))
    from avbtool import Avb, AvbHashtreeDescriptor, ImageHandler

    base = C22_IMAGES / "vbmeta_system.img"
    require_file(base, 131072)
    avb = Avb()
    _, base_header, base_descs, _ = avb._parse_image(ImageHandler(str(base)))
    _, _, sys_descs, _ = avb._parse_image(ImageHandler(str(system_image)))
    new_system = next(d for d in sys_descs if isinstance(d, AvbHashtreeDescriptor)
                      and d.partition_name == "system")
    old_system = next(d for d in base_descs if isinstance(d, AvbHashtreeDescriptor)
                      and d.partition_name == "system")
    if new_system.image_size != old_system.image_size or new_system.partition_name != old_system.partition_name:
        raise RuntimeError("New system descriptor is incompatible with the existing vbmeta_system descriptor.")
    new_descs = [new_system if isinstance(d, AvbHashtreeDescriptor) and d.partition_name == "system" else d
                 for d in base_descs]
    blob = avb._generate_vbmeta_blob(
        algorithm_name="NONE", key_path=None, public_key_metadata_path=None,
        descriptors=new_descs, chain_partitions_use_ab=None,
        chain_partitions_do_not_use_ab=None, rollback_index=base_header.rollback_index,
        flags=base_header.flags, rollback_index_location=base_header.rollback_index_location,
        props=None, props_from_file=None, kernel_cmdlines=None,
        setup_rootfs_from_kernel=None, ht_desc_to_setup=None,
        include_descriptors_from_image=None, signing_helper=None,
        signing_helper_with_files=None, release_string=base_header.release_string,
        append_to_release_string=None,
        required_libavb_version_minor=base_header.required_libavb_version_minor)
    if len(blob) > 131072:
        raise RuntimeError("C23 vbmeta_system blob exceeds the existing partition image size.")
    out.write_bytes(blob + b"\0" * (131072 - len(blob)))
    _, new_header, check_descs, _ = avb._parse_image(ImageHandler(str(out)))
    old_by_name = {d.partition_name: d for d in base_descs if isinstance(d, AvbHashtreeDescriptor)}
    new_by_name = {d.partition_name: d for d in check_descs if isinstance(d, AvbHashtreeDescriptor)}
    if set(new_by_name) != set(old_by_name) or new_by_name["system"].root_digest != new_system.root_digest:
        raise RuntimeError("C23 vbmeta_system hashtree descriptor validation failed.")
    for name in old_by_name:
        if name != "system" and descriptor_json(old_by_name[name]) != descriptor_json(new_by_name[name]):
            raise RuntimeError(f"C23 unexpectedly changed the {name} hashtree descriptor.")
    if (new_header.flags, new_header.rollback_index, new_header.rollback_index_location,
            new_header.release_string) != (base_header.flags, base_header.rollback_index,
            base_header.rollback_index_location, base_header.release_string):
        raise RuntimeError("C23 vbmeta_system header fields changed unexpectedly.")
    run(["python3", AVBTOOL, "info_image", "--image", out], log=stage / "vbmeta_system_c23_info.txt")
    return {
        "base_sha256": sha256(base),
        "flags": new_header.flags,
        "rollback_index": new_header.rollback_index,
        "rollback_index_location": new_header.rollback_index_location,
        "system_image_size": new_system.image_size,
        "system_root_digest": new_system.root_digest.hex(),
        "unchanged_other_descriptors": sorted(name for name in old_by_name if name != "system"),
    }


def build_super(system_image: Path, stage: Path) -> tuple[Path, dict[str, object]]:
    vendor = C22 / "vendor_c22.img"
    system_ext = C22_MIGRATION / "c21_system_ext_a_from_super_20260927/system_ext_a.img"
    mi_ext = C1 / "super/avb_images/mi_ext.img"
    odm = C1 / "provider_images/odm.img"
    product = C1 / "super/avb_images/product.img"
    expected = {vendor: VENDOR_SIZE, system_ext: SYSTEM_EXT_SIZE,
                mi_ext: 202_375_168, odm: 35_758_080, product: 4_387_241_984}
    input_hashes: dict[str, dict[str, object]] = {}
    for path, size in expected.items():
        require_file(path, size)
        input_hashes[path.name] = {"bytes": size, "sha256": sha256(path)}

    sparse = C23_IMAGES / "super.img"
    raw = stage / "super_c23_raw_validate.img"
    args = [
        LPMAKE, "--metadata-size", "65536", "--metadata-slots", "3",
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
        "--image", f"mi_ext_a={mi_ext}", "--image", f"odm_a={odm}",
        "--image", f"product_a={product}", "--image", f"system_a={system_image}",
        "--image", f"system_ext_a={system_ext}", "--image", f"vendor_a={vendor}",
        "--output", sparse,
    ]
    run(args, log=stage / "lpmake_c23.log")
    if sparse.stat().st_size < 5_000_000_000:
        raise RuntimeError("C23 sparse super output is unexpectedly small.")
    run([SIMG2IMG, sparse, raw], log=stage / "simg2img_c23.log")
    lpdump_log = stage / "lpdump_c23.txt"
    lp_text = run([LPDUMP, raw], log=lpdump_log)
    for part in ("mi_ext_a", "odm_a", "product_a", "system_a", "system_ext_a", "vendor_a"):
        if part not in lp_text:
            raise RuntimeError(f"C23 LP metadata omits expected partition {part}.")
    for part, expected_size in (("system_a", SYSTEM_SIZE), ("system_ext_a", SYSTEM_EXT_SIZE),
                                ("vendor_a", VENDOR_SIZE)):
        match = __import__("re").search(
            rf"(?ms)^  Name: {part}\n  Group: [^\n]+\n  Attributes: [^\n]+\n  Extents:\n(?P<extents>(?:    .*\n)*)",
            lp_text)
        extent = __import__("re").search(r"(?m)^    0 \.\. (\d+) linear super (\d+)$",
                                         match.group("extents")) if match else None
        if not extent or (int(extent.group(1)) + 1) * 512 != expected_size:
            raise RuntimeError(f"C23 LP extent size mismatch for {part}.")
    raw.unlink()
    return sparse, input_hashes


def main() -> None:
    if "microsoft" not in Path("/proc/sys/kernel/osrelease").read_text().lower():
        raise RuntimeError("Run this builder inside WSL Ubuntu, not native Windows Python.")
    if C23_DIR.exists() or C23_WORK.exists():
        raise FileExistsError("C23 run4 already exists; refusing to overwrite any prior output.")
    for tool in (MKFS, FSCK, DUMP, LPMAKE, SIMG2IMG, LPDUMP, AVBTOOL):
        require_file(tool)
    for executable in (MKFS, FSCK, DUMP, LPMAKE, SIMG2IMG, LPDUMP):
        if not os.access(executable, os.X_OK):
            raise PermissionError(f"Build tool is not executable: {executable}")

    c22_info = check_c22_manifest()
    c22_manifest = c22_info["manifest"]
    C23_DIR.mkdir(parents=True, exist_ok=False)
    C23_IMAGES.mkdir(parents=True, exist_ok=False)
    C23_WORK.mkdir(parents=True, exist_ok=False)
    base_tree = C21 / "system_tree"
    require_file(base_tree / "system/build.prop")
    tree = C23_WORK / "system_tree"
    shutil.copytree(base_tree, tree, symlinks=True)

    say("[C23] Rebuilding system with only service.sf.prime_shader_cache=0")
    system_image = build_system(tree, C23_WORK)
    say("[C23] Replacing only system descriptor in vbmeta_system")
    vbmeta_system_info = rebuild_vbmeta_system(system_image,
                                              C23_IMAGES / "vbmeta_system.img", C23_WORK)
    say("[C23] Repacking LP with C22 vendor UMD and the same logical partition sources")
    super_image, lp_inputs = build_super(system_image, C23_WORK)

    inherited = ("boot.img", "vendor_boot.img", "dtbo.img", "vbmeta.img")
    for name in inherited:
        shutil.copy2(C22_IMAGES / name, C23_IMAGES / name)
        if sha256(C23_IMAGES / name) != c22_info["inherited"][name]["sha256"]:
            raise RuntimeError(f"C23 inherited image copy mismatch: {name}")

    entries: dict[str, dict[str, object]] = {}
    for name in IMAGE_NAMES:
        path = C23_IMAGES / name
        require_file(path)
        entries[name] = {"bytes": path.stat().st_size, "sha256": sha256(path)}

    manifest = {
        "candidate": CANDIDATE,
        "base": EXPECTED_C22,
        "changes": [
            "system/build.prop: set service.sf.prime_shader_cache=0 to bypass the optional RenderEngine shader-cache prime that produced the C22 output-buffer GPU-usage fatal.",
        ],
        "evidence_basis": [
            "C22 pmsg recorded 89 identical SurfaceFlinger aborts with output buffer not gpu writeable; the stack traversed Cache::primeShaderCache and SkiaRenderEngine::primeCache.",
            "Android 17 upstream SurfaceFlinger gates primeCache() on service.sf.prime_shader_cache, defaulting to 1; C23 sets it to 0 before SurfaceFlinger starts.",
        ],
        "limits": [
            "This is a diagnostic bypass of optional startup shader prewarming, not a proven fix for allocator/GraphicBuffer usage mismatches during regular composition.",
            "C22 logs did not identify the actual Vulkan ICD/backend, so successful selection of the K40 Vulkan UMD is not claimed.",
        ],
        "retained_from_c22": [
            "C22 K40 Android 17 Vulkan ICD and isolated SONAME UMD/GSL/LLVM dependencies in vendor_a.",
            "C13-C22 boot, SELinux, BPF, ION, storage, RenderEngine and hardware-specific thyme changes.",
            "Thyme kernel, boot, vendor_boot, dtbo, root vbmeta, system_ext, product, odm and mi_ext inputs retained; userdata and metadata are not modified.",
        ],
        "checks": [
            "C22 inherited boot/vendor_boot/dtbo/vbmeta/vbmeta_system files checked against the C22 manifest (C22 super was not rehashed).",
            "C23 final EROFS fsck passed; build.prop was read back from the final EROFS and retained C20-C21 properties plus the C23 property were asserted exactly once.",
            "New system AVB hashtree descriptor is the only vbmeta_system descriptor replaced; product/system_ext descriptors and header metadata were preserved.",
            "LP was rebuilt with the C22 vendor UMD and prior A logical partition geometry; lpdump checked expected partitions and extents.",
        ],
        "flash_scope_prepared": ["super", "vbmeta_system_a"],
        "inherited_images_checked": c22_info["inherited"],
        "logical_input_hashes": lp_inputs,
        "vbmeta_system_update": vbmeta_system_info,
        "images": entries,
    }
    manifest_path = C23_IMAGES / "BUILD_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                             encoding="utf-8", newline="\n")
    report = [
        "# Candidate 23 build result", "",
        f"- Candidate: {CANDIDATE}", f"- Base: {EXPECTED_C22}",
        "- Change: `service.sf.prime_shader_cache=0` in system/build.prop; no other config or binaries changed.",
        "- The change skips only optional SurfaceFlinger startup shader-cache priming; underlying output-buffer usage mismatch remains unproven/unfixed.",
        "- C22 K40 Vulkan UMD/vendor set and previous system/SELinux/storage changes retained.",
        "- EROFS fsck, property readback, system AVB descriptor, vbmeta_system descriptor preservation and LP extent checks passed.",
        "- Flash scope prepared: `super`, `vbmeta_system_a`. The builder does not contact a device.", "",
        "| Image | Bytes | SHA-256 |", "|---|---:|---|",
    ]
    report += [f"| `{name}` | {entries[name]['bytes']} | `{entries[name]['sha256']}` |" for name in IMAGE_NAMES]
    (C23_DIR / "BUILD_REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8", newline="\n")
    say(f"[C23] Build complete: {C23_IMAGES}")
    for name in IMAGE_NAMES:
        say(f"  {name}: {entries[name]['bytes']} bytes SHA256={entries[name]['sha256']}")


if __name__ == "__main__":
    main()
