#!/usr/bin/env python3
"""Build Candidate 46: Unified Manifest Version (370399999) & Aligned CAPEX Tethering
for Xiaomi 10S (thyme / Snapdragon 870) running HyperOS 4 / Android 17.

STRICT SINGLE-VARIABLE REPAIR:
Fix the Manifest version mismatch between container and filesystem image:
- Unifies apex_manifest.pb across all layers to canonical version 370399999 (matching apex_payload.img interior and dada/alioth baselines).
- Reuses the EXACT byte-for-byte C43/C44/C45 apex_payload.img ([REDACTED_DEVICE_ID]...) containing the 4-byte netd patch.
- Reuses the EXACT byte-for-byte C43/C44/C45 libnetd_updatable.so ([REDACTED_DEVICE_ID]...).
- Enforces AOSP standard 4096-byte alignment on apex_payload.img inside inner ordinary APEX.
- Employs apksigner --alignment-preserved with v3 signing scheme to preserve the 4096-byte alignment intact.
- Enforces zipalign -c 4096 verification on final signed inner APEX (offset % 4096 == 0).
- Encodes capexMetadata.originalApexDigest ([REDACTED_DEVICE_ID]...) into outer apex_manifest.pb matching actual payload AVB root digest.
- Rigorous Gate: Verify inner manifest is 100% byte-for-byte identical to the manifest inside the payload image filesystem.
- Preserves all C40 (codecs variant _V1_0) and C42 (display XML lower bound 0.000854597) fixes.
- End-to-end runtime equivalence gates on both staging CAPEX and EROFS readback CAPEX.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import struct
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

C43_WORK = WSL_BUILD / "c43_netd_ebpf_bypass_20261004"

C44_STAGE = ROOT / "work/stage_c44_capex_digest_fix_20261004"
C44_IMAGES = C44_STAGE / "images"
C44_WORK = WSL_BUILD / "c44_capex_digest_fix_20261004"

C45_STAGE = ROOT / "work/stage_c45_aligned_capex_20261004"
C45_IMAGES = C45_STAGE / "images"
C45_WORK = WSL_BUILD / "c45_aligned_capex_20261004"
C45_STAGING = C45_WORK / "staging"
C45_TREE = C45_WORK / "system_tree"

C46_STAGE = ROOT / "work/stage_c46_unified_manifest_capex_20261004"
C46_IMAGES = C46_STAGE / "images"
C46_WORK = WSL_BUILD / "c46_unified_manifest_capex_20261004"
C46_STAGING = C46_WORK / "staging"
C46_TREE = C46_WORK / "system_tree"
REPORT_DIR = ROOT / "reports/c46_candidate46_build_20261004"

DADA_CAPEX = ROOT / "work/three_way_tethering_check/dada_tethering.capex"

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

ZIPALIGN_EXE_WIN = r"[LOCAL_USER_PATH]"
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
EXPECTED_PAYLOAD_SHA256 = "cf284e425f8c7b9f30dbb09e7ab6010791e69f32cc943d4a2630a98f0b75d347"
EXPECTED_PATCHED_SO_SHA256 = "a70a3176b82d792cdea3ed876c90980c1d459fbcdb859d5e21f12c3a5eaf92f5"
EXPECTED_ROOT_DIGEST = "4bdfe2f9158035e7d4dd5efe814f5d1dd9eee1d9052eb7c1f571125e9c67e042"
EXPECTED_PUBKEY_SHA1 = "944fdf0f06b2c517710befe752a8931b3d4d3ca8"
EXPECTED_PACKAGE_NAME = "com.android.tethering"
EXPECTED_VERSION_INT = 370399999  # Canonical version from dada donor and internal ext4 filesystem

CANDIDATE = "Candidate 46 Unified Manifest Version & Aligned CAPEX Tethering"
BASE_CANDIDATE = "Candidate 45 Aligned CAPEX Tethering (Loop Mount Breakthrough)"

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
            length = 0; shift = 0
            while True:
                vb = data[idx]; idx += 1
                length |= (vb & 0x7f) << shift
                if not (vb & 0x80): break
                shift += 7
            val = data[idx:idx+length]; idx += length
            if fn == 1:
                parsed["name"] = val.decode("utf-8", errors="ignore")
            elif fn == 11 or fn == 12:  # capexMetadata
                sub_idx = 0
                while sub_idx < len(val):
                    sub_b = val[sub_idx]; sub_idx += 1
                    sub_fn = sub_b >> 3; sub_wt = sub_b & 7
                    if sub_wt == 2:
                        sub_len = 0; sub_s = 0
                        while True:
                            svb = val[sub_idx]; sub_idx += 1
                            sub_len |= (svb & 0x7f) << sub_s
                            if not (svb & 0x80): break
                            sub_s += 7
                        sub_val = val[sub_idx:sub_idx+sub_len]; sub_idx += sub_len
                        if sub_fn == 1:
                            parsed["originalApexDigest"] = sub_val.decode("utf-8", errors="ignore")
                    else:
                        break
    return parsed

def get_zip_entry_data_offset(zip_bytes: bytes, target_filename: str) -> tuple[int, int]:
    """Return (data_offset, compress_type) for the target file inside zip bytes."""
    idx = 0
    while idx < len(zip_bytes) - 30:
        if zip_bytes[idx:idx+4] == b'PK\x03\x04':
            compress_type = struct.unpack('<H', zip_bytes[idx+8:idx+10])[0]
            fn_len = struct.unpack('<H', zip_bytes[idx+26:idx+28])[0]
            extra_len = struct.unpack('<H', zip_bytes[idx+28:idx+30])[0]
            fn = zip_bytes[idx+30:idx+30+fn_len].decode("utf-8", errors="ignore")
            if fn == target_filename:
                data_offset = idx + 30 + fn_len + extra_len
                return data_offset, compress_type
            idx += 30 + fn_len + extra_len
        else:
            idx += 1
    raise RuntimeError(f"Entry {target_filename} not found in zip bytes!")

def to_win_path(p: Path) -> str:
    """Convert WSL /root/... or /mnt/e/... path to Windows path."""
    s = str(p.resolve())
    if s.startswith("/mnt/"):
        drive = s[5].upper()
        rest = s[6:].replace("/", "\\")
        return f"{drive}:{rest}"
    elif s.startswith("/root"):
        rest = s[5:].replace("/", "\\")
        return f"\\\\wsl.localhost\\Ubuntu\\root{rest}"
    else:
        rest = s.replace("/", "\\")
        return f"\\\\wsl.localhost\\Ubuntu{rest}"

def verify_capex_runtime_equivalence(capex_path: Path, context: str) -> dict[str, object]:
    say(f"\n[GATE-EQUIVALENCE] Verifying CAPEX runtime equivalence ({context}): {capex_path.name}")
    require_file(capex_path)

    with open(capex_path, "rb") as f:
        capex_bytes = f.read()

    with zipfile.ZipFile(io_capex := zipfile.io.BytesIO(capex_bytes), "r") as z_capex:
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
        say(f"  Extracted original_apex size: {len(orig_apex_bytes)} bytes, SHA256: {orig_apex_sha256}")

        # 3. Check inner APEX alignment and contents
        payload_offset, payload_comp = get_zip_entry_data_offset(orig_apex_bytes, "apex_payload.img")
        say(f"  Inner original_apex apex_payload.img ZIP data offset: {payload_offset}")
        say(f"  Inner original_apex apex_payload.img compress_type:    {payload_comp} (0=STORED)")

        if payload_comp != 0:
            raise RuntimeError(f"apex_payload.img MUST be STORED (0), got {payload_comp}")
        if payload_offset % 4096 != 0:
            raise RuntimeError(f"FATAL: apex_payload.img offset {payload_offset} is NOT 4096-aligned! ({payload_offset % 4096})")
        say(f"  CRITICAL CHECK: payload offset {payload_offset} % 4096 == 0: ALIGNED PASS!")

        # 4. Write temp original_apex to verify zipalign -c 4096 and apksigner
        tmp_orig = Path(f"/tmp/verify_orig_{os.getpid()}.apex")
        tmp_orig.write_bytes(orig_apex_bytes)
        try:
            win_orig = to_win_path(tmp_orig)
            cmd_za = ["powershell.exe", "-NoProfile", "-Command",
                      f'& "{ZIPALIGN_EXE_WIN}" -c -v 4096 "{win_orig}"']
            za_out = run_cmd(cmd_za)
            if "apex_payload.img (OK)" not in za_out:
                raise RuntimeError(f"zipalign -c 4096 did not verify apex_payload.img as OK:\n{za_out}")
            say("  CRITICAL CHECK: zipalign -c 4096 verification: PASS (OK)")

            cmd_as = ["powershell.exe", "-NoProfile", "-Command",
                      f'& "{APKSIGNER_BAT_WIN}" verify --verbose "{win_orig}"']
            as_out = run_cmd(cmd_as)
            if "Verified using v3 scheme (APK Signature Scheme v3): true" not in as_out:
                raise RuntimeError(f"apksigner verify v3 failed on inner original_apex:\n{as_out}")
            say("  Inner original_apex signature verification: PASS (v3: true)")

            with zipfile.ZipFile(tmp_orig, "r") as z_orig:
                inner_manifest_raw = z_orig.read("apex_manifest.pb")
                inner_meta = parse_apex_manifest_pb(inner_manifest_raw)
                say(f"  Inner manifest parsed: {inner_meta}")
                if inner_meta.get("name") != outer_pkg:
                    raise RuntimeError(f"Package mismatch between inner ({inner_meta.get('name')}) and outer ({outer_pkg})")
                if inner_meta.get("version") != outer_ver:
                    raise RuntimeError(f"Version mismatch between inner ({inner_meta.get('version')}) and outer ({outer_ver})")

                # Check AndroidManifest.xml versionCode
                manifest_xml = z_orig.read("AndroidManifest.xml")
                ver_found = False
                for off in range(0, len(manifest_xml) - 4, 2):
                    val = struct.unpack('<I', manifest_xml[off:off+4])[0]
                    if val == EXPECTED_VERSION_INT:
                        ver_found = True
                        break
                if not ver_found:
                    raise RuntimeError(f"AndroidManifest.xml does not contain expected versionCode {EXPECTED_VERSION_INT}!")
                say(f"  AndroidManifest.xml contains versionCode {EXPECTED_VERSION_INT}: PASS")

                # Check pubkey identity
                inner_pub = z_orig.read("apex_pubkey")
                outer_pub = z_capex.read("apex_pubkey")
                if inner_pub != outer_pub:
                    raise RuntimeError("Pubkey mismatch between inner original_apex and outer capex!")
                pub_sha1 = hashlib.sha1(inner_pub).hexdigest().lower()
                if pub_sha1 != EXPECTED_PUBKEY_SHA1:
                    raise RuntimeError(f"Pubkey SHA1 mismatch: {pub_sha1} != {EXPECTED_PUBKEY_SHA1}")
                say(f"  Pubkey identity: {pub_sha1} PASS")

                # Extract inner payload and calculate AVB root digest & verify netd patched SO
                payload_data = z_orig.read("apex_payload.img")
                payload_sha256 = sha256_bytes(payload_data).lower()
                say(f"  Inner payload SHA256: {payload_sha256}")
                if payload_sha256 != EXPECTED_PAYLOAD_SHA256:
                    raise RuntimeError(f"Payload SHA256 mismatch! {payload_sha256} != {EXPECTED_PAYLOAD_SHA256}")
                say("  Inner payload SHA256 matches C45/C44/C43: EXACT MATCH PASS")

                # CRITICAL MANIFEST BYTE-FOR-BYTE CHECK:
                # Inode 93 (/apex_manifest.pb) inside payload ext4 image
                payload_manifest_pos = 36093952
                payload_manifest_bytes = payload_data[payload_manifest_pos:payload_manifest_pos+len(inner_manifest_raw)]
                say(f"  Comparing container inner_manifest ({len(inner_manifest_raw)} B) with payload filesystem manifest ({len(payload_manifest_bytes)} B)...")
                if inner_manifest_raw != payload_manifest_bytes:
                    say(f"  Inner manifest hex:   {inner_manifest_raw.hex()[:60]}...")
                    say(f"  Payload manifest hex: {payload_manifest_bytes.hex()[:60]}...")
                    raise RuntimeError("FATAL: Container inner manifest DOES NOT MATCH manifest inside filesystem! VerifyManifestMatches() will fail!")
                say("  CRITICAL CHECK: Container manifest == Payload filesystem manifest: 100% BYTE-FOR-BYTE EXACT MATCH PASS!")

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

                # Verify libnetd_updatable.so presence in payload
                so_marker = b"libnetd_updatable.so"
                if so_marker not in payload_data:
                    raise RuntimeError("libnetd_updatable.so marker not found in payload image!")
                say("  libnetd_updatable.so binary present in payload: CONFIRMED")

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
        "payload_offset": payload_offset,
        "payload_offset_mod_4096": payload_offset % 4096,
        "payload_compress_type": payload_comp,
        "payload_sha256": payload_sha256,
        "original_apex_sha256": orig_apex_sha256,
        "pubkey_sha1": pub_sha1,
        "manifest_exact_match": True
    }

def build_candidate46_aligned_capex(work_dir: Path) -> tuple[Path, dict[str, object]]:
    say("\n=======================================================")
    say("=== STEP 1: Constructing Candidate 46 Aligned CAPEX ===")
    say("===       Unified Manifest Version: 370399999        ===")
    say("=======================================================")
    apex_work = work_dir / "tethering_apex"
    apex_work.mkdir(parents=True, exist_ok=True)

    # 1. Source C45 original_apex for entries
    c45_capex = C45_WORK / "system_tree/system/apex/com.android.tethering.capex"
    require_file(c45_capex)
    say(f"[C46-APEX] Sourcing clean entries from C45 CAPEX: {c45_capex}")

    with zipfile.ZipFile(c45_capex, "r") as z_capex:
        c45_orig_apex_bytes = z_capex.read("original_apex")

    with zipfile.ZipFile(io_orig := zipfile.io.BytesIO(c45_orig_apex_bytes), "r") as z_orig:
        inner_entries = {name: z_orig.read(name) for name in z_orig.namelist() if not name.startswith("META-INF/")}

    say(f"[C46-APEX] Clean inner entries extracted ({len(inner_entries)} entries): {list(inner_entries.keys())}")
    for req in ["apex_payload.img", "apex_pubkey", "AndroidManifest.xml", "resources.arsc", "apex_build_info.pb"]:
        if req not in inner_entries:
            raise RuntimeError(f"Missing required inner entry: {req}")

    # 2. Source the canonical 598-byte manifest with version 370399999
    # Extract from dada_tethering.capex
    require_file(DADA_CAPEX)
    with zipfile.ZipFile(DADA_CAPEX, "r") as z_dada_capex:
        dada_orig = z_dada_capex.read("original_apex")
    with zipfile.ZipFile(io_dada := zipfile.io.BytesIO(dada_orig), "r") as z_dada_orig:
        dada_inner_manifest = z_dada_orig.read("apex_manifest.pb")

    say(f"[C46-APEX] Sourced dada inner manifest: {len(dada_inner_manifest)} bytes")
    parsed_dada_manifest = parse_apex_manifest_pb(dada_inner_manifest)
    say(f"[C46-APEX] Parsed dada manifest: {parsed_dada_manifest}")
    if parsed_dada_manifest.get("name") != EXPECTED_PACKAGE_NAME:
        raise RuntimeError(f"Manifest package mismatch: {parsed_dada_manifest.get('name')}")
    if parsed_dada_manifest.get("version") != EXPECTED_VERSION_INT:
        raise RuntimeError(f"Manifest version mismatch: {parsed_dada_manifest.get('version')} != {EXPECTED_VERSION_INT}")

    # Set inner_manifest_bytes to the unified 598-byte manifest
    inner_manifest_bytes = dada_inner_manifest
    inner_entries["apex_manifest.pb"] = inner_manifest_bytes

    # 3. Verify payload SHA256 before packaging
    payload_bytes = inner_entries["apex_payload.img"]
    h_payload = sha256_bytes(payload_bytes).lower()
    say(f"[C46-APEX] Payload size: {len(payload_bytes)} bytes, SHA256: {h_payload}")
    if h_payload != EXPECTED_PAYLOAD_SHA256:
        raise RuntimeError(f"Payload hash mismatch! Expected {EXPECTED_PAYLOAD_SHA256}, got {h_payload}")

    # Verify AVB root digest via avbtool
    tmp_p = apex_work / "extracted_payload.img"
    tmp_p.write_bytes(payload_bytes)
    digests_out = run_cmd(["python3", str(AVBTOOL), "print_partition_digests", "--image", str(tmp_p)])
    actual_root_digest = digests_out.strip().split(": ")[1].strip().lower()
    say(f"[C46-APEX] Payload AVB root digest: {actual_root_digest}")
    if actual_root_digest != EXPECTED_ROOT_DIGEST:
        raise RuntimeError(f"Root digest mismatch: {actual_root_digest} != {EXPECTED_ROOT_DIGEST}")

    # Verify manifest inside payload matches inner_manifest_bytes
    payload_manifest_pos = 36093952
    payload_manifest_bytes = payload_bytes[payload_manifest_pos:payload_manifest_pos+len(inner_manifest_bytes)]
    if payload_manifest_bytes != inner_manifest_bytes:
        raise RuntimeError("Payload internal manifest does not match unified inner manifest!")
    say("[C46-APEX] Payload internal manifest == Unified inner manifest: EXACT MATCH CONFIRMED")

    # 4. Assemble unsigned inner APEX container
    # Standard APEX structure: apex_payload.img is placed FIRST as uncompressed STORED entry
    unsigned_inner = apex_work / "com.android.tethering.unsigned.apex"
    aligned_inner = apex_work / "com.android.tethering.aligned.apex"
    signed_inner = apex_work / "com.android.tethering.apex"

    say(f"[C46-APEX] Assembling unsigned inner APEX: {unsigned_inner}...")
    with zipfile.ZipFile(unsigned_inner, "w") as z_out:
        # Write apex_payload.img FIRST as uncompressed STORED
        z_out.writestr("apex_payload.img", payload_bytes, compress_type=zipfile.ZIP_STORED)
        for name, data in inner_entries.items():
            if name != "apex_payload.img":
                comp = zipfile.ZIP_STORED if name == "resources.arsc" else zipfile.ZIP_DEFLATED
                z_out.writestr(name, data, compress_type=comp)

    require_file(unsigned_inner)

    # 5. Align unsigned inner APEX using zipalign -f 4096
    win_unsigned_inner = to_win_path(unsigned_inner)
    win_aligned_inner = to_win_path(aligned_inner)

    cmd_align_inner = [
        "powershell.exe", "-NoProfile", "-Command",
        f'& "{ZIPALIGN_EXE_WIN}" -f 4096 "{win_unsigned_inner}" "{win_aligned_inner}"'
    ]
    say("[C46-APEX] Aligning inner APEX container with zipalign -f 4096...")
    run_cmd(cmd_align_inner)
    require_file(aligned_inner)

    # Inspect offset of aligned_inner
    with open(aligned_inner, "rb") as f:
        aligned_bytes = f.read()
    aligned_offset, aligned_comp = get_zip_entry_data_offset(aligned_bytes, "apex_payload.img")
    say(f"[C46-APEX] aligned_inner payload offset: {aligned_offset} (mod 4096: {aligned_offset % 4096})")
    if aligned_offset % 4096 != 0:
        raise RuntimeError(f"aligned_inner failed 4096 alignment: offset {aligned_offset}")

    # 6. Sign inner APEX using apksigner with --alignment-preserved
    key_pk8 = C43_WORK / "tethering_apex/c43_tethering_apex_key.pk8"
    cert_pem = C43_WORK / "tethering_apex/c43_tethering_apex_cert.pem"
    require_file(key_pk8)
    require_file(cert_pem)

    win_key = to_win_path(key_pk8)
    win_cert = to_win_path(cert_pem)
    win_signed_inner = to_win_path(signed_inner)

    cmd_sign_inner = [
        "powershell.exe", "-NoProfile", "-Command",
        f'& "{APKSIGNER_BAT_WIN}" sign --key "{win_key}" --cert "{win_cert}" --v2-signing-enabled false --v3-signing-enabled true --alignment-preserved --out "{win_signed_inner}" "{win_aligned_inner}"'
    ]
    say("[C46-APEX] Signing inner APEX container with apksigner (v3, --alignment-preserved)...")
    run_cmd(cmd_sign_inner)
    require_file(signed_inner)

    # 7. Rigorous Gate Verification on signed inner APEX
    with open(signed_inner, "rb") as f:
        signed_inner_bytes = f.read()
    signed_inner_offset, signed_inner_comp = get_zip_entry_data_offset(signed_inner_bytes, "apex_payload.img")
    say(f"[C46-APEX] Final signed_inner payload offset: {signed_inner_offset} (mod 4096: {signed_inner_offset % 4096})")
    if signed_inner_offset % 4096 != 0:
        raise RuntimeError(f"FATAL: signed_inner payload offset {signed_inner_offset} is NOT 4096-aligned after signing!")

    cmd_check_inner = [
        "powershell.exe", "-NoProfile", "-Command",
        f'& "{ZIPALIGN_EXE_WIN}" -c -v 4096 "{win_signed_inner}"'
    ]
    check_inner_out = run_cmd(cmd_check_inner)
    if "apex_payload.img (OK)" not in check_inner_out:
        raise RuntimeError(f"zipalign -c 4096 failed on signed_inner:\n{check_inner_out}")
    say("[C46-APEX] zipalign -c 4096 on signed_inner: PASS (apex_payload.img OK)")

    cmd_verify_inner = [
        "powershell.exe", "-NoProfile", "-Command",
        f'& "{APKSIGNER_BAT_WIN}" verify --verbose "{win_signed_inner}"'
    ]
    verify_inner_out = run_cmd(cmd_verify_inner)
    if "Verified using v3 scheme (APK Signature Scheme v3): true" not in verify_inner_out:
        raise RuntimeError(f"apksigner verify v3 failed on signed_inner:\n{verify_inner_out}")
    say("[C46-APEX] apksigner verify on signed_inner: PASS (v3: true)")

    # 8. Construct outer apex_manifest.pb with capexMetadata.originalApexDigest
    # Proto chunk: tag 12 wire type 2 (0x62), length 0x42 (66 bytes), subtag 1 wire type 2 (0x0a), length 0x40 (64 bytes), sha256 ascii (64 bytes)
    capex_metadata_chunk = b'\x62\x42\n@' + actual_root_digest.encode("ascii")
    outer_manifest = inner_manifest_bytes + capex_metadata_chunk
    if len(outer_manifest) != 666:
        raise RuntimeError(f"Unexpected outer manifest length: {len(outer_manifest)} != 666")

    parsed_outer = parse_apex_manifest_pb(outer_manifest)
    say(f"[C46-APEX] Constructed outer manifest parsed: {parsed_outer}")
    if parsed_outer.get("version") != EXPECTED_VERSION_INT:
        raise RuntimeError(f"Outer manifest version mismatch: {parsed_outer.get('version')} != {EXPECTED_VERSION_INT}")
    if parsed_outer.get("originalApexDigest") != actual_root_digest:
        raise RuntimeError("Failed to verify encoded originalApexDigest in outer manifest!")

    # 9. Assemble unsigned CAPEX container
    unsigned_capex = apex_work / "com.android.tethering.unsigned.capex"
    aligned_capex = apex_work / "com.android.tethering.aligned.capex"
    signed_capex = apex_work / "com.android.tethering.capex"

    say(f"[C46-APEX] Assembling unsigned CAPEX: {unsigned_capex}...")
    with zipfile.ZipFile(unsigned_capex, "w") as z_capex_out:
        z_capex_out.writestr("AndroidManifest.xml", inner_entries["AndroidManifest.xml"], compress_type=zipfile.ZIP_STORED)
        z_capex_out.writestr("apex_build_info.pb", inner_entries["apex_build_info.pb"], compress_type=zipfile.ZIP_STORED)
        z_capex_out.writestr("apex_manifest.pb", outer_manifest, compress_type=zipfile.ZIP_STORED)
        z_capex_out.writestr("apex_pubkey", inner_entries["apex_pubkey"], compress_type=zipfile.ZIP_STORED)
        with open(signed_inner, "rb") as f_orig:
            z_capex_out.writestr("original_apex", f_orig.read(), compress_type=zipfile.ZIP_DEFLATED)

    require_file(unsigned_capex)

    # 10. Align and sign outer CAPEX container
    win_unsigned_capex = to_win_path(unsigned_capex)
    win_aligned_capex = to_win_path(aligned_capex)
    win_signed_capex = to_win_path(signed_capex)

    cmd_align_capex = [
        "powershell.exe", "-NoProfile", "-Command",
        f'& "{ZIPALIGN_EXE_WIN}" -f 4096 "{win_unsigned_capex}" "{win_aligned_capex}"'
    ]
    say("[C46-APEX] Aligning CAPEX container with zipalign -f 4096...")
    run_cmd(cmd_align_capex)
    require_file(aligned_capex)

    cmd_sign_capex = [
        "powershell.exe", "-NoProfile", "-Command",
        f'& "{APKSIGNER_BAT_WIN}" sign --key "{win_key}" --cert "{win_cert}" --v2-signing-enabled false --v3-signing-enabled true --alignment-preserved --out "{win_signed_capex}" "{win_aligned_capex}"'
    ]
    say("[C46-APEX] Signing CAPEX container with apksigner (v3, --alignment-preserved)...")
    run_cmd(cmd_sign_capex)
    require_file(signed_capex)

    cmd_verify_capex = [
        "powershell.exe", "-NoProfile", "-Command",
        f'& "{APKSIGNER_BAT_WIN}" verify --verbose "{win_signed_capex}"'
    ]
    verify_capex_out = run_cmd(cmd_verify_capex)
    if "Verified using v3 scheme (APK Signature Scheme v3): true" not in verify_capex_out:
        raise RuntimeError("apksigner verification failed on capex container!")
    say("[C46-APEX] apksigner verify on signed_capex: PASS (v3: true)")

    # 11. Execute full runtime equivalence gate on newly assembled staging CAPEX
    equiv_report = verify_capex_runtime_equivalence(signed_capex, "STAGING_CAPEX")

    return signed_capex, equiv_report

def assemble_c46_system_tree(signed_capex: Path, work_dir: Path) -> dict[str, object]:
    say("\n[TREE] Assembling Candidate 46 system tree based on C40...")
    sys_tree = C46_TREE
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

def build_system_c46_image(signed_capex: Path, work_dir: Path) -> tuple[Path, dict[str, object]]:
    say("\n=======================================================")
    say("=== STEP 2: Preparing System Tree & EROFS Image ===")
    say("=======================================================")

    tree_meta = assemble_c46_system_tree(signed_capex, work_dir)
    stage = C46_STAGING
    stage.mkdir(parents=True, exist_ok=True)

    base_contexts = C40_STAGING / "system_file_contexts_c40"
    base_fs_config = C40_STAGING / "system_fs_config_c40"
    require_file(base_contexts)
    require_file(base_fs_config)

    raw_img = stage / "system_c46.raw.erofs"
    out_img = C46_IMAGES / "system_c46.img"
    C46_IMAGES.mkdir(parents=True, exist_ok=True)

    cmd_mkfs = [
        str(MKFS_EROFS), "-zlz4hc", "-T", "0", "-U", SYSTEM_UUID,
        "--mount-point=/system", f"--fs-config-file={base_fs_config}",
        f"--file-contexts={base_contexts}", str(raw_img), str(C46_TREE)
    ]
    run_cmd(cmd_mkfs, log_file=stage / "mkfs_system_c46.log")
    run_cmd([str(FSCK_EROFS), "-d0", str(raw_img)], log_file=stage / "fsck_system_c46.log")
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
    run_cmd(cmd_avb, log_file=stage / "avb_system_c46.log")
    require_file(out_img, SYSTEM_SIZE)

    # Verify AVB image
    verify_link = out_img.parent / "system.img"
    if verify_link.exists() or verify_link.is_symlink():
        verify_link.unlink()
    verify_link.symlink_to(out_img)
    try:
        run_cmd(["python3", str(AVBTOOL), "verify_image", "--image", str(out_img)],
                log_file=stage / "avb_verify_system_c46.log")
    finally:
        verify_link.unlink(missing_ok=True)

    info_res = run_cmd(["python3", str(AVBTOOL), "info_image", "--image", str(out_img)])
    root_digest_match = re.search(r"Root Digest:\s+([0-9a-fA-F]+)", info_res)
    if not root_digest_match:
        raise RuntimeError("Could not find root digest in system info_image!")
    system_root_digest = root_digest_match.group(1).lower()

    sys_hash = sha256_file(out_img)
    say(f"[SYSTEM] system_c46.img built! SHA256: {sys_hash}, Root Digest: {system_root_digest}")

    # EROFS Readback Verification
    say("\n[C46-READBACK] Extracting com.android.tethering.capex from final system_c46.img...")
    extracted_capex_path = stage / "extracted_readback.capex"
    with open(extracted_capex_path, "wb") as f_out:
        subprocess.check_call(
            [str(DUMP_EROFS), "--cat", "--path=/system/apex/com.android.tethering.capex", str(out_img)],
            stdout=f_out
        )
    require_file(extracted_capex_path)

    h_extracted = sha256_file(extracted_capex_path)
    h_staging = sha256_file(signed_capex)
    say(f"[C46-READBACK] Staging CAPEX SHA256:   {h_staging}")
    say(f"[C46-READBACK] Readback CAPEX SHA256:  {h_extracted}")
    if h_extracted != h_staging:
        raise RuntimeError(f"Readback CAPEX hash mismatch! {h_extracted} != {h_staging}")
    say("[C46-READBACK] Exact byte match between staging and image readback: PASS")

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
    out_vbmeta_sys = C46_IMAGES / "vbmeta_system.img"
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
    out_super = C46_IMAGES / "super.img"
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

    lpmake_log = stage / "lpmake_c46.log"
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
    C46_STAGE.mkdir(parents=True, exist_ok=True)
    C46_IMAGES.mkdir(parents=True, exist_ok=True)
    C46_WORK.mkdir(parents=True, exist_ok=True)
    C46_STAGING.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Build Candidate 46 signed CAPEX with unified manifest version and 4096-aligned inner APEX
    signed_capex, capex_meta = build_candidate46_aligned_capex(C46_WORK)

    # 2. Build system_c46.img with EROFS and AVB + Readback verification
    system_img, system_meta = build_system_c46_image(signed_capex, C46_WORK)

    # 3. Rebuild vbmeta_system.img
    vbmeta_sys_img, vbmeta_sys_meta = update_vbmeta_system(system_img, C46_WORK)

    # 4. Inherit vendor_c42.img (100% C42 Display XML brightness fix)
    vendor_c42 = C42_STAGING / "vendor_c42.img"
    require_file(vendor_c42, VENDOR_SIZE)
    vendor_c42_sha = sha256_file(vendor_c42)
    say(f"[VENDOR] Inherited vendor_c42.img: SHA256={vendor_c42_sha}")
    if vendor_c42_sha != "615FC15C287CF81E2871D1BC00A85F5435FF29BA0C49F5D14085198D691924DE":
        raise RuntimeError(f"vendor_c42.img hash mismatch: {vendor_c42_sha}")

    # 5. Rebuild super.img with lpmake
    super_img, logical_hashes = build_super(system_img, vendor_c42, C46_WORK)

    # 6. Inherit boot images (boot.img, vendor_boot.img, dtbo.img, vbmeta.img)
    inherited_hashes = {}
    for name in ("boot.img", "vendor_boot.img", "dtbo.img", "vbmeta.img"):
        src = C42_IMAGES / name
        dst = C46_IMAGES / name
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
            "component": "/system/apex/com.android.tethering.capex",
            "fix": "Unified apex_manifest.pb version to canonical 370399999 matching payload ext4 filesystem & retained 4096-byte ZIP data alignment",
            "c45_inner_payload_offset": 4096,
            "c46_inner_payload_offset": capex_meta["payload_offset"],
            "c46_inner_payload_offset_mod_4096": capex_meta["payload_offset_mod_4096"],
            "library": "/apex/com.android.tethering/lib64/libnetd_updatable.so",
            "symbol": "libnetd_updatable_init",
            "netd_patch": "4-byte NOP (0x1f 0x20 0x03 0xd5) retained identical to C43",
            "patched_so_sha256": EXPECTED_PATCHED_SO_SHA256,
            "payload_sha256": EXPECTED_PAYLOAD_SHA256,
            "manifest_version": EXPECTED_VERSION_INT,
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

    manifest_path = C46_IMAGES / "BUILD_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    report_manifest = REPORT_DIR / "C46_BUILD_MANIFEST.json"
    report_manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    say(f"\n[MANIFEST] Manifest written to {manifest_path} and {report_manifest}")

    say("\n=== Candidate 46 Build Completed Successfully! ===")

if __name__ == "__main__":
    main()
