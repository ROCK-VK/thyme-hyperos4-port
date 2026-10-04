#!/usr/bin/env python3
"""Build Candidate 40: MediaProfiles Single-Variable Property Fix for Snapdragon 870.

Inherits Candidate 39-DIAG (repacked runtime apex, C39 linker64, c32 canary).
Modifications:
STRICTLY SINGLE-VARIABLE:
1. In system/build.prop:
   Append: ro.media.xml_variant.codecs=_V1_0
   Directly guides Xiaomi libmedia.so to locate /vendor/etc/media_profiles_V1_0.xml.
   No additional XML added.
   No modifications to libmedia.so, SELinux, or linker64.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WSL_BUILD = Path("/path/to/thyme-os4-build")

C31_STAGE = ROOT / "work/stage_c31_diag_zygote_critical_20261001_run1"
C31_IMAGES = C31_STAGE / "images"

C39_STAGE = ROOT / "work/stage_c39_diag_runtime_abort_20261003"
C39_IMAGES = C39_STAGE / "images"
C39_WORK = WSL_BUILD / "c39_diag_runtime_abort_20261003"
C39_TREE = C39_WORK / "system_tree"

C40_STAGE = ROOT / "work/stage_c40_media_profiles_variant_20261003"
C40_IMAGES = C40_STAGE / "images"
C40_WORK = WSL_BUILD / "c40_media_profiles_variant_20261003"
C40_TREE = C40_WORK / "system_tree"
REPORT_DIR = ROOT / "reports/c40_candidate40_build_20261003"

IMAGE_NAMES = ("super.img", "vbmeta_system.img")
INHERITED_SMALL = ("boot.img", "vendor_boot.img", "dtbo.img", "vbmeta.img")
CANDIDATE = "Candidate 40 MediaProfiles Single-Variable Property Fix"
BASE_CANDIDATE = "Candidate 39-DIAG Real Zygote ART Runtime::Abort Level-2 Caller and Message in-situ capture"

def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load build module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()

def require_file(path: Path, size: int | None = None) -> None:
    if not path.is_file():
        raise FileNotFoundError(path)
    if size is not None and path.stat().st_size != size:
        raise RuntimeError(f"Unexpected size for {path}: {path.stat().st_size} != {size}")

def run(args: list[str | os.PathLike[str]], log: Path | None = None) -> str:
    command = [os.fspath(value) for value in args]
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, errors="replace")
    output = result.stdout or ""
    if log is not None:
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(output, encoding="utf-8", newline="\n")
    if result.returncode:
        print(f"FAILED ({result.returncode}): {' '.join(command)}", flush=True)
        if output:
            print(output[-12000:], flush=True)
        raise subprocess.CalledProcessError(result.returncode, command, output)
    return output

def run_bytes(args: list[str | os.PathLike[str]]) -> bytes:
    command = [os.fspath(value) for value in args]
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        raise subprocess.CalledProcessError(result.returncode, command,
            result.stderr.decode("utf-8", errors="replace"))
    return result.stdout

def check_space() -> dict[str, float]:
    storage: dict[str, float] = {}
    for drive, mount in (("C", "/mnt/c"), ("D", "/mnt/d"), ("E", "/mnt/e")):
        usage = shutil.disk_usage(mount)
        free_gib = round(usage.free / (1024 ** 3), 2)
        storage[f"{drive}_free_gib"] = free_gib
        print(f"[SPACE] {drive}: free={free_gib:.2f} GiB", flush=True)
        if usage.free < 50 * 1024 ** 3:
            raise RuntimeError(f"{drive}: below 50 GiB project gate; no build or extraction started.")
    return storage

def load_c39_manifest() -> dict[str, object]:
    path = C39_IMAGES / "BUILD_MANIFEST.json"
    require_file(path)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("candidate") != BASE_CANDIDATE:
        raise RuntimeError("C39 manifest candidate name does not match expected baseline.")
    for name in INHERITED_SMALL:
        item = manifest["inherited_images"][name]
        require_file(C31_IMAGES / name, int(item["bytes"]))
        if sha256(C31_IMAGES / name) != str(item["sha256"]).upper():
            raise RuntimeError(f"C31 inherited image mismatch: {name}")
    return manifest

def assemble_c40_system_tree(stage: Path) -> dict[str, object]:
    print("\n[TREE] Assembling C40 system_tree from C39 baseline...")
    if C40_TREE.exists():
        shutil.rmtree(C40_TREE)
    C40_WORK.mkdir(parents=True, exist_ok=True)
    
    # Copy baseline tree preserving permissions and symlinks
    run(["cp", "-a", str(C39_TREE), str(C40_TREE)])

    # Append single property to system/build.prop
    prop_path = C40_TREE / "system/build.prop"
    require_file(prop_path)
    prop_content = prop_path.read_text(encoding="utf-8")
    addition = "\n# Candidate 40: MediaProfiles single-variable variant for Snapdragon 870 Treble media_profiles_V1_0.xml\nro.media.xml_variant.codecs=_V1_0\n"
    prop_path.write_text(prop_content + addition, encoding="utf-8", newline="\n")

    # Readback verify
    verify_lines = [l for l in prop_path.read_text(encoding="utf-8").splitlines() if "ro.media.xml_variant.codecs" in l]
    print(f"[TREE] Verified property line:\n  {verify_lines}")
    if verify_lines != ["ro.media.xml_variant.codecs=_V1_0"]:
        raise RuntimeError(f"Unexpected property verification: {verify_lines}")

    # Verify system_tree diff between C39 and C40: MUST BE STRICTLY system/build.prop ONLY
    diff_res = subprocess.run(["diff", "--no-dereference", "-r", "-q", str(C39_TREE), str(C40_TREE)],
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    diff_lines = [l.strip() for l in diff_res.stdout.splitlines() if l.strip()]
    print(f"[TREE] Diff between C39 and C40 system_tree ({len(diff_lines)} files):")
    for d in diff_lines:
        print(f"  {d}")
    if len(diff_lines) != 1 or "system/build.prop" not in diff_lines[0]:
        raise RuntimeError(f"Strict single-variable violation! Unexpected diffs: {diff_lines}")

    return {
        "modified_files": ["system/build.prop"],
        "injected_property": "ro.media.xml_variant.codecs=_V1_0",
        "diff_count": len(diff_lines)
    }

def build_system(c23, stage: Path) -> tuple[Path, dict[str, object]]:
    print("\n[SYSTEM] Building system_c40.img with EROFS and AVB footer...")
    base_contexts = c23.C1 / "configs_retained/system/file_contexts"
    fs_config_source = c23.C1 / "configs_retained/system/fs_config"
    require_file(base_contexts)
    require_file(fs_config_source)

    additions = (
        "/system/system/bin/c25_bootdiag u:object_r:shell_exec:s0",
        "/system/system/etc/init/c25_bootdiag\\.rc u:object_r:system_file:s0",
        "/system/system/bin/c30_diag u:object_r:c30_diag_exec:s0",
        "/system/system/etc/init/c30_diag\\.rc u:object_r:system_file:s0",
        "/system/system/bin/c32_zygote_canary u:object_r:zygote_exec:s0",
    )
    contexts = base_contexts.read_text(encoding="utf-8").rstrip("\n") + "\n" + "\n".join(additions) + "\n"
    contexts_path = stage / "system_file_contexts_c40"
    contexts_path.write_text(contexts, encoding="utf-8", newline="\n")

    source_lines = fs_config_source.read_text(encoding="utf-8").splitlines()
    rebased: list[str] = []
    for line in source_lines:
        fields = line.split(maxsplit=1)
        rebased.append(line if not fields or fields[0] == "/" else
                       "system/" + fields[0].lstrip("/") +
                       (" " + fields[1] if len(fields) > 1 else ""))
    known = {line.split()[0].lstrip("/") for line in rebased
             if line.strip() and not line.lstrip().startswith("#")}
    added: list[str] = []
    for item in sorted(C40_TREE.rglob("*"), key=lambda p: p.relative_to(C40_TREE).as_posix()):
        rel = "system/" + item.relative_to(C40_TREE).as_posix()
        if rel in known:
            continue
        st = item.lstat()
        added.append(f"{rel} {st.st_uid} {st.st_gid} {stat.S_IMODE(st.st_mode):04o}")
        known.add(rel)
    fs_config = stage / "system_fs_config_c40"
    fs_config.write_text("\n".join(rebased + added) + "\n", encoding="utf-8", newline="\n")

    raw = stage / "system_c40.raw.erofs"
    image = C40_IMAGES / "system_c40.img"

    c23.run([c23.MKFS, "-zlz4hc", "-T", "0", "-U", c23.SYSTEM_UUID,
             "--mount-point=/system", f"--fs-config-file={fs_config}",
             f"--file-contexts={contexts_path}", raw, C40_TREE],
            log=stage / "mkfs_system_c40.log")
    c23.run([c23.FSCK, "-d0", raw], log=stage / "fsck_system_c40.log")
    shutil.copy2(raw, image)
    c23.run(["python3", str(c23.AVBTOOL), "add_hashtree_footer", "--image", str(image),
             "--partition_size", str(c23.SYSTEM_SIZE), "--partition_name", "system",
             "--hash_algorithm", "sha256", "--salt", c23.SYSTEM_SALT,
             "--algorithm", "NONE", "--do_not_generate_fec"],
             log=stage / "avb_system_c40.log")
    require_file(image, c23.SYSTEM_SIZE)

    # Readback checks
    expected_readbacks = {
        "/system/etc/init/hw/init.rc": ("setprop init.svc_debug.no_fatal.zygote true", "THYME_C32_CANARY event=trigger"),
        "/system/apex/com.android.runtime.apex": (),
        "/system/bin/c32_zygote_canary": (),
        "/system/build.prop": ("ro.media.xml_variant.codecs=_V1_0",),
    }
    readbacks = {}
    for path, tokens in expected_readbacks.items():
        data = run_bytes([c23.DUMP, "--cat", f"--path={path}", raw])
        content = data.decode("utf-8", errors="replace")
        for t in tokens:
            if t not in content:
                raise RuntimeError(f"Token {t} missing in {path} readback!")
        readbacks[path] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest().upper()}

    verify_link = image.parent / "system.img"
    if verify_link.exists() or verify_link.is_symlink():
        verify_link.unlink()
    verify_link.symlink_to(image)
    try:
        c23.run(["python3", str(c23.AVBTOOL), "verify_image", "--image", str(image)],
                log=stage / "avb_verify_system_c40.log")
    finally:
        verify_link.unlink(missing_ok=True)

    sys_hash = sha256(image)
    print(f"[SYSTEM] system_c40.img successfully built and verified: {sys_hash}")
    return image, {
        "bytes": image.stat().st_size,
        "sha256": sys_hash,
        "readbacks": readbacks,
    }

def main():
    if "microsoft" not in Path("/proc/sys/kernel/osrelease").read_text().lower():
        raise RuntimeError("Run this builder inside Ubuntu WSL.")

    parser = argparse.ArgumentParser(description=f"Build {CANDIDATE}")
    parser.add_argument("--dry-run", action="store_true", help="Check prerequisites only")
    args = parser.parse_args()

    print(f"=== {CANDIDATE} ===")
    check_space()
    c39_manifest = load_c39_manifest()

    c23 = load_module("candidate23_builder_for_c40", ROOT / "tools/build_candidate23_sf_prime_skip.py")
    c24 = load_module("candidate24_builder_for_c40", ROOT / "tools/build_candidate24_framework_display_diag.py")

    C40_STAGE.mkdir(parents=True, exist_ok=True)
    C40_IMAGES.mkdir(parents=True, exist_ok=True)
    C40_WORK.mkdir(parents=True, exist_ok=True)
    stage = C40_WORK / "staging"
    stage.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    if args.dry_run:
        print("[DRY-RUN] Prerequisites validated successfully.")
        return

    # 1. Assemble C40 System Tree (Single variable)
    tree_info = assemble_c40_system_tree(stage)

    # 2. Build System Image
    system_img, system_info = build_system(c23, stage)

    # 3. Build vbmeta_system.img
    print("\n[VBMETA_SYSTEM] Rebuilding vbmeta_system.img...")
    c24.C23_IMAGES = C39_IMAGES
    vbmeta_info = c24.rebuild_vbmeta_system_c24(c23, system_img, C40_IMAGES / "vbmeta_system.img", stage)
    print(f"[VBMETA_SYSTEM] vbmeta_system.img built: {sha256(C40_IMAGES / 'vbmeta_system.img')}")

    # 4. Build super.img
    print("\n[SUPER] Rebuilding super.img with lpmake...")
    c23.C23_IMAGES = C40_IMAGES
    super_img, logical_hashes = c23.build_super(system_img, stage)
    if logical_hashes != c39_manifest.get("logical_input_hashes", {}):
        raise RuntimeError("Non-system logical partition inputs differed from baseline!")
    print(f"[SUPER] super.img built: {sha256(C40_IMAGES / 'super.img')}")

    # 5. Copy inherited small images
    entries = {}
    for name in IMAGE_NAMES:
        img = C40_IMAGES / name
        require_file(img)
        entries[name] = {"bytes": img.stat().st_size, "sha256": sha256(img)}

    inherited_entries = {}
    for name in INHERITED_SMALL:
        src = C31_IMAGES / name
        dst = C40_IMAGES / name
        require_file(src)
        if not dst.exists() or dst.stat().st_size != src.stat().st_size:
            shutil.copy2(src, dst)
        require_file(dst)
        inherited_entries[name] = {"bytes": dst.stat().st_size, "sha256": sha256(dst)}

    # 6. Create Build Manifest
    build_manifest = {
        "candidate": CANDIDATE,
        "base_candidate": BASE_CANDIDATE,
        "single_variable_modification": tree_info,
        "system_image": system_info,
        "vbmeta_system_image": vbmeta_info,
        "images": entries,
        "inherited_images": inherited_entries,
        "logical_input_hashes": logical_hashes
    }
    manifest_path = C40_IMAGES / "BUILD_MANIFEST.json"
    manifest_path.write_text(json.dumps(build_manifest, indent=2), encoding="utf-8")
    report_manifest = REPORT_DIR / "C40_BUILD_MANIFEST.json"
    report_manifest.write_text(json.dumps(build_manifest, indent=2), encoding="utf-8")
    print(f"\n[MANIFEST] Manifest written to {manifest_path}")
    print("\n=== Candidate 40 Build Completed Successfully! ===")

if __name__ == "__main__":
    main()
