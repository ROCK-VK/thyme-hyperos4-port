#!/usr/bin/env python3
"""Build Candidate 39-DIAG: Real Zygote ART Runtime::Abort Level-2 Caller and Message in-situ capture.

Inherits Candidate 32-DIAG (zygote-domain canary, init markers, C31 no_fatal.zygote).
Modifies:
1. com.android.runtime.apex:
   - bin/linker64:
     C39 patched linker64 (SHA256: aab9dbfcde057e7c2d934d0f9be1a31629ce17e6c26f008264893d9cd97adedd)
     In-situ capture of Level-2 Caller LR & callsite, and bounded zero-crash abort message string via sys_mincore.
   - Repacked payload EROFS + AVB hashtree footer (SHA256_RSA4096)
   - Repacked APEX container signed with APK Signature Scheme v3
2. system/bin/c32_zygote_canary:
   - Updated C39 canary calling Runtime::Abort("C39_CANARY_TEST") via test_c39_level2_caller
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

C35_WORK = WSL_BUILD / "c35_diag_linker_capture_20261002"

C39_STAGE = ROOT / "work/stage_c39_diag_runtime_abort_20261003"
C39_IMAGES = C39_STAGE / "images"
C39_WORK = WSL_BUILD / "c39_diag_runtime_abort_20261003"
C39_TREE = C39_WORK / "system_tree"
REPORT_DIR = ROOT / "reports/c39_diag_candidate39_build_20261003"

IMAGE_NAMES = ("super.img", "vbmeta_system.img")
INHERITED_SMALL = ("boot.img", "vendor_boot.img", "dtbo.img", "vbmeta.img")
CANDIDATE = "Candidate 39-DIAG Real Zygote ART Runtime::Abort Level-2 Caller and Message in-situ capture"
BASE_CANDIDATE = "Candidate 32-DIAG zygote-domain crash-dump isolation canary"

CANONICAL_LINKER_SHA256 = "aab9dbfcde057e7c2d934d0f9be1a31629ce17e6c26f008264893d9cd97adedd"
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

def build_repacked_runtime_apex(stage: Path) -> tuple[Path, dict[str, object]]:
    print("\n[APEX] Rebuilding com.android.runtime.apex for C39...")
    C39_WORK.mkdir(parents=True, exist_ok=True)

    key_pem = C35_WORK / "c35_apex_key.pem"
    pubkey_path = C35_WORK / "apex_pubkey"
    cert_pem = C35_WORK / "c35_apex_cert.pem"
    key_pk8 = C35_WORK / "c35_apex_key.pk8"

    require_file(key_pem)
    require_file(pubkey_path)
    require_file(cert_pem)
    require_file(key_pk8)

    with open(pubkey_path, "rb") as f:
        pub_bytes = f.read()
    pub_sha1 = hashlib.sha1(pub_bytes).hexdigest()
    print(f"[APEX] Using verified APEX key: pubkey_sha1={pub_sha1}")

    # Prepare payload tree
    orig_payload_dir = WSL_BUILD / "c31_runtime_inspect_20261001/rootfs/payload"
    c39_payload_dir = C39_WORK / "payload_tree"
    if c39_payload_dir.exists():
        shutil.rmtree(c39_payload_dir)
    shutil.copytree(orig_payload_dir, c39_payload_dir, symlinks=True)

    # Replace bin/linker64 with C39 patched linker64
    c39_linker = WSL_BUILD / "linker64_c39_patched"
    require_file(c39_linker, EXPECTED_LINKER_SIZE)
    l_hash = hashlib.sha256(c39_linker.read_bytes()).hexdigest().lower()
    if l_hash != CANONICAL_LINKER_SHA256:
        raise RuntimeError(f"Linker hash mismatch: {l_hash} != {CANONICAL_LINKER_SHA256}")

    target_linker = c39_payload_dir / "bin/linker64"
    shutil.copy2(c39_linker, target_linker)
    os.chmod(target_linker, 0o755)
    print(f"[APEX] C39 patched linker64 copied to payload tree (SHA256: {l_hash})")

    # Pack payload EROFS image
    config_dir = WSL_BUILD / "c31_runtime_inspect_20261001/rootfs/config"
    fs_config = config_dir / "payload_fs_config"
    file_contexts = config_dir / "payload_file_contexts"
    raw_img = C39_WORK / "payload.raw.erofs"
    payload_img = C39_WORK / "apex_payload.img"

    if raw_img.exists():
        raw_img.unlink()
    if payload_img.exists():
        payload_img.unlink()

    print("[APEX] Running mkfs.erofs on payload...")
    cmd_mkfs = [
        MKFS, "-zlz4hc", "-T", "0", "-U", "[REDACTED_DEVICE_ID]-9dfa-5edb-a43e-98e3a4d20250",
        "--mount-point=/payload", f"--fs-config-file={fs_config}", f"--file-contexts={file_contexts}",
        raw_img, c39_payload_dir
    ]
    run(cmd_mkfs, log=stage / "mkfs_apex_payload_c39.log")
    run([FSCK, "-d0", raw_img], log=stage / "fsck_apex_payload_c39.log")
    shutil.copy2(raw_img, payload_img)

    # Sign payload with avbtool
    print("[APEX] Signing payload with avbtool add_hashtree_footer...")
    cmd_avb = [
        "python3", AVBTOOL, "add_hashtree_footer", "--image", payload_img,
        "--partition_size", "12853248", "--hash_algorithm", "sha256",
        "--salt", "48e74bbf3dead7386e9a16ba8ff51cd9983c5d5ab6973bb7fb8c445a9653d0d9",
        "--key", key_pem, "--algorithm", "SHA256_RSA4096",
        "--prop", "apex.key:com.android.runtime", "--do_not_generate_fec"
    ]
    run(cmd_avb, log=stage / "avb_apex_payload_c39.log")

    # Verify payload AVB
    out_info = run(["python3", AVBTOOL, "info_image", "--image", payload_img],
                   log=stage / "avb_info_apex_payload_c39.log")
    if pub_sha1 not in out_info:
        raise RuntimeError("APEX pubkey does not match payload AVB footer public key!")

    # Repack APEX ZIP
    orig_apex = WSL_BUILD / "c32_diag_zygote_domain_canary_20261001_run3/system_tree/system/apex/com.android.runtime.apex"
    unsigned_apex = C39_WORK / "com.android.runtime.unsigned.apex"
    final_apex = C39_WORK / "com.android.runtime.apex"

    print(f"[APEX] Assembling uncompressed APEX container {unsigned_apex}...")
    with zipfile.ZipFile(orig_apex, "r") as z_in:
        with zipfile.ZipFile(unsigned_apex, "w") as z_out:
            for item in z_in.infolist():
                if item.filename == "apex_payload.img":
                    with open(payload_img, "rb") as f_pay:
                        pay_data = f_pay.read()
                    z_out.writestr("apex_payload.img", pay_data, compress_type=zipfile.ZIP_STORED)
                elif item.filename == "apex_pubkey":
                    z_out.writestr("apex_pubkey", pub_bytes, compress_type=zipfile.ZIP_STORED)
                elif item.filename.startswith("META-INF/"):
                    continue
                else:
                    data = z_in.read(item.filename)
                    z_out.writestr(item, data)

    # Sign APEX container using apksigner
    print("[APEX] Signing APEX container with apksigner APK v3 scheme...")
    wsl_prefix = r"\\wsl.localhost\Ubuntu"
    win_key = wsl_prefix + str(key_pk8).replace("/", "\\")
    win_cert = wsl_prefix + str(cert_pem).replace("/", "\\")
    win_in = wsl_prefix + str(unsigned_apex).replace("/", "\\")
    win_out = wsl_prefix + str(final_apex).replace("/", "\\")

    cmd_sign = [
        "powershell.exe", "-NoProfile", "-Command",
        f'& "{APKSIGNER_BAT_WIN}" sign --key "{win_key}" --cert "{win_cert}" --v2-signing-enabled false --v3-signing-enabled true --out "{win_out}" "{win_in}"'
    ]
    subprocess.check_call(cmd_sign)
    require_file(final_apex)

    # Verify APEX
    cmd_verify = [
        "powershell.exe", "-NoProfile", "-Command",
        f'& "{APKSIGNER_BAT_WIN}" verify --verbose "{win_out}"'
    ]
    verify_out = subprocess.check_output(cmd_verify, text=True)
    if "Verified using v3 scheme (APK Signature Scheme v3): true" not in verify_out:
        raise RuntimeError(f"APEX v3 verification failed: {verify_out}")
    print("[APEX] apksigner verify: 100% PASS (APK Signature Scheme v3: true)")

    # Verify dumped linker inside APEX
    dumped_linker = run_bytes([DUMP, "--cat", "--path=/bin/linker64", payload_img])
    dumped_sha256 = hashlib.sha256(dumped_linker).hexdigest().lower()
    if dumped_sha256 != CANONICAL_LINKER_SHA256:
        raise RuntimeError(f"Dumped linker inside APEX does not match canonical SHA256: {dumped_sha256}")

    print(f"[APEX] APEX rebuild & verification 100% complete: {final_apex.stat().st_size} bytes, SHA256={sha256(final_apex)}")

    return final_apex, {
        "bytes": final_apex.stat().st_size,
        "sha256": sha256(final_apex),
        "pubkey_sha1": pub_sha1,
        "payload_bytes": payload_img.stat().st_size,
        "linker_sha256": dumped_sha256,
    }

def assemble_system_tree(repacked_apex: Path, c28) -> dict[str, object]:
    print("\n[SYSTEM_TREE] Assembling C39 system tree from C32 baseline...")
    if C39_TREE.exists():
        shutil.rmtree(C39_TREE)
    shutil.copytree(C32_TREE, C39_TREE, symlinks=True, copy_function=c28.hardlink_or_copy)

    # 1. Update runtime APEX
    target_apex = C39_TREE / "system/apex/com.android.runtime.apex"
    if target_apex.exists():
        target_apex.unlink()
    shutil.copy2(repacked_apex, target_apex)
    os.chmod(target_apex, 0o644)

    # 2. Update c32_zygote_canary with C39 canary binary
    c39_canary_bin = WSL_BUILD / "c39_zygote_canary"
    require_file(c39_canary_bin)
    target_canary = C39_TREE / "system/bin/c32_zygote_canary"
    if target_canary.exists():
        target_canary.unlink()
    shutil.copy2(c39_canary_bin, target_canary)
    os.chmod(target_canary, 0o755)
    print(f"[SYSTEM_TREE] Updated /system/bin/c32_zygote_canary with C39 canary binary (SHA256: {sha256(target_canary)})")

    # Verify tree delta against C32
    before_items = {p.relative_to(C32_TREE).as_posix(): p for p in C32_TREE.rglob("*") if p.is_file() or p.is_symlink()}
    after_items = {p.relative_to(C39_TREE).as_posix(): p for p in C39_TREE.rglob("*") if p.is_file() or p.is_symlink()}

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
    expected = {"removed": [], "added": [], "modified": ["system/apex/com.android.runtime.apex", "system/bin/c32_zygote_canary"]}
    if delta != expected:
        raise RuntimeError(f"Unexpected system tree delta: {delta} != {expected}")

    print(f"[SYSTEM_TREE] Tree delta confirmed: strictly 2 files modified ({', '.join(modified)})")
    return delta

def build_system(c23, stage: Path) -> tuple[Path, dict[str, object]]:
    print("\n[SYSTEM] Building system_c39_diag.img with EROFS and AVB...")
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
    contexts_path = stage / "system_file_contexts_c39"
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
    for item in sorted(C39_TREE.rglob("*"), key=lambda p: p.relative_to(C39_TREE).as_posix()):
        rel = "system/" + item.relative_to(C39_TREE).as_posix()
        if rel in known:
            continue
        st = item.lstat()
        added.append(f"{rel} {st.st_uid} {st.st_gid} {stat.S_IMODE(st.st_mode):04o}")
        known.add(rel)
    fs_config = stage / "system_fs_config_c39"
    fs_config.write_text("\n".join(rebased + added) + "\n", encoding="utf-8", newline="\n")

    raw = stage / "system_c39_diag.raw.erofs"
    image = stage / "system_c39_diag.img"
    c23.run([c23.MKFS, "-zlz4hc", "-T", "0", "-U", c23.SYSTEM_UUID,
             "--mount-point=/system", f"--fs-config-file={fs_config}",
             f"--file-contexts={contexts_path}", raw, C39_TREE],
            log=stage / "mkfs_system_c39_diag.log")
    c23.run([c23.FSCK, "-d0", raw], log=stage / "fsck_system_c39_diag.log")
    shutil.copy2(raw, image)
    c23.run(["python3", c23.AVBTOOL, "add_hashtree_footer", "--image", image,
             "--partition_size", str(c23.SYSTEM_SIZE), "--partition_name", "system",
             "--hash_algorithm", "sha256", "--salt", c23.SYSTEM_SALT,
             "--algorithm", "NONE", "--do_not_generate_fec"],
             log=stage / "avb_system_c39_diag.log")
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
            if hashlib.sha256(data).hexdigest().upper() != sha256(C39_TREE / "system/apex/com.android.runtime.apex"):
                raise RuntimeError("Dumped APEX does not match source tree APEX!")
        elif path == "/system/bin/c32_zygote_canary":
            if hashlib.sha256(data).hexdigest().upper() != sha256(C39_TREE / "system/bin/c32_zygote_canary"):
                raise RuntimeError("Dumped canary does not match C39 canary!")
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
                log=stage / "avb_verify_system_c39_diag.log")
    finally:
        verify_link.unlink(missing_ok=True)

    print(f"[SYSTEM] system_c39_diag.img successfully built and verified: {sha256(image)}")
    return image, {
        "bytes": image.stat().st_size,
        "sha256": sha256(image),
        "readbacks": readbacks,
    }

def main():
    if "microsoft" not in Path("/proc/sys/kernel/osrelease").read_text().lower():
        raise RuntimeError("Run this builder inside Ubuntu WSL.")

    print("==================================================")
    print("THYME-OS4 C39-DIAG CANDIDATE BUILD PIPELINE")
    print("==================================================")

    storage = check_space()
    c32_manifest = load_c32_manifest()

    c23 = load_module("candidate23_builder_for_c39", ROOT / "tools/build_candidate23_sf_prime_skip.py")
    c24 = load_module("candidate24_builder_for_c39", ROOT / "tools/build_candidate24_framework_display_diag.py")
    c28 = load_module("candidate28_builder_for_c39", ROOT / "tools/build_candidate28_recovery_diag.py")

    C39_STAGE.mkdir(parents=True, exist_ok=True)
    C39_IMAGES.mkdir(parents=True, exist_ok=True)
    C39_WORK.mkdir(parents=True, exist_ok=True)
    stage = C39_WORK / "staging"
    stage.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Rebuild and Sign APEX
    repacked_apex, apex_info = build_repacked_runtime_apex(stage)

    # 2. Assemble C39 System Tree
    delta_info = assemble_system_tree(repacked_apex, c28)

    # 3. Build System Image
    system_img, system_info = build_system(c23, stage)

    # 4. Build vbmeta_system.img
    print("\n[VBMETA_SYSTEM] Rebuilding vbmeta_system.img...")
    c24.C23_IMAGES = C32_IMAGES
    vbmeta_info = c24.rebuild_vbmeta_system_c24(c23, system_img, C39_IMAGES / "vbmeta_system.img", stage)
    print(f"[VBMETA_SYSTEM] vbmeta_system.img built: {sha256(C39_IMAGES / 'vbmeta_system.img')}")

    # 5. Build super.img
    print("\n[SUPER] Rebuilding super.img with lpmake...")
    c23.C23_IMAGES = C39_IMAGES
    super_img, logical_hashes = c23.build_super(system_img, stage)
    if logical_hashes != c32_manifest.get("logical_input_hashes", {}):
        raise RuntimeError("Non-system logical partition inputs differed from baseline!")
    print(f"[SUPER] super.img built: {sha256(C39_IMAGES / 'super.img')}")

    # 6. Copy inherited small images
    entries = {}
    for name in IMAGE_NAMES:
        img = C39_IMAGES / name
        require_file(img)
        entries[name] = {"bytes": img.stat().st_size, "sha256": sha256(img)}

    inherited_entries = {}
    for name in INHERITED_SMALL:
        src = C31_IMAGES / name
        dst = C39_IMAGES / name
        require_file(src)
        if not dst.exists() or dst.stat().st_size != src.stat().st_size:
            shutil.copy2(src, dst)
        require_file(dst)
        inherited_entries[name] = {"bytes": dst.stat().st_size, "sha256": sha256(dst)}

    # 7. Create Build Manifest
    manifest = {
        "candidate": CANDIDATE,
        "base": BASE_CANDIDATE,
        "classification": "diagnostic-only; linker64 ART Runtime::Abort Level-2 caller and message in-situ capture",
        "canonical_linker64_sha256": CANONICAL_LINKER_SHA256,
        "linker_patch": {
            "canonical_sha256": CANONICAL_LINKER_SHA256,
            "bytes": EXPECTED_LINKER_SIZE,
            "modifications": [
                "Trampoline: b 0x09c9c0 at 0x1106f4",
                "Stub: 0x09c9c0 ~ 0x09cd85 (BinaryExpr dead code cave, tri-log C37/C38/C39 output, in-situ capture of [x29_runtime + 8] Level-2 caller LR and [x29_runtime - 16] msg_ptr, sys_mincore zero-crash validation, bounded 127B string copy)",
            ],
        },
        "canary_update": {
            "path": "/system/bin/c32_zygote_canary",
            "sha256": sha256(C39_TREE / "system/bin/c32_zygote_canary"),
            "function": "dlopen libart.so -> test_c39_level2_caller -> Runtime::Abort(\"C39_CANARY_TEST\")",
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
        "device_state": "Fastboot A retry=4, B retry=7; DO NOT REBOOT without user explicit command",
    }

    manifest_file = C39_IMAGES / "BUILD_MANIFEST.json"
    manifest_file.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\n[MANIFEST] Saved build manifest to {manifest_file}")

    report_manifest = REPORT_DIR / "C39_BUILD_MANIFEST.json"
    report_manifest.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print("\n==================================================")
    print("CANDIDATE 39 BUILD PIPELINE 100% COMPLETE & VERIFIED")
    print("==================================================")
    print(f"super.img:         {entries['super.img']['bytes']} bytes, SHA256={entries['super.img']['sha256']}")
    print(f"vbmeta_system.img: {entries['vbmeta_system.img']['bytes']} bytes, SHA256={entries['vbmeta_system.img']['sha256']}")
    print(f"Linker64 SHA256:   {CANONICAL_LINKER_SHA256}")

if __name__ == "__main__":
    main()
