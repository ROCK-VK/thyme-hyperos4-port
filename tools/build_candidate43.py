#!/usr/bin/env python3
"""Build Candidate 43: Netd eBPF Init Abort Surgical Bypass & System Integration
for Xiaomi 10S (thyme / Snapdragon 870) running HyperOS 4 / Android 17.

STRICT SINGLE-VARIABLE MODIFICATION:
Modify ONLY:
  /apex/com.android.tethering/lib64/libnetd_updatable.so
Specifically:
  In libnetd_updatable_init(const char* cg2_path):
    offset 0x11534: cbnz w8, 115d8 (0x28 0x05 0x00 0x35) -> nop (0x1f 0x20 0x03 0xd5)
  In apex_manifest.pb:
    version bump: 370400127 -> 370400128 (forces apexd to evict /data/apex/decompressed cache)
All other XML nodes, framework components, vendor libraries, display configurations,
and kernel remain 100% UNTOUCHED, inheriting C40 (codecs variant _V1_0) and C42 (display XML lower bound).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import zipfile
from pathlib import Path

# Base Paths
ROOT = Path("/path/to/thyme-os4-local")
WSL_BUILD = Path("/path/to/thyme-os4-build")

C30_AUDIT = ROOT / "work/third_party_milo_hyperos4_audit_20260930"
C40_STAGE = ROOT / "work/stage_c40_media_profiles_variant_20261003"
C40_TREE = WSL_BUILD / "c40_media_profiles_variant_20261003/system_tree"
C40_STAGING = WSL_BUILD / "c40_media_profiles_variant_20261003/staging"

C42_STAGE = ROOT / "work/stage_c42_display_config_fix_20261004"
C42_IMAGES = C42_STAGE / "images"
C42_UNPACKED = WSL_BUILD / "c42_display_config_fix_20261004/unpacked_super"
C42_STAGING = WSL_BUILD / "c42_display_config_fix_20261004/staging"

C43_STAGE = ROOT / "work/stage_c43_netd_ebpf_bypass_20261004"
C43_IMAGES = C43_STAGE / "images"
C43_WORK = WSL_BUILD / "c43_netd_ebpf_bypass_20261004"
C43_STAGING = C43_WORK / "staging"
C43_TREE = C43_WORK / "system_tree"
REPORT_DIR = ROOT / "reports/c43_candidate43_build_20261004"

# Tools
TOOLS = ROOT / "tools"
ANDROID_TOOLS = TOOLS / "android-tools-static/linux/android-tools-static"
LPMAKE = ANDROID_TOOLS / "lpmake"
SIMG2IMG = ANDROID_TOOLS / "simg2img"
LPDUMP = ANDROID_TOOLS / "lpdump"
AVBTOOL = TOOLS / "bootimg/avbtool.py"
MKFS_EROFS = TOOLS / "erofs-utils/wsl/mkfs.erofs"
FSCK_EROFS = TOOLS / "erofs-utils/wsl/fsck.erofs"
DUMP_EROFS = TOOLS / "erofs-utils/wsl/dump.erofs"
APKSIGNER_BAT_WIN = r"[LOCAL_USER_PATH]"

# Partition Constants
DEVICE_SIZE = 9_126_805_504
ALIGNMENT = 1_048_576
SYSTEM_SIZE = 1_092_616_192
SYSTEM_EXT_SIZE = 942_669_824
VENDOR_SIZE = 1_510_998_016
SYSTEM_UUID = "[REDACTED_DEVICE_ID]-8f73-4e28-aefe-8ee48d2d8b41"
SYSTEM_SALT = "c5ffc2c51fef1864ad27e6903e582f52611121819811b66eb40f6ea9b60350c5"

EXPECTED_ORIG_SO_SHA256 = "2c811151e99f227bc8e180f64f0b686e8d696b5323ce2f81313914cc597277ad".lower()
EXPECTED_PATCHED_SO_SHA256 = "a70a3176b82d792cdea3ed876c90980c1d459fbcdb859d5e21f12c3a5eaf92f5".lower()
SO_PATCH_OFFSET = 0x11534
PAYLOAD_PATCH_OFFSET = 7818 * 4096 + 0x534  # 0x1e8a534

CANDIDATE = "Candidate 43 Netd eBPF Init Abort Surgical Bypass"
BASE_CANDIDATE = "Candidate 42 DisplayDeviceConfig Minimum Brightness Fix"

def say(msg: str) -> None:
    print(msg, flush=True)

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8 * 1024 * 1024):
            h.update(chunk)
    return h.hexdigest().upper()

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()

def require_file(path: Path, expected_size: int | None = None) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Required file missing: {path}")
    if expected_size is not None and path.stat().st_size != expected_size:
        raise RuntimeError(f"Size mismatch for {path}: got {path.stat().st_size}, expected {expected_size}")

def check_space() -> dict[str, float]:
    storage: dict[str, float] = {}
    for drive, mount in (("C", "/mnt/c"), ("D", "/mnt/d"), ("E", "/mnt/e")):
        usage = shutil.disk_usage(mount)
        free_gib = round(usage.free / (1024 ** 3), 2)
        storage[f"{drive}_free_gib"] = free_gib
        say(f"[SPACE] {drive}: free={free_gib:.2f} GiB")
        if usage.free < 50 * 1024 ** 3:
            raise RuntimeError(f"{drive}: below 50 GiB project gate!")
    return storage

def run_cmd(cmd: list[str] | str, log_file: Path | None = None) -> str:
    if isinstance(cmd, str):
        res = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    else:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        log_file.write_text(res.stdout, encoding="utf-8")
    if res.returncode != 0:
        say(f"Command FAILED: {cmd}\nOutput:\n{res.stdout}")
        raise subprocess.CalledProcessError(res.returncode, cmd, res.stdout)
    return res.stdout

def build_patched_tethering_apex(work_dir: Path) -> tuple[Path, dict[str, object]]:
    say("\n[APEX] Building patched com.android.tethering.capex...")
    apex_work = work_dir / "tethering_apex"
    apex_work.mkdir(parents=True, exist_ok=True)

    # 1. Verify original libnetd_updatable.so
    orig_so_path = C30_AUDIT / "libnetd_updatable_c30.so"
    require_file(orig_so_path, 103648)
    h_orig = sha256_file(orig_so_path).lower()
    if h_orig != EXPECTED_ORIG_SO_SHA256:
        raise RuntimeError(f"Original SO hash mismatch: {h_orig} != {EXPECTED_ORIG_SO_SHA256}")
    say(f"[APEX] Original libnetd_updatable.so SHA256: {h_orig}")

    # Create patched libnetd_updatable.so
    with open(orig_so_path, "rb") as f:
        so_data = bytearray(f.read())
    if so_data[SO_PATCH_OFFSET:SO_PATCH_OFFSET+4] != b'\x28\x05\x00\x35':
        raise RuntimeError(f"Unexpected instruction at SO offset 0x{SO_PATCH_OFFSET:x}!")
    so_data[SO_PATCH_OFFSET:SO_PATCH_OFFSET+4] = b'\x1f\x20\x03\xd5'  # NOP
    patched_so_path = apex_work / "libnetd_updatable.so"
    patched_so_path.write_bytes(so_data)
    h_patched_so = sha256_file(patched_so_path).lower()
    if h_patched_so != EXPECTED_PATCHED_SO_SHA256:
        raise RuntimeError(f"Patched SO hash mismatch: {h_patched_so} != {EXPECTED_PATCHED_SO_SHA256}")
    say(f"[APEX] Patched libnetd_updatable.so SHA256: {h_patched_so}")

    # 2. Patch apex_payload.img
    orig_payload_path = C30_AUDIT / "apex_unpack_c30/apex_payload.img"
    require_file(orig_payload_path, 36421632)
    with open(orig_payload_path, "rb") as f:
        payload_data = bytearray(f.read())

    if payload_data[PAYLOAD_PATCH_OFFSET:PAYLOAD_PATCH_OFFSET+4] != b'\x28\x05\x00\x35':
        raise RuntimeError(f"Unexpected instruction at payload offset 0x{PAYLOAD_PATCH_OFFSET:x}!")
    payload_data[PAYLOAD_PATCH_OFFSET:PAYLOAD_PATCH_OFFSET+4] = b'\x1f\x20\x03\xd5'  # NOP

    patched_payload_raw = apex_work / "apex_payload.raw.img"
    patched_payload_raw.write_bytes(payload_data[:36126720])  # Strip old AVB hashtree + footer
    say(f"[APEX] Stripped raw payload size: {patched_payload_raw.stat().st_size} bytes")

    # Verify dumped libnetd_updatable.so from patched payload using debugfs
    dumped_so_path = apex_work / "dumped_libnetd.so"
    run_cmd(f"debugfs -R 'dump /lib64/libnetd_updatable.so {dumped_so_path}' {patched_payload_raw} >/dev/null 2>&1")
    h_dumped = sha256_file(dumped_so_path).lower()
    if h_dumped != h_patched_so:
        raise RuntimeError(f"Dumped SO hash {h_dumped} != patched SO hash {h_patched_so}")
    say("[APEX] debugfs dump verification: PASS (SHA256 matches)")

    # 3. APEX RSA-4096 Key setup
    key_pem = apex_work / "c43_tethering_apex_key.pem"
    key_pk8 = apex_work / "c43_tethering_apex_key.pk8"
    cert_pem = apex_work / "c43_tethering_apex_cert.pem"
    pubkey_path = apex_work / "apex_pubkey"

    # Reuse key if present in c43_tethering_patch_test to avoid unnecessary re-generation
    test_key_dir = Path("/path/to/thyme-os4-build/c43_tethering_patch_test")
    if (test_key_dir / "c43_tethering_apex_key.pem").exists():
        say("[APEX] Reusing verified test key pair from test workspace...")
        shutil.copy2(test_key_dir / "c43_tethering_apex_key.pem", key_pem)
        shutil.copy2(test_key_dir / "c43_tethering_apex_key.pk8", key_pk8)
        shutil.copy2(test_key_dir / "c43_tethering_apex_cert.pem", cert_pem)
        shutil.copy2(test_key_dir / "apex_pubkey", pubkey_path)
    else:
        say("[APEX] Generating fresh RSA-4096 APEX key...")
        run_cmd(f"openssl genrsa -out {key_pem} 4096")
        run_cmd(f"openssl pkcs8 -topk8 -inform PEM -outform DER -in {key_pem} -out {key_pk8} -nocrypt")
        run_cmd(f"openssl req -new -x509 -key {key_pem} -out {cert_pem} -days 10000 -subj '/C=US/ST=California/L=Mountain View/O=Android/OU=Android/CN=Android/emailAddress=[REDACTED_EMAIL]'")
        run_cmd(f"python3 {AVBTOOL} extract_public_key --key {key_pem} --output {pubkey_path}")

    pub_bytes = pubkey_path.read_bytes()
    pub_sha1 = hashlib.sha1(pub_bytes).hexdigest()
    say(f"[APEX] APEX pubkey: {len(pub_bytes)} bytes, SHA1={pub_sha1}")

    # 4. Sign payload with avbtool add_hashtree_footer
    final_payload_img = apex_work / "apex_payload.img"
    shutil.copy2(patched_payload_raw, final_payload_img)
    cmd_avb = [
        "python3", str(AVBTOOL), "add_hashtree_footer",
        "--image", str(final_payload_img),
        "--hash_algorithm", "sha256",
        "--salt", "07ef9904b69427951e0ccfcd9fa86a7b962e3b52254d93e23e62e0c045a3947b",
        "--key", str(key_pem),
        "--algorithm", "SHA256_RSA4096",
        "--prop", "apex.key:com.android.tethering",
        "--do_not_generate_fec"
    ]
    run_cmd(cmd_avb)
    require_file(final_payload_img, 36421632)
    say(f"[APEX] Signed payload with avbtool: size={final_payload_img.stat().st_size} bytes")

    info_res = run_cmd(f"python3 {AVBTOOL} info_image --image {final_payload_img}")
    if pub_sha1 not in info_res:
        raise RuntimeError("Public key SHA1 not in payload AVB footer info!")
    say("[APEX] Verified payload AVB info_image: PASS")

    # 5. Build repacked com.android.tethering.apex (uncompressed container)
    orig_apex_file = C30_AUDIT / "apex_unpack_c30/original_apex"
    require_file(orig_apex_file)
    unsigned_apex = apex_work / "com.android.tethering.unsigned.apex"
    signed_apex = apex_work / "com.android.tethering.apex"

    # Version bump in apex_manifest.pb: 370400127 -> 370400128
    with zipfile.ZipFile(orig_apex_file, "r") as z_in:
        manifest_data = bytearray(z_in.read("apex_manifest.pb"))
    old_varint = b'\xff\xb5\xcf\xb0\x01'  # 370400127
    new_varint = b'\x80\xb6\xcf\xb0\x01'  # 370400128
    if old_varint not in manifest_data:
        raise RuntimeError("Old version varint not found in apex_manifest.pb!")
    manifest_data = bytearray(bytes(manifest_data).replace(old_varint, new_varint))

    say("[APEX] Assembling uncompressed APEX container...")
    with zipfile.ZipFile(orig_apex_file, "r") as z_in:
        with zipfile.ZipFile(unsigned_apex, "w") as z_out:
            for item in z_in.infolist():
                if item.filename == "apex_payload.img":
                    z_out.writestr("apex_payload.img", final_payload_img.read_bytes(), compress_type=zipfile.ZIP_STORED)
                elif item.filename == "apex_pubkey":
                    z_out.writestr("apex_pubkey", pub_bytes, compress_type=zipfile.ZIP_STORED)
                elif item.filename == "apex_manifest.pb":
                    z_out.writestr("apex_manifest.pb", manifest_data, compress_type=zipfile.ZIP_STORED)
                elif item.filename.startswith("META-INF/"):
                    continue
                else:
                    z_out.writestr(item, z_in.read(item.filename))

    # Sign uncompressed APEX with apksigner (v3 scheme)
    wsl_prefix = r"\\wsl.localhost\Ubuntu"
    win_key = wsl_prefix + str(key_pk8).replace("/", "\\")
    win_cert = wsl_prefix + str(cert_pem).replace("/", "\\")
    win_in = wsl_prefix + str(unsigned_apex).replace("/", "\\")
    win_out = wsl_prefix + str(signed_apex).replace("/", "\\")

    cmd_sign = [
        "powershell.exe", "-NoProfile", "-Command",
        f'& "{APKSIGNER_BAT_WIN}" sign --key "{win_key}" --cert "{win_cert}" --v2-signing-enabled false --v3-signing-enabled true --out "{win_out}" "{win_in}"'
    ]
    say("[APEX] Signing original_apex with apksigner (v3)...")
    subprocess.check_call(cmd_sign)
    require_file(signed_apex)

    cmd_verify = [
        "powershell.exe", "-NoProfile", "-Command",
        f'& "{APKSIGNER_BAT_WIN}" verify --verbose "{win_out}"'
    ]
    verify_out = subprocess.check_output(cmd_verify, text=True)
    if "Verified using v3 scheme (APK Signature Scheme v3): true" not in verify_out:
        raise RuntimeError("apksigner verification failed on original_apex!")
    say("[APEX] apksigner verify on original_apex: PASS (v3: true)")

    # 6. Build compressed APEX container (com.android.tethering.capex)
    say("[APEX] Assembling compressed APEX container (capex)...")
    unsigned_capex = apex_work / "com.android.tethering.unsigned.capex"
    signed_capex = apex_work / "com.android.tethering.capex"

    with zipfile.ZipFile(orig_apex_file, "r") as z_in:
        android_manifest = z_in.read("AndroidManifest.xml")
        apex_build_info = z_in.read("apex_build_info.pb")

    with zipfile.ZipFile(unsigned_capex, "w") as z_out:
        z_out.writestr("AndroidManifest.xml", android_manifest, compress_type=zipfile.ZIP_STORED)
        z_out.writestr("apex_build_info.pb", apex_build_info, compress_type=zipfile.ZIP_STORED)
        z_out.writestr("apex_manifest.pb", manifest_data, compress_type=zipfile.ZIP_STORED)
        z_out.writestr("apex_pubkey", pub_bytes, compress_type=zipfile.ZIP_STORED)
        with open(signed_apex, "rb") as f_orig:
            z_out.writestr("original_apex", f_orig.read(), compress_type=zipfile.ZIP_DEFLATED)

    win_capex_in = wsl_prefix + str(unsigned_capex).replace("/", "\\")
    win_capex_out = wsl_prefix + str(signed_capex).replace("/", "\\")
    cmd_sign_capex = [
        "powershell.exe", "-NoProfile", "-Command",
        f'& "{APKSIGNER_BAT_WIN}" sign --key "{win_key}" --cert "{win_cert}" --v2-signing-enabled false --v3-signing-enabled true --out "{win_capex_out}" "{win_capex_in}"'
    ]
    say("[APEX] Signing capex container with apksigner (v3)...")
    subprocess.check_call(cmd_sign_capex)
    require_file(signed_capex)

    cmd_verify_capex = [
        "powershell.exe", "-NoProfile", "-Command",
        f'& "{APKSIGNER_BAT_WIN}" verify --verbose "{win_capex_out}"'
    ]
    verify_capex_out = subprocess.check_output(cmd_verify_capex, text=True)
    if "Verified using v3 scheme (APK Signature Scheme v3): true" not in verify_capex_out:
        raise RuntimeError("apksigner verification failed on capex container!")
    say(f"[APEX] apksigner verify on capex: PASS (v3: true)")
    say(f"[APEX] Final signed capex size: {signed_capex.stat().st_size} bytes, SHA256: {sha256_file(signed_capex)}")

    return signed_capex, {
        "orig_so_sha256": h_orig,
        "patched_so_sha256": h_patched_so,
        "patched_offset": SO_PATCH_OFFSET,
        "patched_bytes": "NOP (0x1f 0x20 0x03 0xd5)",
        "manifest_version_before": 370400127,
        "manifest_version_after": 370400128,
        "capex_size": signed_capex.stat().st_size,
        "capex_sha256": sha256_file(signed_capex),
        "apex_pubkey_sha1": pub_sha1,
    }

def assemble_c43_system_tree(patched_capex: Path, work_dir: Path) -> dict[str, object]:
    say("\n[TREE] Assembling C43 system_tree from C40 baseline...")
    if C43_TREE.exists():
        shutil.rmtree(C43_TREE)
    C43_WORK.mkdir(parents=True, exist_ok=True)

    # 1. Copy C40 system_tree preserving permissions and symlinks
    run_cmd(["cp", "-a", str(C40_TREE), str(C43_TREE)])

    # 2. Replace com.android.tethering.capex
    target_capex = C43_TREE / "system/apex/com.android.tethering.capex"
    require_file(target_capex)
    old_capex_sha = sha256_file(target_capex)
    old_capex_size = target_capex.stat().st_size

    shutil.copy2(patched_capex, target_capex)
    os.chmod(target_capex, 0o644)
    new_capex_sha = sha256_file(target_capex)
    new_capex_size = target_capex.stat().st_size

    say(f"[TREE] com.android.tethering.capex updated:")
    say(f"       Before: {old_capex_size} bytes, SHA256: {old_capex_sha}")
    say(f"       After:  {new_capex_size} bytes, SHA256: {new_capex_sha}")

    # 3. Strict diff check: ONLY com.android.tethering.capex may differ from C40 tree!
    diff_res = subprocess.run(["diff", "--no-dereference", "-r", "-q", str(C40_TREE), str(C43_TREE)],
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    diff_lines = [l.strip() for l in diff_res.stdout.splitlines() if l.strip()]
    say(f"[TREE] System tree diff count against C40 baseline: {len(diff_lines)}")
    for d in diff_lines:
        say(f"  {d}")
    if len(diff_lines) != 1 or "com.android.tethering.capex" not in diff_lines[0]:
        raise RuntimeError(f"Strict single-variable violation! Unexpected diffs: {diff_lines}")
    say("[TREE] Single-variable gate PASS: strictly com.android.tethering.capex only!")

    return {
        "old_capex_sha256": old_capex_sha,
        "new_capex_sha256": new_capex_sha,
        "diff_count": len(diff_lines),
        "diff_file": "system/apex/com.android.tethering.capex",
    }

def build_system(work_dir: Path) -> tuple[Path, dict[str, object]]:
    say("\n[SYSTEM] Building system_c43.img with EROFS and AVB footer...")
    stage = work_dir / "staging"
    stage.mkdir(parents=True, exist_ok=True)

    # Use C40 staging file_contexts and fs_config
    base_contexts = C40_STAGING / "system_file_contexts_c40"
    base_fs_config = C40_STAGING / "system_fs_config_c40"
    require_file(base_contexts)
    require_file(base_fs_config)

    raw_img = stage / "system_c43.raw.erofs"
    out_img = C43_IMAGES / "system_c43.img"

    cmd_mkfs = [
        str(MKFS_EROFS), "-zlz4hc", "-T", "0", "-U", SYSTEM_UUID,
        "--mount-point=/system", f"--fs-config-file={base_fs_config}",
        f"--file-contexts={base_contexts}", str(raw_img), str(C43_TREE)
    ]
    run_cmd(cmd_mkfs, log_file=stage / "mkfs_system_c43.log")
    run_cmd([str(FSCK_EROFS), "-d0", str(raw_img)], log_file=stage / "fsck_system_c43.log")
    say(f"[SYSTEM] Raw EROFS filesystem built: {raw_img.stat().st_size} bytes")

    # Add AVB hashtree footer
    shutil.copy2(raw_img, out_img)
    cmd_avb = [
        "python3", str(AVBTOOL), "add_hashtree_footer",
        "--image", str(out_img),
        "--partition_size", str(SYSTEM_SIZE),
        "--partition_name", "system",
        "--hash_algorithm", "sha256",
        "--salt", SYSTEM_SALT,
        "--algorithm", "NONE",
        "--do_not_generate_fec"
    ]
    run_cmd(cmd_avb, log_file=stage / "avb_system_c43.log")
    require_file(out_img, SYSTEM_SIZE)

    # Verify AVB image
    verify_link = out_img.parent / "system.img"
    if verify_link.exists() or verify_link.is_symlink():
        verify_link.unlink()
    verify_link.symlink_to(out_img)
    try:
        run_cmd(["python3", str(AVBTOOL), "verify_image", "--image", str(out_img)],
                log_file=stage / "avb_verify_system_c43.log")
    finally:
        verify_link.unlink(missing_ok=True)

    info_res = run_cmd(["python3", str(AVBTOOL), "info_image", "--image", str(out_img)])
    root_digest_match = re.search(r"Root Digest:\s+([0-9a-fA-F]+)", info_res)
    if not root_digest_match:
        raise RuntimeError("Could not find root digest in system info_image!")
    system_root_digest = root_digest_match.group(1).lower()

    sys_hash = sha256_file(out_img)
    say(f"[SYSTEM] system_c43.img built! SHA256: {sys_hash}, Root Digest: {system_root_digest}")

    return out_img, {
        "bytes": out_img.stat().st_size,
        "sha256": sys_hash,
        "root_digest": system_root_digest,
        "raw_erofs_size": raw_img.stat().st_size,
    }

def update_vbmeta_system(system_img: Path, work_dir: Path) -> tuple[Path, dict[str, object]]:
    say("\n[VBMETA_SYSTEM] Updating vbmeta_system.img with new system hashtree descriptor...")
    stage = work_dir / "staging"
    out_vbmeta_sys = C43_IMAGES / "vbmeta_system.img"
    base_vbmeta_sys = C40_STAGE / "images/vbmeta_system.img"
    require_file(base_vbmeta_sys, 131072)

    sys.path.insert(0, str(TOOLS / "bootimg"))
    from avbtool import Avb, AvbHashtreeDescriptor, ImageHandler

    avb = Avb()
    _, base_header, base_descs, _ = avb._parse_image(ImageHandler(str(base_vbmeta_sys)))
    _, _, system_descs, _ = avb._parse_image(ImageHandler(str(system_img)))

    new_system = next((d for d in system_descs if isinstance(d, AvbHashtreeDescriptor) and d.partition_name == "system"), None)
    old_system = next((d for d in base_descs if isinstance(d, AvbHashtreeDescriptor) and d.partition_name == "system"), None)
    if new_system is None or old_system is None:
        raise RuntimeError("Missing system hashtree descriptor in base vbmeta_system or new system image!")

    updated_descs = [new_system if d is old_system else d for d in base_descs]

    blob = avb._generate_vbmeta_blob(
        algorithm_name="NONE", key_path=None, public_key_metadata_path=None,
        descriptors=updated_descs, chain_partitions_use_ab=None,
        chain_partitions_do_not_use_ab=None, rollback_index=base_header.rollback_index,
        flags=base_header.flags, rollback_index_location=base_header.rollback_index_location,
        props=None, props_from_file=None, kernel_cmdlines=None,
        setup_rootfs_from_kernel=None, ht_desc_to_setup=None,
        include_descriptors_from_image=None, signing_helper=None,
        signing_helper_with_files=None, release_string=base_header.release_string,
        append_to_release_string=None,
        required_libavb_version_minor=base_header.required_libavb_version_minor
    )
    if len(blob) > 131072:
        raise RuntimeError(f"vbmeta_system blob exceeds 128 KiB: {len(blob)}")
    out_vbmeta_sys.write_bytes(blob + b"\0" * (131072 - len(blob)))
    require_file(out_vbmeta_sys, 131072)

    # Verify updated vbmeta_system
    _, new_header, check_descs, _ = avb._parse_image(ImageHandler(str(out_vbmeta_sys)))
    check_system = next((d for d in check_descs if isinstance(d, AvbHashtreeDescriptor) and d.partition_name == "system"), None)
    if check_system.root_digest != new_system.root_digest:
        raise RuntimeError("System root digest mismatch in updated vbmeta_system!")

    vbmeta_sys_sha = sha256_file(out_vbmeta_sys)
    say(f"[VBMETA_SYSTEM] vbmeta_system.img regenerated! SHA256: {vbmeta_sys_sha}")
    say(f"                System Root Digest: {old_system.root_digest.hex()} -> {new_system.root_digest.hex()}")

    return out_vbmeta_sys, {
        "base_sha256": sha256_file(base_vbmeta_sys),
        "new_sha256": vbmeta_sys_sha,
        "system_root_digest_before": old_system.root_digest.hex(),
        "system_root_digest_after": new_system.root_digest.hex(),
    }

def build_super(system_img: Path, vendor_img: Path, work_dir: Path) -> tuple[Path, dict[str, object]]:
    say("\n[SUPER] Rebuilding super.img with lpmake...")
    out_super = C43_IMAGES / "super.img"
    stage = work_dir / "staging"

    mi_ext_a = C42_UNPACKED / "mi_ext_a.img"
    odm_a = C42_UNPACKED / "odm_a.img"
    product_a = C42_UNPACKED / "product_a.img"
    system_ext_a = C42_UNPACKED / "system_ext_a.img"

    inputs = {
        "mi_ext_a": mi_ext_a,
        "odm_a": odm_a,
        "product_a": product_a,
        "system_a": system_img,
        "system_ext_a": system_ext_a,
        "vendor_a": vendor_img,
    }
    input_hashes = {}
    for name, p in inputs.items():
        require_file(p)
        input_hashes[name] = {"bytes": p.stat().st_size, "sha256": sha256_file(p)}
        say(f"  {name}: {p.stat().st_size} bytes, sha256={input_hashes[name]['sha256']}")

    lpmake_log = stage / "lpmake_c43.log"
    args = [
        str(LPMAKE), "--metadata-size", "65536", "--metadata-slots", "3",
        "--device-size", str(DEVICE_SIZE), "--block-size", "4096",
        "--alignment", str(ALIGNMENT), "--virtual-ab", "--sparse",
        "--super-name", "super",
        "--group", f"qti_dynamic_partitions_a:{DEVICE_SIZE}",
        "--group", f"qti_dynamic_partitions_b:{DEVICE_SIZE}",
        "--partition", f"mi_ext_a:readonly:{inputs['mi_ext_a'].stat().st_size}:qti_dynamic_partitions_a",
        "--partition", "mi_ext_b:none:0:qti_dynamic_partitions_b",
        "--partition", f"odm_a:readonly:{inputs['odm_a'].stat().st_size}:qti_dynamic_partitions_a",
        "--partition", "odm_b:none:0:qti_dynamic_partitions_b",
        "--partition", f"product_a:readonly:{inputs['product_a'].stat().st_size}:qti_dynamic_partitions_a",
        "--partition", "product_b:none:0:qti_dynamic_partitions_b",
        "--partition", f"system_a:readonly:{inputs['system_a'].stat().st_size}:qti_dynamic_partitions_a",
        "--partition", "system_b:none:0:qti_dynamic_partitions_b",
        "--partition", f"system_ext_a:readonly:{inputs['system_ext_a'].stat().st_size}:qti_dynamic_partitions_a",
        "--partition", "system_ext_b:none:0:qti_dynamic_partitions_b",
        "--partition", f"vendor_a:readonly:{inputs['vendor_a'].stat().st_size}:qti_dynamic_partitions_a",
        "--partition", "vendor_b:none:0:qti_dynamic_partitions_b",
        "--image", f"mi_ext_a={inputs['mi_ext_a']}",
        "--image", f"odm_a={inputs['odm_a']}",
        "--image", f"product_a={inputs['product_a']}",
        "--image", f"system_a={inputs['system_a']}",
        "--image", f"system_ext_a={inputs['system_ext_a']}",
        "--image", f"vendor_a={inputs['vendor_a']}",
        "--output", str(out_super),
    ]
    run_cmd(args, log_file=lpmake_log)
    require_file(out_super)
    super_sha = sha256_file(out_super)
    say(f"[SUPER] super.img rebuilt! Size: {out_super.stat().st_size} bytes, SHA256: {super_sha}")

    # Verify LP metadata with lpdump
    say("[SUPER] Verifying super image with lpdump...")
    raw_super = stage / "super_raw_verify.img"
    run_cmd([str(SIMG2IMG), str(out_super), str(raw_super)])
    lp_text = run_cmd([str(LPDUMP), str(raw_super)])
    raw_super.unlink()
    for part in ("mi_ext_a", "odm_a", "product_a", "system_a", "system_ext_a", "vendor_a"):
        if part not in lp_text:
            raise RuntimeError(f"Partition {part} missing from lpdump!")
    say("[SUPER] LP metadata verification PASS")

    return out_super, input_hashes

def main():
    if "microsoft" not in Path("/proc/sys/kernel/osrelease").read_text().lower():
        raise RuntimeError("Must run inside Ubuntu WSL.")

    say(f"=== {CANDIDATE} BUILD ===")
    check_space()

    # Create destination directories
    C43_STAGE.mkdir(parents=True, exist_ok=True)
    C43_IMAGES.mkdir(parents=True, exist_ok=True)
    C43_WORK.mkdir(parents=True, exist_ok=True)
    C43_STAGING.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Build patched Tethering APEX
    patched_capex, apex_meta = build_patched_tethering_apex(C43_WORK)

    # 2. Assemble C43 system tree (Single-variable verification against C40)
    tree_meta = assemble_c43_system_tree(patched_capex, C43_WORK)

    # 3. Build system_c43.img with EROFS and AVB
    system_img, system_meta = build_system(C43_WORK)

    # 4. Rebuild vbmeta_system.img
    vbmeta_sys_img, vbmeta_sys_meta = update_vbmeta_system(system_img, C43_WORK)

    # 5. Inherit vendor_c42.img (100% C42 Display XML brightness fix)
    vendor_c42 = C42_STAGING / "vendor_c42.img"
    require_file(vendor_c42, VENDOR_SIZE)
    vendor_c42_sha = sha256_file(vendor_c42)
    say(f"[VENDOR] Inherited vendor_c42.img: SHA256={vendor_c42_sha}")
    if vendor_c42_sha != "615FC15C287CF81E2871D1BC00A85F5435FF29BA0C49F5D14085198D691924DE":
        raise RuntimeError(f"vendor_c42.img hash mismatch: {vendor_c42_sha}")

    # 6. Rebuild super.img with lpmake
    super_img, logical_hashes = build_super(system_img, vendor_c42, C43_WORK)

    # 7. Inherit boot images (boot.img, vendor_boot.img, dtbo.img, vbmeta.img)
    inherited_hashes = {}
    for name in ("boot.img", "vendor_boot.img", "dtbo.img", "vbmeta.img"):
        src = C42_IMAGES / name
        dst = C43_IMAGES / name
        require_file(src)
        if not dst.exists() or dst.stat().st_size != src.stat().st_size:
            shutil.copy2(src, dst)
        require_file(dst)
        inherited_hashes[name] = {"bytes": dst.stat().st_size, "sha256": sha256_file(dst)}
        say(f"[INHERITED] {name}: {dst.stat().st_size} bytes, sha256={inherited_hashes[name]['sha256']}")

    # 8. Generate Manifest
    manifest = {
        "candidate": CANDIDATE,
        "base_candidate": BASE_CANDIDATE,
        "single_variable_modification": {
            "library": "/apex/com.android.tethering/lib64/libnetd_updatable.so",
            "symbol": "libnetd_updatable_init",
            "patch_offset": SO_PATCH_OFFSET,
            "instruction_before": "cbnz w8, 115d8 (0x28 0x05 0x00 0x35)",
            "instruction_after": "nop (0x1f 0x20 0x03 0xd5)",
            "orig_so_sha256": apex_meta["orig_so_sha256"],
            "patched_so_sha256": apex_meta["patched_so_sha256"],
            "manifest_version_before": apex_meta["manifest_version_before"],
            "manifest_version_after": apex_meta["manifest_version_after"],
            "capex_sha256": apex_meta["capex_sha256"],
            "capex_size": apex_meta["capex_size"],
            "system_tree_diff": tree_meta
        },
        "system_image": system_meta,
        "vendor_image": {
            "bytes": VENDOR_SIZE,
            "sha256": vendor_c42_sha,
            "source": "Candidate 42 DisplayDeviceConfig Minimum Brightness Fix"
        },
        "vbmeta_system_image": vbmeta_sys_meta,
        "super_image": {
            "bytes": super_img.stat().st_size,
            "sha256": sha256_file(super_img)
        },
        "logical_partition_inputs": logical_hashes,
        "inherited_boot_images": inherited_hashes
    }

    manifest_path = C43_IMAGES / "BUILD_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    report_manifest = REPORT_DIR / "C43_BUILD_MANIFEST.json"
    report_manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    say(f"\n[MANIFEST] Manifest written to {manifest_path} and {report_manifest}")

    say("\n=== Candidate 43 Build Completed Successfully! ===")

if __name__ == "__main__":
    main()
