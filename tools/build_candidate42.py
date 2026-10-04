#!/usr/bin/env python3
"""Build Candidate 42: DisplayDeviceConfig Minimum Brightness Lower-Bound Minimal Fix
for Xiaomi 10S (thyme / Snapdragon 870) running HyperOS 4 / Android 17.

STRICT SINGLE-VARIABLE MODIFICATION:
Modify ONLY:
  /vendor/etc/displayconfig/display_id_4630946545580055169.xml
Specifically:
  <screenBrightnessMap>
      <point>
          <value>0.001709819</value>  ->  <value>0.000854597</value>
      </point>
All other XML nodes, attributes, framework components, libraries, and kernel remain 100% UNTOUCHED.
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
import xml.etree.ElementTree as ET
from pathlib import Path

# Paths
ROOT = Path("/path/to/thyme-os4-local")
WSL_BUILD = Path("/path/to/thyme-os4-build")

C40_STAGE = ROOT / "work/stage_c40_media_profiles_variant_20261003"
C40_IMAGES = C40_STAGE / "images"

C42_STAGE = ROOT / "work/stage_c42_display_config_fix_20261004"
C42_IMAGES = C42_STAGE / "images"
C42_WORK = WSL_BUILD / "c42_display_config_fix_20261004"
C42_STAGING = C42_WORK / "staging"
C42_UNPACKED = C42_WORK / "unpacked_super"
REPORT_DIR = ROOT / "reports/c42_candidate42_build_20261004"

# Tools
TOOLS = ROOT / "tools"
ANDROID_TOOLS = TOOLS / "android-tools-static/linux/android-tools-static"
LPMAKE = ANDROID_TOOLS / "lpmake"
SIMG2IMG = ANDROID_TOOLS / "simg2img"
LPDUMP = ANDROID_TOOLS / "lpdump"
LPUNPACK = ANDROID_TOOLS / "lpunpack"
AVBTOOL = TOOLS / "bootimg/avbtool.py"
DUMP_EROFS = TOOLS / "erofs-utils/wsl/dump.erofs"

# Partition Constants
DEVICE_SIZE = 9_126_805_504
ALIGNMENT = 1_048_576
SYSTEM_SIZE = 1_092_616_192
SYSTEM_EXT_SIZE = 942_669_824
VENDOR_SIZE = 1_510_998_016
VENDOR_FS_SIZE = 1_486_426_112
VENDOR_SALT = "869fbe2b06434e545491b0977ea070676ec7307609884d646234d592793f777f"
VENDOR_LABEL = "u:object_r:vendor_configs_file:s0"

TARGET_XML_REL = "/etc/displayconfig/display_id_4630946545580055169.xml"
OLD_VALUE = "0.001709819"
NEW_VALUE = "0.000854597"

CANDIDATE = "Candidate 42 DisplayDeviceConfig Minimum Brightness Fix"
BASE_CANDIDATE = "Candidate 40 MediaProfiles Single-Variable Property Fix"

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

def canonical_descriptor(desc: object) -> str:
    def normalize(val: object) -> object:
        if isinstance(val, bytes):
            return {"bytes_hex": val.hex()}
        if isinstance(val, (str, int, float, bool)) or val is None:
            return val
        if isinstance(val, (tuple, list)):
            return [normalize(x) for x in val]
        if isinstance(val, dict):
            return {str(k): normalize(v) for k, v in val.items()}
        return repr(val)
    return json.dumps({"type": type(desc).__name__, "fields": normalize(vars(desc))},
                      sort_keys=True, separators=(",", ":"))

def modify_vendor_xml(base_vendor: Path, work_dir: Path) -> tuple[Path, dict[str, object]]:
    say("\n[VENDOR] Preparing Candidate 42 vendor image...")
    # 1. Dump baseline XML from base_vendor
    res = subprocess.run(
        ["/usr/sbin/debugfs", "-R", f"cat {TARGET_XML_REL}", str(base_vendor)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True
    )
    old_bytes = res.stdout
    if old_bytes.startswith(b"debugfs"):
        old_bytes = old_bytes[old_bytes.find(b"\n") + 1:]
    
    old_xml_sha = sha256_bytes(old_bytes)
    say(f"[VENDOR] Baseline XML size: {len(old_bytes)} bytes, SHA256: {old_xml_sha}")

    old_target = f"<value>{OLD_VALUE}</value>".encode("ascii")
    new_target = f"<value>{NEW_VALUE}</value>".encode("ascii")
    if old_bytes.count(old_target) != 1:
        raise RuntimeError(f"Expected exactly 1 occurrence of {old_target}, found {old_bytes.count(old_target)}")
    
    new_bytes = old_bytes.replace(old_target, new_target, 1)
    new_xml_sha = sha256_bytes(new_bytes)
    say(f"[VENDOR] Target XML size: {len(new_bytes)} bytes, SHA256: {new_xml_sha}")

    diff_offsets = []
    for i, (b_old, b_new) in enumerate(zip(old_bytes, new_bytes)):
        if b_old != b_new:
            diff_offsets.append((i, chr(b_old), chr(b_new)))
    say(f"[VENDOR] XML byte diff count: {len(diff_offsets)}, offset range: {diff_offsets[0][0]}..{diff_offsets[-1][0]}")

    # Validate XML parsing
    tree = ET.fromstring(new_bytes.decode("utf-8"))
    pts = tree.findall(".//screenBrightnessMap/point")
    if len(pts) != 3 or pts[0].find("value").text != NEW_VALUE:
        raise RuntimeError("XML parse validation failed for modified content!")

    staged_xml = work_dir / "display_id_4630946545580055169.xml"
    staged_xml.write_bytes(new_bytes)

    # 2. Prepare vendor copy
    vendor_out = work_dir / "vendor_c42.img"
    shutil.copy2(base_vendor, vendor_out)
    require_file(vendor_out, VENDOR_SIZE)

    # 3. Erase AVB footer
    say("[VENDOR] Erasing AVB footer...")
    subprocess.run(["python3", str(AVBTOOL), "erase_footer", "--image", str(vendor_out)], check=True)
    if vendor_out.stat().st_size != VENDOR_FS_SIZE:
        raise RuntimeError(f"Unexpected ext4 size after erasing footer: {vendor_out.stat().st_size} != {VENDOR_FS_SIZE}")

    # 4. Patch XML with debugfs
    say("[VENDOR] Patching XML into ext4 filesystem using debugfs...")
    xattr_file = work_dir / "vendor_configs_file.label"
    xattr_file.write_bytes(VENDOR_LABEL.encode("ascii") + b"\0")

    cmd_file = work_dir / "debugfs_patch.cmds"
    cmds = [
        f"rm {TARGET_XML_REL}",
        f"write {staged_xml} {TARGET_XML_REL}",
        f"set_inode_field {TARGET_XML_REL} uid 0",
        f"set_inode_field {TARGET_XML_REL} gid 0",
        f"set_inode_field {TARGET_XML_REL} mode 0100644",
        f"ea_set -f {xattr_file} {TARGET_XML_REL} security.selinux",
    ]
    cmd_file.write_text("\n".join(cmds) + "\n", encoding="utf-8")
    dbg_res = subprocess.run(["/usr/sbin/debugfs", "-w", "-f", str(cmd_file), str(vendor_out)],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if "File not found" in dbg_res.stdout or "Command not found" in dbg_res.stdout:
        raise RuntimeError(f"debugfs failed: {dbg_res.stdout}")

    # 5. Readback verification
    readback = subprocess.run(["/usr/sbin/debugfs", "-R", f"cat {TARGET_XML_REL}", str(vendor_out)],
                              stdout=subprocess.PIPE, check=True).stdout
    if readback.startswith(b"debugfs"):
        readback = readback[readback.find(b"\n") + 1:]
    if sha256_bytes(readback) != new_xml_sha:
        raise RuntimeError("Readback XML hash does not match target XML hash!")

    # 6. e2fsck verification
    say("[VENDOR] Running e2fsck verification...")
    fsck_res = subprocess.run(["/usr/sbin/e2fsck", "-f", "-n", str(vendor_out)],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if fsck_res.returncode != 0:
        raise RuntimeError(f"e2fsck failed on patched vendor: {fsck_res.stdout}")
    say("[VENDOR] e2fsck check PASS (clean)")

    # 7. Add AVB hashtree footer
    say("[VENDOR] Adding AVB hashtree footer...")
    avb_cmd = [
        "python3", str(AVBTOOL), "add_hashtree_footer", "--image", str(vendor_out),
        "--partition_size", str(VENDOR_SIZE), "--partition_name", "vendor",
        "--hash_algorithm", "sha256", "--salt", VENDOR_SALT,
        "--algorithm", "NONE", "--do_not_generate_fec",
    ]
    subprocess.run(avb_cmd, check=True)
    require_file(vendor_out, VENDOR_SIZE)

    info_res = subprocess.run(["python3", str(AVBTOOL), "info_image", "--image", str(vendor_out)],
                              stdout=subprocess.PIPE, text=True, check=True).stdout
    root_digest_match = re.search(r"Root Digest:\s+([0-9a-fA-F]+)", info_res)
    if not root_digest_match:
        raise RuntimeError("Could not find root digest in vendor info_image!")
    vendor_root_digest = root_digest_match.group(1).lower()
    say(f"[VENDOR] vendor_c42.img successfully built! Root Digest: {vendor_root_digest}")

    return vendor_out, {
        "old_xml_sha256": old_xml_sha,
        "new_xml_sha256": new_xml_sha,
        "byte_diff_count": len(diff_offsets),
        "diff_offsets": [{"offset": o[0], "old": o[1], "new": o[2]} for o in diff_offsets],
        "vendor_sha256": sha256_file(vendor_out),
        "vendor_root_digest": vendor_root_digest,
        "vendor_size": VENDOR_SIZE
    }

def update_root_vbmeta(vendor_img: Path, base_vbmeta: Path, out_vbmeta: Path, work_dir: Path) -> dict[str, object]:
    say("\n[VBMETA] Updating root vbmeta.img with new vendor hashtree descriptor...")
    sys.path.insert(0, str(ROOT / "tools/bootimg"))
    from avbtool import Avb, AvbHashtreeDescriptor, ImageHandler

    avb = Avb()
    _, base_header, base_descs, _ = avb._parse_image(ImageHandler(str(base_vbmeta)))
    _, _, vendor_descs, _ = avb._parse_image(ImageHandler(str(vendor_img)))

    old = [d for d in base_descs if isinstance(d, AvbHashtreeDescriptor) and d.partition_name == "vendor"]
    new = [d for d in vendor_descs if isinstance(d, AvbHashtreeDescriptor) and d.partition_name == "vendor"]
    if len(old) != 1 or len(new) != 1:
        raise RuntimeError("Expected exactly 1 vendor hashtree descriptor in both base vbmeta and new vendor!")

    old_desc, new_desc = old[0], new[0]
    updated = [new_desc if desc is old_desc else desc for desc in base_descs]
    before_other = [canonical_descriptor(desc) for desc in base_descs if desc is not old_desc]

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
        raise RuntimeError(f"vbmeta blob exceeds 128 KiB: {len(blob)}")
    
    out_vbmeta.write_bytes(blob + b"\0" * (131_072 - len(blob)))
    require_file(out_vbmeta, 131_072)

    # Verify updated vbmeta
    _, new_header, new_descs, _ = avb._parse_image(ImageHandler(str(out_vbmeta)))
    after_other = [canonical_descriptor(desc) for desc in new_descs if not (isinstance(desc, AvbHashtreeDescriptor) and desc.partition_name == "vendor")]
    if before_other != after_other:
        raise RuntimeError("Non-vendor descriptors changed unexpectedly in root vbmeta!")
    
    out_sha = sha256_file(out_vbmeta)
    say(f"[VBMETA] Root vbmeta.img regenerated! SHA256: {out_sha}")
    return {
        "base_vbmeta_sha256": sha256_file(base_vbmeta),
        "new_vbmeta_sha256": out_sha,
        "vendor_root_digest_before": old_desc.root_digest.hex(),
        "vendor_root_digest_after": new_desc.root_digest.hex(),
        "other_descriptors_unchanged": True,
    }

def build_super(vendor_img: Path, unpacked_dir: Path, out_super: Path, work_dir: Path) -> tuple[Path, dict[str, object]]:
    say("\n[SUPER] Rebuilding super.img with lpmake...")
    system_a = unpacked_dir / "system_a.img"
    system_ext_a = unpacked_dir / "system_ext_a.img"
    product_a = unpacked_dir / "product_a.img"
    mi_ext_a = unpacked_dir / "mi_ext_a.img"
    odm_a = unpacked_dir / "odm_a.img"

    inputs = {
        "mi_ext_a": mi_ext_a,
        "odm_a": odm_a,
        "product_a": product_a,
        "system_a": system_a,
        "system_ext_a": system_ext_a,
        "vendor_a": vendor_img,
    }
    input_hashes = {}
    for name, p in inputs.items():
        require_file(p)
        input_hashes[name] = {"bytes": p.stat().st_size, "sha256": sha256_file(p)}
        say(f"  {name}: {p.stat().st_size} bytes, sha256={input_hashes[name]['sha256']}")

    lpmake_log = work_dir / "lpmake_c42.log"
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
    res = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    lpmake_log.write_text(res.stdout, encoding="utf-8")
    if res.returncode != 0:
        raise RuntimeError(f"lpmake failed: {res.stdout}")
    
    super_sha = sha256_file(out_super)
    say(f"[SUPER] super.img rebuilt! Size: {out_super.stat().st_size} bytes, SHA256: {super_sha}")

    # Verify LP metadata with lpdump
    say("[SUPER] Verifying super image with lpdump...")
    raw_super = work_dir / "super_raw_verify.img"
    subprocess.run([str(SIMG2IMG), str(out_super), str(raw_super)], check=True)
    lp_text = subprocess.run([str(LPDUMP), str(raw_super)], stdout=subprocess.PIPE, text=True, check=True).stdout
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
    C42_STAGE.mkdir(parents=True, exist_ok=True)
    C42_IMAGES.mkdir(parents=True, exist_ok=True)
    C42_WORK.mkdir(parents=True, exist_ok=True)
    C42_STAGING.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    base_vendor = C42_UNPACKED / "vendor_a.img"
    require_file(base_vendor, VENDOR_SIZE)

    # 1. Build modified vendor_c42.img
    vendor_c42, vendor_meta = modify_vendor_xml(base_vendor, C42_STAGING)

    # 2. Update vbmeta.img
    base_vbmeta = C40_IMAGES / "vbmeta.img"
    require_file(base_vbmeta, 131_072)
    out_vbmeta = C42_IMAGES / "vbmeta.img"
    vbmeta_meta = update_root_vbmeta(vendor_c42, base_vbmeta, out_vbmeta, C42_STAGING)

    # 3. Inherit vbmeta_system.img (UNTOUCHED)
    base_vbmeta_system = C40_IMAGES / "vbmeta_system.img"
    require_file(base_vbmeta_system, 131_072)
    out_vbmeta_system = C42_IMAGES / "vbmeta_system.img"
    shutil.copy2(base_vbmeta_system, out_vbmeta_system)
    require_file(out_vbmeta_system, 131_072)
    vbmeta_sys_sha = sha256_file(out_vbmeta_system)
    say(f"[VBMETA_SYSTEM] Inherited unchanged vbmeta_system.img: {vbmeta_sys_sha}")

    # 4. Rebuild super.img
    out_super = C42_IMAGES / "super.img"
    super_img, input_hashes = build_super(vendor_c42, C42_UNPACKED, out_super, C42_STAGING)

    # 5. Inherit small boot images (boot.img, vendor_boot.img, dtbo.img)
    inherited_hashes = {}
    for name in ("boot.img", "vendor_boot.img", "dtbo.img"):
        src = C40_IMAGES / name
        dst = C42_IMAGES / name
        require_file(src)
        if not dst.exists() or dst.stat().st_size != src.stat().st_size:
            shutil.copy2(src, dst)
        require_file(dst)
        inherited_hashes[name] = {"bytes": dst.stat().st_size, "sha256": sha256_file(dst)}
        say(f"[INHERITED] {name}: {dst.stat().st_size} bytes, sha256={inherited_hashes[name]['sha256']}")

    # 6. Generate Manifest
    manifest = {
        "candidate": CANDIDATE,
        "base_candidate": BASE_CANDIDATE,
        "single_variable_modification": {
            "file": TARGET_XML_REL,
            "old_value": OLD_VALUE,
            "new_value": NEW_VALUE,
            "old_xml_sha256": vendor_meta["old_xml_sha256"],
            "new_xml_sha256": vendor_meta["new_xml_sha256"],
            "byte_diff_count": vendor_meta["byte_diff_count"],
            "diff_offsets": vendor_meta["diff_offsets"]
        },
        "vendor_image": {
            "bytes": VENDOR_SIZE,
            "sha256": vendor_meta["vendor_sha256"],
            "root_digest": vendor_meta["vendor_root_digest"]
        },
        "vbmeta_image": vbmeta_meta,
        "vbmeta_system_image": {
            "bytes": 131_072,
            "sha256": vbmeta_sys_sha
        },
        "super_image": {
            "bytes": out_super.stat().st_size,
            "sha256": sha256_file(out_super)
        },
        "logical_partition_inputs": input_hashes,
        "inherited_boot_images": inherited_hashes
    }

    manifest_path = C42_IMAGES / "BUILD_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    report_manifest = REPORT_DIR / "C42_BUILD_MANIFEST.json"
    report_manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    say(f"\n[MANIFEST] Manifest written to {manifest_path}")

    say("\n=== Candidate 42 Build Completed Successfully! ===")

if __name__ == "__main__":
    main()
