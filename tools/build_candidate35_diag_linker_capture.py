#!/usr/bin/env python3
"""Build Candidate 35-DIAG: Linker64 crash_dump helper stderr pipe capture.

Inherits Candidate 32-DIAG (zygote-domain canary, init markers, C31 no_fatal.zygote).
Modifies exactly ONE component in the system tree:
com.android.runtime.apex:
  - bin/linker64:
    1. Child: dup2(output_pipe[1], 1), dup2(output_pipe[1], 2), dup2(crash_dump_pipe[0], 0)
    2. Parent: protocol-aware handshake check (rc > 0 && buf[0] == 0x01 -> SUCCESS)
    3. Parent failure capture: 512-byte stack buffer reads stderr, null-terms, logs "C35 helper output: %s\n"
    4. Canonical patched SHA256: 8cc81052fb27b91214314e660ae6ab4245bda96c43e20b2368d3f340d5762574
  - Repacked payload EROFS + AVB hashtree footer (SHA256_RSA4096)
  - Repacked APEX container signed with APK Signature Scheme v3
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
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WSL_BUILD = Path("/path/to/thyme-os4-build")

C31_STAGE = ROOT / "work/stage_c31_diag_zygote_critical_20261001_run1"
C31_IMAGES = C31_STAGE / "images"

C32_STAGE = ROOT / "work/stage_c32_diag_zygote_domain_canary_20261001_run3"
C32_IMAGES = C32_STAGE / "images"
C32_WORK = WSL_BUILD / "c32_diag_zygote_domain_canary_20261001_run3"
C32_TREE = C32_WORK / "system_tree"

C35_STAGE = ROOT / "work/stage_c35_diag_linker_capture_20261002"
C35_IMAGES = C35_STAGE / "images"
C35_WORK = WSL_BUILD / "c35_diag_linker_capture_20261002"
C35_TREE = C35_WORK / "system_tree"
REPORT_DIR = ROOT / "reports/c35_diag_candidate35_build_20261002"

IMAGE_NAMES = ("super.img", "vbmeta_system.img")
INHERITED_SMALL = ("boot.img", "vendor_boot.img", "dtbo.img", "vbmeta.img")
CANDIDATE = "Candidate 35-DIAG Linker64 crash_dump helper stderr capture"
BASE_CANDIDATE = "Candidate 32-DIAG zygote-domain crash-dump isolation canary"

CANONICAL_LINKER_SHA256 = "8cc81052fb27b91214314e660ae6ab4245bda96c43e20b2368d3f340d5762574"
EXPECTED_LINKER_SIZE = 2473488

SYSTEM_UUID = "[REDACTED_DEVICE_ID]-8f73-4e28-aefe-8ee48d2d8b41"
SYSTEM_SALT = "c5ffc2c51fef1864ad27e6903e582f52611121819811b66eb40f6ea9b60350c5"
SYSTEM_SIZE = 1_092_616_192

MKFS = ROOT / "tools/erofs-utils/wsl/mkfs.erofs"
FSCK = ROOT / "tools/erofs-utils/wsl/fsck.erofs"
DUMP = ROOT / "tools/erofs-utils/wsl/dump.erofs"
LPMAKE = ROOT / "tools/android-tools-static/linux/android-tools-static/lpmake"
SIMG2IMG = ROOT / "tools/android-tools-static/linux/android-tools-static/simg2img"
LPDUMP = ROOT / "tools/android-tools-static/linux/android-tools-static/lpdump"
AVBTOOL = ROOT / "tools/bootimg/avbtool.py"

APKSIGNER_BAT_WIN = r"[LOCAL_USER_PATH]"

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

def load_c32_manifest() -> dict[str, object]:
    path = C32_IMAGES / "BUILD_MANIFEST.json"
    require_file(path)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("candidate") != BASE_CANDIDATE:
        raise RuntimeError("C32 manifest candidate name does not match expected baseline.")
    for name in INHERITED_SMALL:
        item = manifest["inherited_images"][name]
        require_file(C31_IMAGES / name, int(item["bytes"]))
        if sha256(C31_IMAGES / name) != str(item["sha256"]).upper():
            raise RuntimeError(f"C31 inherited image mismatch: {name}")
    return manifest

def build_patched_linker() -> Path:
    patched_linker = C35_WORK / "linker64"
    if not patched_linker.is_file():
        raise RuntimeError(f"Patched linker64 not found at {patched_linker}. Run build_c35_clean_linker.py first.")
    h = hashlib.sha256(patched_linker.read_bytes()).hexdigest().lower()
    sz = patched_linker.stat().st_size
    if h != CANONICAL_LINKER_SHA256:
        raise RuntimeError(f"Linker64 SHA256 mismatch: {h} != {CANONICAL_LINKER_SHA256}")
    if sz != EXPECTED_LINKER_SIZE:
        raise RuntimeError(f"Linker64 size mismatch: {sz} != {EXPECTED_LINKER_SIZE}")
    print(f"[LINKER64] Confirmed canonical patched linker64: SHA256={h}, Size={sz}")
    return patched_linker

def build_repacked_runtime_apex(stage: Path) -> tuple[Path, dict[str, object]]:
    print("[APEX] Rebuilding com.android.runtime.apex...")
    final_apex = C35_WORK / "com.android.runtime.apex"
    if not final_apex.is_file():
        raise RuntimeError(f"Repacked APEX not found at {final_apex}. Run test_apex_pipeline.py and sign.")
    
    # Verify APEX
    with zipfile.ZipFile(final_apex, "r") as z:
        pubkey = z.read("apex_pubkey")
        payload = z.read("apex_payload.img")
    
    pubkey_sha1 = hashlib.sha1(pubkey).hexdigest()
    payload_file = stage / "apex_payload_extracted.img"
    payload_file.write_bytes(payload)
    
    avb_info = run(["python3", os.fspath(AVBTOOL), "info_image", "--image", os.fspath(payload_file)],
                   log=stage / "apex_payload_avb_info.txt")
    if pubkey_sha1 not in avb_info:
        raise RuntimeError("APEX pubkey does not match payload AVB footer public key!")
    
    run([os.fspath(FSCK), "-d0", os.fspath(payload_file)], log=stage / "apex_payload_fsck.txt")
    
    dumped_linker = run_bytes([os.fspath(DUMP), "--cat", "--path=/bin/linker64", os.fspath(payload_file)])
    dumped_sha256 = hashlib.sha256(dumped_linker).hexdigest().lower()
    if dumped_sha256 != CANONICAL_LINKER_SHA256:
        raise RuntimeError(f"Dumped linker inside APEX does not match canonical SHA256: {dumped_sha256}")
        
    print(f"[APEX] Verified com.android.runtime.apex: payload={len(payload)}B, pubkey_sha1={pubkey_sha1}, linker_sha256={dumped_sha256}")
    payload_file.unlink()
    
    return final_apex, {
        "bytes": final_apex.stat().st_size,
        "sha256": sha256(final_apex),
        "pubkey_sha1": pubkey_sha1,
        "payload_bytes": len(payload),
        "linker_sha256": dumped_sha256,
    }

def assemble_system_tree(repacked_apex: Path, c28) -> dict[str, object]:
    print("[SYSTEM_TREE] Assembling C35 system tree from C32 baseline...")
    if C35_TREE.exists():
        shutil.rmtree(C35_TREE)
    shutil.copytree(C32_TREE, C35_TREE, symlinks=True, copy_function=c28.hardlink_or_copy)
    
    target_apex = C35_TREE / "system/apex/com.android.runtime.apex"
    if target_apex.exists():
        target_apex.unlink()
    shutil.copy2(repacked_apex, target_apex)
    os.chmod(target_apex, 0o644)
    
    # Verify tree delta against C32
    before_items = {p.relative_to(C32_TREE).as_posix(): p for p in C32_TREE.rglob("*") if p.is_file() or p.is_symlink()}
    after_items = {p.relative_to(C35_TREE).as_posix(): p for p in C35_TREE.rglob("*") if p.is_file() or p.is_symlink()}
    
    removed = sorted(set(before_items) - set(after_items))
    added = sorted(set(after_items) - set(before_items))
    modified = []
    for rel in sorted(set(before_items) & set(after_items)):
        if before_items[rel].is_symlink() or after_items[rel].is_symlink():
            if os.readlink(before_items[rel]) != os.readlink(after_items[rel]):
                modified.append(rel)
        elif before_items[rel].stat().st_size != after_items[rel].stat().st_size or sha256(before_items[rel]) != sha256(after_items[rel]):
            modified.append(rel)
            
    delta = {"removed": removed, "added": added, "modified": modified}
    expected = {"removed": [], "added": [], "modified": ["system/apex/com.android.runtime.apex"]}
    if delta != expected:
        raise RuntimeError(f"Unexpected system tree delta: {delta} != {expected}")
        
    print(f"[SYSTEM_TREE] Tree delta confirmed: exactly 1 file modified (com.android.runtime.apex)")
    return delta

def build_system(c23, stage: Path) -> tuple[Path, dict[str, object]]:
    print("[SYSTEM] Building system_c35_diag.img with EROFS and AVB...")
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
    contexts_path = stage / "system_file_contexts_c35"
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
    for item in sorted(C35_TREE.rglob("*"), key=lambda p: p.relative_to(C35_TREE).as_posix()):
        rel = "system/" + item.relative_to(C35_TREE).as_posix()
        if rel in known:
            continue
        st = item.lstat()
        added.append(f"{rel} {st.st_uid} {st.st_gid} {stat.S_IMODE(st.st_mode):04o}")
        known.add(rel)
    fs_config = stage / "system_fs_config_c35"
    fs_config.write_text("\n".join(rebased + added) + "\n", encoding="utf-8", newline="\n")
    
    raw = stage / "system_c35_diag.raw.erofs"
    image = stage / "system_c35_diag.img"
    c23.run([c23.MKFS, "-zlz4hc", "-T", "0", "-U", c23.SYSTEM_UUID,
             "--mount-point=/system", f"--fs-config-file={fs_config}",
             f"--file-contexts={contexts_path}", raw, C35_TREE],
            log=stage / "mkfs_system_c35_diag.log")
    c23.run([c23.FSCK, "-d0", raw], log=stage / "fsck_system_c35_diag.log")
    shutil.copy2(raw, image)
    c23.run(["python3", c23.AVBTOOL, "add_hashtree_footer", "--image", image,
             "--partition_size", str(c23.SYSTEM_SIZE), "--partition_name", "system",
             "--hash_algorithm", "sha256", "--salt", c23.SYSTEM_SALT,
             "--algorithm", "NONE", "--do_not_generate_fec"],
             log=stage / "avb_system_c35_diag.log")
    require_file(image, c23.SYSTEM_SIZE)
    
    # Readback checks
    expected_readbacks = {
        "/system/etc/init/hw/init.rc": ("setprop init.svc_debug.no_fatal.zygote true", "THYME_C32_CANARY event=trigger"),
        "/system/apex/com.android.runtime.apex": (),
        "/system/bin/c32_zygote_canary": (),
    }
    readbacks = {}
    for path, tokens in expected_readbacks.items():
        data = run_bytes([c23.DUMP, "--cat", f"--path={path}", raw])
        if path == "/system/apex/com.android.runtime.apex":
            if hashlib.sha256(data).hexdigest().upper() != sha256(C35_TREE / "system/apex/com.android.runtime.apex"):
                raise RuntimeError("Dumped APEX does not match source tree APEX!")
        elif path == "/system/bin/c32_zygote_canary":
            if hashlib.sha256(data).hexdigest().upper() != sha256(C32_TREE / "system/bin/c32_zygote_canary"):
                raise RuntimeError("Dumped canary does not match C32 baseline canary!")
        else:
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
        c23.run(["python3", c23.AVBTOOL, "verify_image", "--image", image],
                log=stage / "avb_verify_system_c35_diag.log")
    finally:
        verify_link.unlink(missing_ok=True)
        
    print(f"[SYSTEM] system_c35_diag.img successfully built and verified: {sha256(image)}")
    return image, {
        "bytes": image.stat().st_size,
        "sha256": sha256(image),
        "readbacks": readbacks,
    }

def main():
    if "microsoft" not in Path("/proc/sys/kernel/osrelease").read_text().lower():
        raise RuntimeError("Run this builder inside Ubuntu WSL.")
        
    print("==================================================")
    print("THYME-OS4 C35-DIAG CANDIDATE BUILD PIPELINE")
    print("==================================================")
    
    storage = check_space()
    c32_manifest = load_c32_manifest()
    
    c23 = load_module("candidate23_builder_for_c35", ROOT / "tools/build_candidate23_sf_prime_skip.py")
    c24 = load_module("candidate24_builder_for_c35", ROOT / "tools/build_candidate24_framework_display_diag.py")
    c28 = load_module("candidate28_builder_for_c35", ROOT / "tools/build_candidate28_recovery_diag.py")
    
    C35_STAGE.mkdir(parents=True, exist_ok=True)
    C35_IMAGES.mkdir(parents=True, exist_ok=True)
    C35_WORK.mkdir(parents=True, exist_ok=True)
    stage = C35_WORK / "staging"
    stage.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    
    # 1. Patched Linker64
    patched_linker = build_patched_linker()
    
    # 2. Rebuild and Sign APEX
    repacked_apex, apex_info = build_repacked_runtime_apex(stage)
    
    # 3. Assemble C35 System Tree
    delta_info = assemble_system_tree(repacked_apex, c28)
    
    # 4. Build System Image
    system_img, system_info = build_system(c23, stage)
    
    # 5. Build vbmeta_system.img
    print("[VBMETA_SYSTEM] Rebuilding vbmeta_system.img...")
    c24.C23_IMAGES = C32_IMAGES
    vbmeta_info = c24.rebuild_vbmeta_system_c24(c23, system_img, C35_IMAGES / "vbmeta_system.img", stage)
    print(f"[VBMETA_SYSTEM] vbmeta_system.img built: {sha256(C35_IMAGES / 'vbmeta_system.img')}")
    
    # 6. Build super.img
    print("[SUPER] Rebuilding super.img with lpmake...")
    c23.C23_IMAGES = C35_IMAGES
    super_img, logical_hashes = c23.build_super(system_img, stage)
    if logical_hashes != c32_manifest.get("logical_input_hashes", {}):
        raise RuntimeError("Non-system logical partition inputs differed from baseline!")
    print(f"[SUPER] super.img built: {sha256(C35_IMAGES / 'super.img')}")
    
    # 7. Copy inherited small images
    entries = {}
    for name in IMAGE_NAMES:
        img = C35_IMAGES / name
        require_file(img)
        entries[name] = {"bytes": img.stat().st_size, "sha256": sha256(img)}
        
    inherited_entries = {}
    for name in INHERITED_SMALL:
        src = C31_IMAGES / name
        dst = C35_IMAGES / name
        require_file(src)
        if not dst.exists() or dst.stat().st_size != src.stat().st_size:
            shutil.copy2(src, dst)
        require_file(dst)
        inherited_entries[name] = {"bytes": dst.stat().st_size, "sha256": sha256(dst)}
        
    # 8. Create Build Manifest
    manifest = {
        "candidate": CANDIDATE,
        "base": BASE_CANDIDATE,
        "classification": "diagnostic-only; linker64 crash_dump helper stderr pipe capture",
        "canonical_linker64_sha256": CANONICAL_LINKER_SHA256,
        "linker_patch": {
            "canonical_sha256": CANONICAL_LINKER_SHA256,
            "bytes": EXPECTED_LINKER_SIZE,
            "modifications": [
                "Child: dup2(output_pipe[1], 1), dup2(output_pipe[1], 2), dup2(crash_dump_pipe[0], 0)",
                "Parent: protocol-aware handshake check (rc > 0 && buf[0] == 0x01)",
                "Parent failure capture: 512-byte stack buffer reads stderr, null-terms, logs 'C35 helper output: %s\\n'",
            ],
        },
        "apex_build": apex_info,
        "source_delta": delta_info,
        "system_build": system_info,
        "vbmeta_system_update": vbmeta_info,
        "logical_input_hashes": logical_hashes,
        "flash_scope_prepared": ["super", "vbmeta_system_a"],
        "inherited_images": inherited_entries,
        "images": entries,
        "host_storage_gate": storage,
        "device_state": "Fastboot A retry=1, B retry=7; DO NOT REBOOT without user explicit command",
    }
    
    manifest_file = C35_IMAGES / "BUILD_MANIFEST.json"
    manifest_file.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\n[MANIFEST] Saved build manifest to {manifest_file}")
    
    # Also save to Windows report
    report_manifest = REPORT_DIR / "C35_BUILD_MANIFEST.json"
    report_manifest.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    
    print("\n==================================================")
    print("CANDIDATE 35 BUILD PIPELINE 100% COMPLETE & VERIFIED")
    print("==================================================")
    print(f"super.img:         {entries['super.img']['bytes']} bytes, SHA256={entries['super.img']['sha256']}")
    print(f"vbmeta_system.img: {entries['vbmeta_system.img']['bytes']} bytes, SHA256={entries['vbmeta_system.img']['sha256']}")
    print(f"Linker64 SHA256:   {CANONICAL_LINKER_SHA256}")

if __name__ == "__main__":
    main()
