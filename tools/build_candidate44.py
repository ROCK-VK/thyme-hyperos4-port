#!/usr/bin/env python3
"""Build Candidate 44: Fix Tethering CAPEX originalApexDigest & System Integration
for Xiaomi 10S (thyme / Snapdragon 870) running HyperOS 4 / Android 17.

STRICT SINGLE-VARIABLE REPAIR:
Fix ONLY the packaging defect of /system/apex/com.android.tethering.capex:
- Reuses the EXACT byte-for-byte C43 original_apex ([REDACTED_DEVICE_ID]...) containing the 4-byte netd patch.
- Retains version 370400128 (varint b'\\x80\\xb6\\xcf\\xb0\\x01').
- Injects the computed root digest ([REDACTED_DEVICE_ID]...) into capexMetadata.originalApexDigest of the outer apex_manifest.pb.
- Performs end-to-end runtime equivalence gates on both staging CAPEX and EROFS readback CAPEX.
All C40 (codecs variant _V1_0) and C42 (display XML lower bound 0.000854597) are 100% inherited.
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

C44_STAGE = ROOT / "work/stage_c44_capex_digest_fix_20261004"
C44_IMAGES = C44_STAGE / "images"
C44_WORK = WSL_BUILD / "c44_capex_digest_fix_20261004"
C44_STAGING = C44_WORK / "staging"
C44_TREE = C44_WORK / "system_tree"
REPORT_DIR = ROOT / "reports/c44_candidate44_build_20261004"

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

# Expected Hashes & Constants
EXPECTED_ORIGINAL_APEX_SHA256 = "c6c010d1d829ac138e0c93889728167202c8f510b3f5948fe900cc2006cfbfd3"
EXPECTED_PATCHED_SO_SHA256 = "a70a3176b82d792cdea3ed876c90980c1d459fbcdb859d5e21f12c3a5eaf92f5"
EXPECTED_ROOT_DIGEST = "4bdfe2f9158035e7d4dd5efe814f5d1dd9eee1d9052eb7c1f571125e9c67e042"
EXPECTED_PUBKEY_SHA1 = "944fdf0f06b2c517710befe752a8931b3d4d3ca8"
EXPECTED_PACKAGE_NAME = "com.android.tethering"
EXPECTED_VERSION_INT = 370400000  # Encoded as \x80\xb6\xcf\xb0\x01 in C43 original_apex (referred to as 370400128 in C43 logs)

CANDIDATE = "Candidate 44 Tethering CAPEX originalApexDigest Fix"
BASE_CANDIDATE = "Candidate 43 Netd eBPF Init Abort Surgical Bypass"

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

def parse_apex_manifest_pb(data: bytes) -> dict[str, object]:
    parsed: dict[str, object] = {}
    idx = 0
    while idx < len(data):
        b = data[idx]; idx += 1
        fn = b >> 3; wt = b & 7
        if wt == 0:  # varint
            v = 0; shift = 0
            while True:
                vb = data[idx]; idx += 1
                v |= (vb & 0x7f) << shift
                if not (vb & 0x80): break
                shift += 7
            if fn == 2:
                parsed["version"] = v
        elif wt == 2:  # length-delimited
            length = data[idx]; idx += 1
            val = data[idx:idx+length]; idx += length
            if fn == 1:
                parsed["name"] = val.decode("utf-8", errors="ignore")
            elif fn == 12:  # capexMetadata
                if len(val) >= 2 and val[0] == 0x0a:
                    sub_len = val[1]
                    sub_str = val[2:2+sub_len].decode("utf-8", errors="ignore")
                    parsed["originalApexDigest"] = sub_str
    return parsed

def verify_capex_runtime_equivalence(capex_path: Path, context: str) -> dict[str, object]:
    say(f"\n[GATE-EQUIVALENCE] Verifying CAPEX runtime equivalence ({context}): {capex_path.name}")
    require_file(capex_path)
    
    with zipfile.ZipFile(capex_path, "r") as z_capex:
        capex_entries = z_capex.namelist()
        say(f"  CAPEX zip entries: {capex_entries}")
        for req in ["original_apex", "apex_manifest.pb", "apex_pubkey", "AndroidManifest.xml"]:
            if req not in capex_entries:
                raise RuntimeError(f"Missing required entry '{req}' in {capex_path.name}")
        
        # 1. Check outer manifest
        outer_manifest_raw = z_capex.read("apex_manifest.pb")
        outer_meta = parse_apex_manifest_pb(outer_manifest_raw)
        say(f"  Outer manifest parsed: {outer_meta}")
        
        outer_pkg = outer_meta.get("name")
        outer_ver = outer_meta.get("version")
        outer_digest = outer_meta.get("originalApexDigest")
        
        if outer_pkg != EXPECTED_PACKAGE_NAME:
            raise RuntimeError(f"Outer package name mismatch: {outer_pkg} != {EXPECTED_PACKAGE_NAME}")
        if outer_ver != EXPECTED_VERSION_INT:
            raise RuntimeError(f"Outer version mismatch: {outer_ver} != {EXPECTED_VERSION_INT}")
        if not outer_digest:
            raise RuntimeError("Outer manifest MISSING capexMetadata.originalApexDigest!")
        say(f"  Outer originalApexDigest: {outer_digest}")
        
        # 2. Extract and inspect original_apex
        orig_apex_bytes = z_capex.read("original_apex")
        orig_apex_sha256 = sha256_bytes(orig_apex_bytes).lower()
        say(f"  Extracted original_apex SHA256: {orig_apex_sha256}")
        if orig_apex_sha256 != EXPECTED_ORIGINAL_APEX_SHA256:
            raise RuntimeError(f"original_apex SHA256 mismatch with C43 input! {orig_apex_sha256} != {EXPECTED_ORIGINAL_APEX_SHA256}")
        say("  original_apex SHA256 match with C43 input: EXACT MATCH PASS")
        
        # 3. Inspect inner original_apex contents
        tmp_orig = Path(f"/tmp/verify_orig_{os.getpid()}.apex")
        tmp_orig.write_bytes(orig_apex_bytes)
        try:
            with zipfile.ZipFile(tmp_orig, "r") as z_orig:
                inner_manifest_raw = z_orig.read("apex_manifest.pb")
                inner_meta = parse_apex_manifest_pb(inner_manifest_raw)
                say(f"  Inner manifest parsed: {inner_meta}")
                if inner_meta.get("name") != outer_pkg:
                    raise RuntimeError(f"Package mismatch between inner ({inner_meta.get('name')}) and outer ({outer_pkg})")
                if inner_meta.get("version") != outer_ver:
                    raise RuntimeError(f"Version mismatch between inner ({inner_meta.get('version')}) and outer ({outer_ver})")
                
                # Check pubkey identity
                inner_pub = z_orig.read("apex_pubkey")
                outer_pub = z_capex.read("apex_pubkey")
                if inner_pub != outer_pub:
                    raise RuntimeError("Pubkey mismatch between inner original_apex and outer capex!")
                pub_sha1 = hashlib.sha1(inner_pub).hexdigest().lower()
                if pub_sha1 != EXPECTED_PUBKEY_SHA1:
                    raise RuntimeError(f"Pubkey SHA1 mismatch: {pub_sha1} != {EXPECTED_PUBKEY_SHA1}")
                say(f"  Pubkey identity: {pub_sha1} PASS")
                
                # Extract inner payload and calculate AVB root digest
                payload_data = z_orig.read("apex_payload.img")
                tmp_payload = Path(f"/tmp/verify_payload_{os.getpid()}.img")
                tmp_payload.write_bytes(payload_data)
                try:
                    digests_out = run_cmd(["python3", str(AVBTOOL), "print_partition_digests", "--image", str(tmp_payload)])
                    actual_root_digest = digests_out.strip().split(": ")[1].strip().lower()
                    say(f"  Actual payload root digest via avbtool: {actual_root_digest}")
                    
                    if actual_root_digest != EXPECTED_ROOT_DIGEST:
                        raise RuntimeError(f"Actual root digest mismatch: {actual_root_digest} != {EXPECTED_ROOT_DIGEST}")
                    if outer_digest.lower() != actual_root_digest:
                        raise RuntimeError(f"FATAL: Outer manifest originalApexDigest ({outer_digest}) != Actual root digest ({actual_root_digest})!")
                    say("  CRITICAL CHECK: outer originalApexDigest == actual payload root digest: EXACT MATCH PASS!")
                finally:
                    if tmp_payload.exists(): tmp_payload.unlink()
        finally:
            if tmp_orig.exists(): tmp_orig.unlink()
            
    say(f"[GATE-EQUIVALENCE] {context} runtime equivalence: 100% PASS\n")
    return {
        "context": context,
        "outer_package": outer_pkg,
        "outer_version": outer_ver,
        "outer_originalApexDigest": outer_digest,
        "actual_payload_root_digest": actual_root_digest,
        "digest_match": True,
        "original_apex_sha256": orig_apex_sha256,
        "pubkey_sha1": pub_sha1,
    }

def build_candidate44_capex(work_dir: Path) -> tuple[Path, dict[str, object]]:
    say("\n=======================================================")
    say("=== STEP 1: Constructing Candidate 44 CAPEX ===")
    say("=======================================================")
    apex_work = work_dir / "tethering_apex"
    apex_work.mkdir(parents=True, exist_ok=True)
    
    # 1. Source the exact C43 original_apex
    c43_original_apex = C43_WORK / "tethering_apex/com.android.tethering.apex"
    require_file(c43_original_apex)
    c43_apex_sha = sha256_file(c43_original_apex).lower()
    say(f"[C44-APEX] Sourcing C43 original_apex: {c43_original_apex}")
    say(f"[C44-APEX] C43 original_apex SHA256: {c43_apex_sha}")
    if c43_apex_sha != EXPECTED_ORIGINAL_APEX_SHA256:
        raise RuntimeError(f"C43 original_apex hash mismatch! Expected {EXPECTED_ORIGINAL_APEX_SHA256}, got {c43_apex_sha}")
    
    # 2. Extract metadata and calculate payload root digest
    with zipfile.ZipFile(c43_original_apex, "r") as z_in:
        android_manifest = z_in.read("AndroidManifest.xml")
        apex_build_info = z_in.read("apex_build_info.pb")
        inner_manifest = z_in.read("apex_manifest.pb")
        apex_pubkey = z_in.read("apex_pubkey")
        payload_data = z_in.read("apex_payload.img")
    
    tmp_payload = apex_work / "extracted_payload.img"
    tmp_payload.write_bytes(payload_data)
    digests_out = run_cmd(["python3", str(AVBTOOL), "print_partition_digests", "--image", str(tmp_payload)])
    actual_root_digest = digests_out.strip().split(": ")[1].strip().lower()
    say(f"[C44-APEX] avbtool print_partition_digests root digest: {actual_root_digest}")
    if actual_root_digest != EXPECTED_ROOT_DIGEST:
        raise RuntimeError(f"Unexpected root digest: {actual_root_digest} != {EXPECTED_ROOT_DIGEST}")
    
    # 3. Construct outer apex_manifest.pb with capexMetadata.originalApexDigest
    capex_metadata_chunk = b'\x62\x42\n@' + actual_root_digest.encode("ascii")
    outer_manifest = inner_manifest + capex_metadata_chunk
    if len(outer_manifest) != 666:
        raise RuntimeError(f"Unexpected outer manifest length: {len(outer_manifest)} != 666")
    
    # Verify parsing
    parsed_outer = parse_apex_manifest_pb(outer_manifest)
    say(f"[C44-APEX] Constructed outer manifest parsed: {parsed_outer}")
    if parsed_outer.get("originalApexDigest") != actual_root_digest:
        raise RuntimeError("Failed to verify encoded originalApexDigest in outer manifest!")
    
    # 4. Assemble unsigned CAPEX
    unsigned_capex = apex_work / "com.android.tethering.unsigned.capex"
    signed_capex = apex_work / "com.android.tethering.capex"
    
    say(f"[C44-APEX] Assembling unsigned CAPEX: {unsigned_capex}...")
    with zipfile.ZipFile(unsigned_capex, "w") as z_out:
        z_out.writestr("AndroidManifest.xml", android_manifest, compress_type=zipfile.ZIP_STORED)
        z_out.writestr("apex_build_info.pb", apex_build_info, compress_type=zipfile.ZIP_STORED)
        z_out.writestr("apex_manifest.pb", outer_manifest, compress_type=zipfile.ZIP_STORED)
        z_out.writestr("apex_pubkey", apex_pubkey, compress_type=zipfile.ZIP_STORED)
        with open(c43_original_apex, "rb") as f_orig:
            z_out.writestr("original_apex", f_orig.read(), compress_type=zipfile.ZIP_DEFLATED)
    
    # 5. Sign CAPEX with apksigner (v3 scheme) using C43 RSA-4096 key
    key_pk8 = C43_WORK / "tethering_apex/c43_tethering_apex_key.pk8"
    cert_pem = C43_WORK / "tethering_apex/c43_tethering_apex_cert.pem"
    require_file(key_pk8)
    require_file(cert_pem)
    
    wsl_prefix = r"\\wsl.localhost\Ubuntu"
    win_key = wsl_prefix + str(key_pk8).replace("/", "\\")
    win_cert = wsl_prefix + str(cert_pem).replace("/", "\\")
    win_in = wsl_prefix + str(unsigned_capex).replace("/", "\\")
    win_out = wsl_prefix + str(signed_capex).replace("/", "\\")
    
    cmd_sign_capex = [
        "powershell.exe", "-NoProfile", "-Command",
        f'& "{APKSIGNER_BAT_WIN}" sign --key "{win_key}" --cert "{win_cert}" --v2-signing-enabled false --v3-signing-enabled true --out "{win_out}" "{win_in}"'
    ]
    say("[C44-APEX] Signing capex container with apksigner (v3)...")
    subprocess.check_call(cmd_sign_capex)
    require_file(signed_capex)
    
    cmd_verify_capex = [
        "powershell.exe", "-NoProfile", "-Command",
        f'& "{APKSIGNER_BAT_WIN}" verify --verbose "{win_out}"'
    ]
    verify_capex_out = subprocess.check_output(cmd_verify_capex, text=True)
    if "Verified using v3 scheme (APK Signature Scheme v3): true" not in verify_capex_out:
        raise RuntimeError("apksigner verification failed on capex container!")
    say("[C44-APEX] apksigner verify on signed_capex: PASS (v3: true)")
    
    # 6. Execute runtime equivalence gate on newly assembled staging CAPEX
    equiv_report = verify_capex_runtime_equivalence(signed_capex, "STAGING_CAPEX")
    
    return signed_capex, equiv_report

def assemble_c44_system_tree(signed_capex: Path, work_dir: Path) -> dict[str, object]:
    say("\n[TREE] Assembling Candidate 44 system tree based on C40...")
    sys_tree = C44_TREE
    if sys_tree.exists():
        shutil.rmtree(sys_tree)
    
    say(f"  Copying baseline system tree from {C40_TREE} -> {sys_tree}...")
    run_cmd(f"cp -a {C40_TREE} {sys_tree}")
    
    # Verify build.prop codec property is present
    build_prop = sys_tree / "system/build.prop"
    require_file(build_prop)
    prop_content = build_prop.read_text(encoding="utf-8")
    if "ro.media.xml_variant.codecs=_V1_0" not in prop_content:
        raise RuntimeError("C40 fix missing in build.prop!")
    say("  Verified C40 fix ro.media.xml_variant.codecs=_V1_0 present: PASS")
    
    # Replace com.android.tethering.capex
    target_capex = sys_tree / "system/apex/com.android.tethering.capex"
    require_file(target_capex)
    old_capex_sha = sha256_file(target_capex)
    old_capex_size = target_capex.stat().st_size
    
    shutil.copy2(signed_capex, target_capex)
    os.chmod(target_capex, 0o644)
    new_capex_sha = sha256_file(target_capex)
    new_capex_size = target_capex.stat().st_size
    
    say(f"[TREE] com.android.tethering.capex updated:")
    say(f"       Before: {old_capex_size} bytes, SHA256: {old_capex_sha}")
    say(f"       After:  {new_capex_size} bytes, SHA256: {new_capex_sha}")
    
    # Strict diff check: ONLY com.android.tethering.capex may differ from C40 tree!
    diff_res = subprocess.run(["diff", "--no-dereference", "-r", "-q", str(C40_TREE), str(sys_tree)],
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

def build_system_c44_image(signed_capex: Path, work_dir: Path) -> tuple[Path, dict[str, object]]:
    say("\n=======================================================")
    say("=== STEP 2: Preparing System Tree & EROFS Image ===")
    say("=======================================================")
    
    tree_meta = assemble_c44_system_tree(signed_capex, work_dir)
    stage = C44_STAGING
    stage.mkdir(parents=True, exist_ok=True)
    
    base_contexts = C40_STAGING / "system_file_contexts_c40"
    base_fs_config = C40_STAGING / "system_fs_config_c40"
    require_file(base_contexts)
    require_file(base_fs_config)
    
    raw_img = stage / "system_c44.raw.erofs"
    out_img = C44_IMAGES / "system_c44.img"
    C44_IMAGES.mkdir(parents=True, exist_ok=True)
    
    cmd_mkfs = [
        str(MKFS_EROFS), "-zlz4hc", "-T", "0", "-U", SYSTEM_UUID,
        "--mount-point=/system", f"--fs-config-file={base_fs_config}",
        f"--file-contexts={base_contexts}", str(raw_img), str(C44_TREE)
    ]
    run_cmd(cmd_mkfs, log_file=stage / "mkfs_system_c44.log")
    run_cmd([str(FSCK_EROFS), "-d0", str(raw_img)], log_file=stage / "fsck_system_c44.log")
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
    run_cmd(cmd_avb, log_file=stage / "avb_system_c44.log")
    require_file(out_img, SYSTEM_SIZE)
    
    # Verify AVB image
    verify_link = out_img.parent / "system.img"
    if verify_link.exists() or verify_link.is_symlink():
        verify_link.unlink()
    verify_link.symlink_to(out_img)
    try:
        run_cmd(["python3", str(AVBTOOL), "verify_image", "--image", str(out_img)],
                log_file=stage / "avb_verify_system_c44.log")
    finally:
        verify_link.unlink(missing_ok=True)
        
    info_res = run_cmd(["python3", str(AVBTOOL), "info_image", "--image", str(out_img)])
    root_digest_match = re.search(r"Root Digest:\s+([0-9a-fA-F]+)", info_res)
    if not root_digest_match:
        raise RuntimeError("Could not find root digest in system info_image!")
    system_root_digest = root_digest_match.group(1).lower()
    
    sys_hash = sha256_file(out_img)
    say(f"[SYSTEM] system_c44.img built! SHA256: {sys_hash}, Root Digest: {system_root_digest}")
    
    # EROFS Readback Verification
    say("\n[C44-READBACK] Extracting com.android.tethering.capex from final system_c44.img...")
    extracted_capex_path = stage / "extracted_readback.capex"
    with open(extracted_capex_path, "wb") as f_out:
        subprocess.check_call(
            [str(DUMP_EROFS), "--cat", "--path=/system/apex/com.android.tethering.capex", str(out_img)],
            stdout=f_out
        )
    require_file(extracted_capex_path)
    
    h_extracted = sha256_file(extracted_capex_path)
    h_staging = sha256_file(signed_capex)
    say(f"[C44-READBACK] Staging CAPEX SHA256:   {h_staging}")
    say(f"[C44-READBACK] Readback CAPEX SHA256:  {h_extracted}")
    if h_extracted != h_staging:
        raise RuntimeError(f"Readback CAPEX hash mismatch! {h_extracted} != {h_staging}")
    say("[C44-READBACK] Exact byte match between staging and image readback: PASS")
    
    # Execute full runtime equivalence gate on the READBACK CAPEX
    readback_equiv = verify_capex_runtime_equivalence(extracted_capex_path, "READBACK_IMAGE_CAPEX")
    
    return out_img, {
        "bytes": out_img.stat().st_size,
        "sha256": sys_hash,
        "root_digest": system_root_digest,
        "raw_erofs_size": raw_img.stat().st_size,
        "tree_meta": tree_meta,
        "readback_equiv": readback_equiv
    }

def update_vbmeta_system(system_img: Path, work_dir: Path) -> tuple[Path, dict[str, object]]:
    say("\n[VBMETA_SYSTEM] Updating vbmeta_system.img with new system hashtree descriptor...")
    stage = work_dir / "staging"
    out_vbmeta_sys = C44_IMAGES / "vbmeta_system.img"
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
    out_super = C44_IMAGES / "super.img"
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

    lpmake_log = stage / "lpmake_c44.log"
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
    storage = check_space()

    # Create destination directories
    C44_STAGE.mkdir(parents=True, exist_ok=True)
    C44_IMAGES.mkdir(parents=True, exist_ok=True)
    C44_WORK.mkdir(parents=True, exist_ok=True)
    C44_STAGING.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Build Candidate 44 signed CAPEX with injected originalApexDigest
    signed_capex, capex_meta = build_candidate44_capex(C44_WORK)

    # 2. Build system_c44.img with EROFS and AVB + Readback verification
    system_img, system_meta = build_system_c44_image(signed_capex, C44_WORK)

    # 3. Rebuild vbmeta_system.img
    vbmeta_sys_img, vbmeta_sys_meta = update_vbmeta_system(system_img, C44_WORK)

    # 4. Inherit vendor_c42.img (100% C42 Display XML brightness fix)
    vendor_c42 = C42_STAGING / "vendor_c42.img"
    require_file(vendor_c42, VENDOR_SIZE)
    vendor_c42_sha = sha256_file(vendor_c42)
    say(f"[VENDOR] Inherited vendor_c42.img: SHA256={vendor_c42_sha}")
    if vendor_c42_sha != "615FC15C287CF81E2871D1BC00A85F5435FF29BA0C49F5D14085198D691924DE":
        raise RuntimeError(f"vendor_c42.img hash mismatch: {vendor_c42_sha}")

    # 5. Rebuild super.img with lpmake
    super_img, logical_hashes = build_super(system_img, vendor_c42, C44_WORK)

    # 6. Inherit boot images (boot.img, vendor_boot.img, dtbo.img, vbmeta.img)
    inherited_hashes = {}
    for name in ("boot.img", "vendor_boot.img", "dtbo.img", "vbmeta.img"):
        src = C42_IMAGES / name
        dst = C44_IMAGES / name
        require_file(src)
        if not dst.exists() or dst.stat().st_size != src.stat().st_size:
            shutil.copy2(src, dst)
        require_file(dst)
        inherited_hashes[name] = {"bytes": dst.stat().st_size, "sha256": sha256_file(dst)}
        say(f"[INHERITED] {name}: {dst.stat().st_size} bytes, sha256={inherited_hashes[name]['sha256']}")

    # 7. Generate Manifest
    manifest = {
        "candidate": CANDIDATE,
        "base_candidate": BASE_CANDIDATE,
        "storage": storage,
        "single_variable_modification": {
            "library": "/apex/com.android.tethering/lib64/libnetd_updatable.so",
            "symbol": "libnetd_updatable_init",
            "netd_patch": "4-byte NOP (0x1f 0x20 0x03 0xd5) retained identical to C43",
            "patched_so_sha256": EXPECTED_PATCHED_SO_SHA256,
            "manifest_version": EXPECTED_VERSION_INT,
            "original_apex_sha256": EXPECTED_ORIGINAL_APEX_SHA256,
            "actual_payload_root_digest": EXPECTED_ROOT_DIGEST,
            "outer_original_apex_digest": EXPECTED_ROOT_DIGEST,
            "capex_sha256": sha256_file(signed_capex),
            "capex_size": signed_capex.stat().st_size,
            "capex_meta": capex_meta,
            "system_tree_diff": system_meta["tree_meta"]
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

    manifest_path = C44_IMAGES / "BUILD_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    report_manifest = REPORT_DIR / "C44_BUILD_MANIFEST.json"
    report_manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    say(f"\n[MANIFEST] Manifest written to {manifest_path} and {report_manifest}")

    say("\n=== Candidate 44 Build Completed Successfully! ===")

if __name__ == "__main__":
    main()
