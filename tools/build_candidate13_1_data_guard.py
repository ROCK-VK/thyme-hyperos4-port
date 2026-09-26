#!/usr/bin/env python3
"""Build a C13.1 variant that removes explicit fstab check/format triggers.

This is a host-only image builder. It never invokes Fastboot or ADB and never
modifies the pinned Candidate 13 source images. The only filesystem-option
changes are removal of `check` and `formattable` from the normal-boot
/metadata and /data entries in first-stage and runtime fstabs. This does not
disable fs_mgr checks triggered by an unclean filesystem state, journal replay,
or other normal boot-time writes.
"""

from __future__ import annotations

import hashlib
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
C13_IMAGES = ROOT / "work" / "stage_c_thyme_os4_candidate_13_treble_ion_fix" / "images"
OUT_ROOT = ROOT / "work" / "stage_c_thyme_os4_candidate_13_1_data_guard"
OUT_IMAGES = OUT_ROOT / "images_c13_1_attempt_04"
BUILD = OUT_ROOT / "build" / "attempt_04"
VENDOR_PROBE = OUT_ROOT / "build" / "vendor_c13_1_probe.img"
VBOOT_UNPACK = OUT_ROOT / "inputs" / "vendor_boot_unpack"
C13_EXTRACT = "[LOCAL_WSL_USER]/c13_audit/rootcause_lp_20260925_2145/extract_c13_key_20260925"
WSL_ROOT = "/path/to/thyme-os4-local"
TOOLS = WSL_ROOT + "/tools"
AVBTOOL = ROOT / "tools" / "bootimg" / "avbtool.py"
MKBOOTIMG = ROOT / "tools" / "bootimg" / "mkbootimg.py"

C13_EXPECTED = {
    "boot.img": (201_326_592, "E5A016056D5C93C7A886980A7C062617EC44DC06A48417D7DD0F4476708A6368"),
    "vendor_boot.img": (100_663_296, "02333B82BA936F1BAAB1ECAB744632C70F8FC16688A206C7041EF319F112A137"),
    "dtbo.img": (33_554_432, "50E1AC0EDCBD333778217AA6FE8D972F6FF85ADD0DAE8A015A6642C2172DD886"),
    "vbmeta.img": (131_072, "013335BCA9B312E0BEFF737D30903A9B0A1EF829BA19A7BD5802BF83C04F40E9"),
    "vbmeta_system.img": (131_072, "BF4155CD99F125B8CAD26490FD2F3412EA4389F090CE56F36FAA2BF2A759C633"),
    "super.img": (7_684_274_964, "8AFEFDDBCA2357D003DEF055418CC08A832B91EA08EDCB40DEECBEBD42FA2252"),
}

LOGICAL_EXPECTED = {
    "mi_ext_a.img": (202_375_168, "43ED8FC0D1848F5D53BFB7206AC91FE5E5ED4E3F71E958D49F2EEA4C9C8B4BCE"),
    "odm_a.img": (36_700_160, "46AE3BFBBF1BB14DE348D04B9D2569B7EE239A7E293F5D0FF78C1EF54604C347"),
    "product_a.img": (4_387_241_984, "87955DBE97AC28B01A214273BD03F36B5886310DC3B2E4128B9F4661E1C3345E"),
    "system_a.img": (1_092_616_192, "EE85F2459A6054F6F3B04A3485E552198EF1DFE06E302527A27BD63FC9ADC2B4"),
    "system_ext_a.img": (942_669_824, "34598E99D7FB63FC52966A620426AB2BCF7280D2CBC51093626488F6BD4A560C"),
    "vendor_a.img": (1_510_998_016, "A53B926922E74DF76112C3DA76481A9D9BA175D3381026F35C212A0A636C68A0"),
}

PARTITION_EXTENTS = {
    "mi_ext_a": 202_375_168,
    "odm_a": 36_700_160,
    "product_a": 4_387_241_984,
    "system_a": 1_092_616_192,
    "system_ext_a": 942_669_824,
    "vendor_a": 1_510_998_016,
}
LP_DEVICE_SIZE = 9_126_805_504
VENDOR_RAW_SIZE = 1_486_426_112
VENDOR_BOOT_PARTITION_SIZE = 100_663_296
VENDOR_BOOT_SALT = "c5ffc2c51fef1864ad27e6903e582f52611121819811b66eb40f6ea9b60350c5"
VENDOR_SALT = "869fbe2b06434e545491b0977ea070676ec7307609884d646234d592793f777f"
ANDROID17_VENDOR_CMDLINE = (
    "androidboot.console=ttyMSM0 androidboot.fstab_suffix=qcom androidboot.hardware=qcom "
    "androidboot.init_fatal_reboot_target=recovery androidboot.memcg=1 "
    "androidboot.usbcontroller=a600000.dwc3 cgroup.memory=nokmem,nosocket "
    "deferred_probe_timeout=300 iptable_raw.raw_before_defrag=1 ip6table_raw.raw_before_defrag=1 "
    "loop.max_part=7 lpm_levels.sleep_disabled=1 msm_rtb.filter=0x237 reboot=panic_warm "
    "service_locator.enable=1 androidboot.init_fatal_panic=true"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def run(command: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    print("[HOST] " + " ".join(shlex.quote(str(item)) for item in command), flush=True)
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.stdout:
        print(result.stdout, end="", flush=True)
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr, flush=True)
    if result.returncode:
        raise RuntimeError(f"Command failed ({result.returncode}): {command}")
    return result


def run_wsl(command: str) -> str:
    result = run(["wsl.exe", "-d", "Ubuntu", "--", "bash", "-lc", command])
    return result.stdout.replace("\x00", "")


def wsl_path(path: Path) -> str:
    absolute = path.resolve()
    if absolute.drive.upper() != "E:":
        raise ValueError(f"C13.1 work files must remain on E:, got {absolute}")
    return "/mnt/e/" + absolute.as_posix().split(":/", 1)[1]


def patch_fstab_same_length(data: bytes, required_mounts: set[str]) -> tuple[bytes, set[str]]:
    output: list[bytes] = []
    seen: set[str] = set()
    for raw_line in data.splitlines(keepends=True):
        ending = b""
        body = raw_line
        if body.endswith(b"\r\n"):
            body, ending = body[:-2], b"\r\n"
        elif body.endswith(b"\n"):
            body, ending = body[:-1], b"\n"
        text = body.decode("ascii")
        fields = text.split()
        if not fields or fields[0].startswith("#") or len(fields) < 5 or fields[1] not in required_mounts:
            output.append(raw_line)
            continue
        mount = fields[1]
        if mount in seen:
            raise ValueError(f"Expected one normal fstab entry for {mount}; found a duplicate")
        seen.add(mount)
        old_flags = fields[4]
        for flag in ("check", "formattable"):
            if old_flags.count(f",{flag},") != 1:
                raise ValueError(f"Expected exactly one ,{flag}, token on {mount}: {old_flags}")
        new_flags = old_flags.replace(",check,", ",").replace(",formattable,", ",")
        removed = len(old_flags) - len(new_flags)
        start = body.rfind(fields[4].encode("ascii"))
        if start < 0:
            raise ValueError(f"Could not locate fs_mgr flags on {mount}")
        new_body = body[:start] + new_flags.encode("ascii") + body[start + len(old_flags):] + (b" " * removed)
        if len(new_body) != len(body):
            raise AssertionError(f"Patch changed fstab line length for {mount}")
        patched_fields = new_body.decode("ascii").split()
        patched_flags = patched_fields[4]
        if any(f",{flag}," in f",{patched_flags}," for flag in ("check", "formattable")):
            raise AssertionError(f"Guard flags remain on {mount}: {patched_flags}")
        if mount == "/data":
            for token in ("fileencryption=", "metadata_encryption=", "keydirectory="):
                if token not in patched_flags:
                    raise AssertionError(f"Encryption option {token} was lost from /data")
        if mount == "/metadata" and not all(token in patched_flags for token in ("first_stage_mount", "wrappedkey", "metadata_csum")):
            raise AssertionError("A /metadata mount option was changed unexpectedly")
        output.append(new_body + ending)
    if seen != required_mounts:
        raise ValueError(f"Normal-boot fstab entries missing: expected {required_mounts}, found {seen}")
    patched = b"".join(output)
    if len(patched) != len(data):
        raise AssertionError("Fstab patch must preserve the exact byte length")
    return patched, seen


def patch_newc_cpio(path: Path, target_name: str) -> tuple[str, bytes, bytes]:
    data = bytearray(path.read_bytes())
    offset = 0
    hits: list[tuple[int, int, int, str]] = []
    trailer_seen = False
    while offset + 110 <= len(data):
        magic = bytes(data[offset:offset + 6])
        if magic not in (b"070701", b"070702"):
            raise ValueError(f"Invalid newc magic at offset 0x{offset:x}: {magic!r}")
        fields = [int(bytes(data[offset + 6 + i * 8:offset + 14 + i * 8]), 16) for i in range(13)]
        file_size = fields[6]
        name_size = fields[11]
        name_begin = offset + 110
        name_end = name_begin + name_size
        name = bytes(data[name_begin:name_end - 1]).decode("utf-8", errors="strict")
        content_begin = (name_end + 3) & ~3
        content_end = content_begin + file_size
        next_entry = (content_end + 3) & ~3
        if name == target_name:
            hits.append((content_begin, file_size, content_end, name))
        if name == "TRAILER!!!":
            trailer_seen = True
            break
        if next_entry > len(data):
            raise ValueError(f"Truncated newc archive at entry {name}")
        offset = next_entry
    if not trailer_seen:
        raise ValueError("newc archive has no TRAILER!!!")
    if len(hits) != 1:
        raise ValueError(f"Expected one {target_name} entry in vendor ramdisk, found {len(hits)}")
    begin, file_size, _end, _name = hits[0]
    original = bytes(data[begin:begin + file_size])
    patched, _ = patch_fstab_same_length(original, {"/metadata", "/data"})
    data[begin:begin + file_size] = patched
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest(), original, patched


def patch_vendor_data_blocks(image: Path, original_fstab: bytes, patched_fstab: bytes, block_size: int, blocks: list[int]) -> None:
    if len(original_fstab) != len(patched_fstab):
        raise ValueError("Runtime fstab patch must preserve its exact byte length")
    expected_blocks = (len(original_fstab) + block_size - 1) // block_size
    if len(blocks) != expected_blocks:
        raise ValueError(f"Unexpected extent map: expected {expected_blocks} blocks, found {blocks}")
    remaining = memoryview(patched_fstab)
    with image.open("r+b") as stream:
        for block in blocks:
            chunk = bytes(remaining[:block_size])
            remaining = remaining[len(chunk):]
            stream.seek(block * block_size)
            stream.write(chunk)
    if remaining:
        raise AssertionError("Did not write the entire patched fstab")


def main() -> int:
    if not OUT_IMAGES.is_dir() or not BUILD.is_dir() or not VBOOT_UNPACK.is_dir():
        raise SystemExit("C13.1 isolated output/input directories are missing")
    if any(OUT_IMAGES.iterdir()):
        raise SystemExit(f"Refusing to overwrite existing Candidate 13.1 images: {OUT_IMAGES}")

    print("=== Candidate 13.1 data guard build (host only) ===", flush=True)
    for name, (expected_size, expected_hash) in C13_EXPECTED.items():
        source = C13_IMAGES / name
        if not source.is_file() or source.stat().st_size != expected_size:
            raise SystemExit(f"Candidate 13 source image missing or size mismatch: {source}")
        actual = sha256_file(source)
        if actual != expected_hash:
            raise SystemExit(f"Candidate 13 source hash mismatch for {name}: {actual}")
        print(f"[PINNED C13] {name} {expected_size} {actual}", flush=True)

    for name in ("boot.img", "dtbo.img", "vbmeta_system.img", "system_ext_c13.img"):
        shutil.copy2(C13_IMAGES / name, OUT_IMAGES / name)

    # Runtime vendor ext4 is extracted from the audited C13 super. Keep its
    # filesystem inode/xattr metadata unchanged by patching only the two data
    # blocks containing /etc/fstab.qcom; the byte length remains identical.
    vendor_raw = BUILD / "vendor_raw.img"
    expected_vendor_raw = wsl_path(vendor_raw)
    if not VENDOR_PROBE.is_file() or VENDOR_PROBE.stat().st_size != PARTITION_EXTENTS["vendor_a"]:
        raise SystemExit("Expected untouched full-size C13 vendor probe image is missing or has the wrong size")
    if vendor_raw.exists():
        raise SystemExit(f"Refusing to overwrite existing C13.1 vendor working image: {vendor_raw}")
    shutil.copy2(VENDOR_PROBE, vendor_raw)
    run_wsl(f"truncate -s {VENDOR_RAW_SIZE} {shlex.quote(expected_vendor_raw)}")
    if vendor_raw.stat().st_size != VENDOR_RAW_SIZE:
        raise SystemExit("Could not derive the descriptor-sized vendor ext4 working copy")
    vendor_source = C13_EXTRACT + "/vendor_a.img"
    vendor_fstab_file = BUILD / "vendor_fstab_c13_original.txt"
    run_wsl(f"debugfs -R {shlex.quote('cat /etc/fstab.qcom')} {shlex.quote(vendor_source)} 2>/dev/null > {shlex.quote(wsl_path(vendor_fstab_file))}")
    original_vendor_fstab = vendor_fstab_file.read_bytes()
    patched_vendor_fstab, _ = patch_fstab_same_length(original_vendor_fstab, {"/metadata", "/data"})
    (BUILD / "vendor_fstab_c13_1.txt").write_bytes(patched_vendor_fstab)

    info = run_wsl(
        f"dumpe2fs -h {shlex.quote(expected_vendor_raw)} 2>/dev/null | grep 'Block size:'; "
        f"debugfs -R {shlex.quote('blocks /etc/fstab.qcom')} {shlex.quote(expected_vendor_raw)} 2>/dev/null"
    )
    block_size_match = re.search(r"Block size:\s+(\d+)", info)
    block_line = next((line for line in info.splitlines() if re.fullmatch(r"\s*\d+(?:\s+\d+)+\s*", line)), None)
    if not block_size_match or not block_line:
        raise SystemExit(f"Could not read ext4 block geometry for /etc/fstab.qcom: {info!r}")
    block_size = int(block_size_match.group(1))
    blocks = [int(item) for item in block_line.split()]
    patch_vendor_data_blocks(vendor_raw, original_vendor_fstab, patched_vendor_fstab, block_size, blocks)

    verified_vendor_fstab = BUILD / "vendor_fstab_c13_1_verified.txt"
    run_wsl(f"debugfs -R {shlex.quote('cat /etc/fstab.qcom')} {shlex.quote(expected_vendor_raw)} 2>/dev/null > {shlex.quote(wsl_path(verified_vendor_fstab))}")
    if verified_vendor_fstab.read_bytes() != patched_vendor_fstab:
        raise SystemExit("Read-back verification of runtime vendor fstab failed")
    run_wsl(f"e2fsck -fn {shlex.quote(expected_vendor_raw)}")
    shutil.copy2(vendor_raw, OUT_IMAGES / "vendor_a.img")
    run([sys.executable, str(AVBTOOL), "add_hashtree_footer", "--image", str(OUT_IMAGES / "vendor_a.img"),
         "--partition_size", str(PARTITION_EXTENTS["vendor_a"]), "--partition_name", "vendor",
         "--hash_algorithm", "sha256", "--salt", VENDOR_SALT, "--algorithm", "NONE", "--do_not_generate_fec"])

    # Patch only the first-stage CPIO payload; all entry headers, ownership,
    # modes, timestamps, and all other file payloads remain byte-for-byte.
    original_ramdisk = VBOOT_UNPACK / "vendor_ramdisk"
    cpio_original = BUILD / "vendor_ramdisk_c13.cpio"
    cpio_guard = BUILD / "vendor_ramdisk_c13_1.cpio"
    cpio_target = "first_stage_ramdisk/system/etc/fstab.qcom"
    run_wsl(f"lz4 -dc {shlex.quote(wsl_path(original_ramdisk))} > {shlex.quote(wsl_path(cpio_original))}")
    shutil.copy2(cpio_original, cpio_guard)
    cpio_hash, original_first_stage, patched_first_stage = patch_newc_cpio(cpio_guard, cpio_target)
    (BUILD / "first_stage_fstab_c13_original.txt").write_bytes(original_first_stage)
    (BUILD / "first_stage_fstab_c13_1.txt").write_bytes(patched_first_stage)
    compressed_ramdisk = BUILD / "vendor_ramdisk_c13_1.lz4"
    run_wsl(f"lz4 -l -12 --favor-decSpeed {shlex.quote(wsl_path(cpio_guard))} {shlex.quote(wsl_path(compressed_ramdisk))}")
    cpio_verify = BUILD / "vendor_ramdisk_c13_1.verify.cpio"
    run_wsl(f"lz4 -dc {shlex.quote(wsl_path(compressed_ramdisk))} > {shlex.quote(wsl_path(cpio_verify))}")
    if cpio_verify.read_bytes() != cpio_guard.read_bytes():
        raise SystemExit("Recompressed vendor ramdisk did not round-trip to the guarded CPIO")

    vendor_boot_raw = BUILD / "vendor_boot_c13_1.raw.img"
    dtb = VBOOT_UNPACK / "dtb"
    run([sys.executable, str(MKBOOTIMG), "--header_version", "3", "--pagesize", "4096",
         "--base", "0x00000000", "--kernel_offset", "0x00008000", "--ramdisk_offset", "0x01000000",
         "--tags_offset", "0x00000100", "--dtb_offset", "0x0000000001f00000",
         "--vendor_cmdline", ANDROID17_VENDOR_CMDLINE, "--board", "", "--dtb", str(dtb),
         "--vendor_ramdisk", str(compressed_ramdisk), "--vendor_boot", str(vendor_boot_raw)])
    vendor_boot_final = OUT_IMAGES / "vendor_boot.img"
    shutil.copy2(vendor_boot_raw, vendor_boot_final)
    run([sys.executable, str(AVBTOOL), "add_hash_footer", "--image", str(vendor_boot_final),
         "--partition_size", str(VENDOR_BOOT_PARTITION_SIZE), "--partition_name", "vendor_boot",
         "--hash_algorithm", "sha256", "--salt", VENDOR_BOOT_SALT, "--algorithm", "NONE"])

    # Rebuild the same LP layout from C13's audited logical images plus the
    # modified vendor logical image. C13's input extraction is pinned by size
    # and SHA-256 before lpmake is allowed to use it.
    for name, (expected_size, expected_hash) in LOGICAL_EXPECTED.items():
        source = C13_EXTRACT + "/" + name
        check = run_wsl(f"stat -c '%s' {shlex.quote(source)}; sha256sum {shlex.quote(source)}")
        lines = [line.strip() for line in check.splitlines() if line.strip()]
        if len(lines) < 2 or int(lines[-2]) != expected_size or lines[-1].split()[0].upper() != expected_hash:
            raise SystemExit(f"C13 extracted logical image verification failed for {name}: {lines}")

    super_path = OUT_IMAGES / "super.img"
    wsl_super = wsl_path(super_path)
    lpmake = TOOLS + "/android-tools-static/linux/android-tools-static/lpmake"
    parts = [
        "--partition mi_ext_a:readonly:202375168:qti_dynamic_partitions_a --partition mi_ext_b:none:0:qti_dynamic_partitions_b",
        "--partition odm_a:readonly:36700160:qti_dynamic_partitions_a --partition odm_b:none:0:qti_dynamic_partitions_b",
        "--partition product_a:readonly:4387241984:qti_dynamic_partitions_a --partition product_b:none:0:qti_dynamic_partitions_b",
        "--partition system_a:readonly:1092616192:qti_dynamic_partitions_a --partition system_b:none:0:qti_dynamic_partitions_b",
        "--partition system_ext_a:readonly:942669824:qti_dynamic_partitions_a --partition system_ext_b:none:0:qti_dynamic_partitions_b",
        "--partition vendor_a:readonly:1510998016:qti_dynamic_partitions_a --partition vendor_b:none:0:qti_dynamic_partitions_b",
    ]
    images = [
        ("--image", f"mi_ext_a={C13_EXTRACT}/mi_ext_a.img"),
        ("--image", f"odm_a={C13_EXTRACT}/odm_a.img"),
        ("--image", f"product_a={C13_EXTRACT}/product_a.img"),
        ("--image", f"system_a={C13_EXTRACT}/system_a.img"),
        ("--image", f"system_ext_a={C13_EXTRACT}/system_ext_a.img"),
        ("--image", f"vendor_a={wsl_path(OUT_IMAGES / 'vendor_a.img')}") ,
    ]
    lpmake_cmd = (
        f"{shlex.quote(lpmake)} --metadata-size 65536 --metadata-slots 3 --device-size {LP_DEVICE_SIZE} "
        f"--block-size 4096 --alignment 1048576 --virtual-ab --sparse --super-name super "
        f"--group qti_dynamic_partitions_a:{LP_DEVICE_SIZE} --group qti_dynamic_partitions_b:{LP_DEVICE_SIZE} "
        + " ".join(parts) + " " + " ".join(
            f"{shlex.quote(option)} {shlex.quote(value)}" for option, value in images
        )
        + f" --output {shlex.quote(wsl_super)}"
    )
    run_wsl(lpmake_cmd)
    if not super_path.is_file() or super_path.stat().st_size <= 0:
        raise SystemExit("lpmake did not create C13.1 super.img")
    with super_path.open("rb") as stream:
        if stream.read(4) != b"\x3a\xff\x26\xed":
            raise SystemExit("lpmake output is not a valid Android sparse image")

    # Rebuild top-level vbmeta descriptors only for the two changed inputs.
    sys.path.insert(0, str(AVBTOOL.parent))
    from avbtool import Avb, AvbHashtreeDescriptor, AvbHashDescriptor, ImageHandler

    avb = Avb()
    _footer, header, descriptors, _size = avb._parse_image(ImageHandler(str(C13_IMAGES / "vbmeta.img")))
    _boot_footer, _boot_header, boot_descriptors, _boot_size = avb._parse_image(ImageHandler(str(vendor_boot_final)))
    _vendor_footer, _vendor_header, vendor_descriptors, _vendor_size = avb._parse_image(ImageHandler(str(OUT_IMAGES / "vendor_a.img")))
    new_boot_desc = next(d for d in boot_descriptors if isinstance(d, AvbHashDescriptor) and d.partition_name == "vendor_boot")
    new_vendor_desc = next(d for d in vendor_descriptors if isinstance(d, AvbHashtreeDescriptor) and d.partition_name == "vendor")
    replaced = {"vendor_boot": 0, "vendor": 0}
    updated = []
    for descriptor in descriptors:
        if isinstance(descriptor, AvbHashDescriptor) and descriptor.partition_name == "vendor_boot":
            updated.append(new_boot_desc)
            replaced["vendor_boot"] += 1
        elif isinstance(descriptor, AvbHashtreeDescriptor) and descriptor.partition_name == "vendor":
            updated.append(new_vendor_desc)
            replaced["vendor"] += 1
        else:
            updated.append(descriptor)
    if replaced != {"vendor_boot": 1, "vendor": 1}:
        raise SystemExit(f"Expected exactly one root vbmeta descriptor for each changed image, got {replaced}")
    blob = avb._generate_vbmeta_blob(
        algorithm_name="NONE", key_path=None, public_key_metadata_path=None, descriptors=updated,
        chain_partitions_use_ab=None, chain_partitions_do_not_use_ab=None,
        rollback_index=header.rollback_index, flags=header.flags,
        rollback_index_location=header.rollback_index_location,
        props=None, props_from_file=None, kernel_cmdlines=None, setup_rootfs_from_kernel=None,
        ht_desc_to_setup=None, include_descriptors_from_image=None, signing_helper=None,
        signing_helper_with_files=None, release_string=header.release_string,
        append_to_release_string=None, required_libavb_version_minor=header.required_libavb_version_minor,
    )
    vbmeta_path = OUT_IMAGES / "vbmeta.img"
    if len(blob) > C13_EXPECTED["vbmeta.img"][0]:
        raise SystemExit("Rebuilt top-level vbmeta exceeds its 128 KiB partition image")
    vbmeta_path.write_bytes(blob + b"\0" * (C13_EXPECTED["vbmeta.img"][0] - len(blob)))

    # Verify the rebuilt LP metadata through a temporary raw image.
    raw_super = BUILD / "super_c13_1.verify.raw.img"
    simg2img = TOOLS + "/android-tools-static/linux/android-tools-static/simg2img"
    lpdump = TOOLS + "/android-tools-static/linux/android-tools-static/lpdump"
    run_wsl(f"{shlex.quote(simg2img)} {shlex.quote(wsl_super)} {shlex.quote(wsl_path(raw_super))}")
    lpdump_out = run_wsl(f"{shlex.quote(lpdump)} {shlex.quote(wsl_path(raw_super))}")
    if not all(name in lpdump_out for name in ("mi_ext_a", "odm_a", "product_a", "system_a", "system_ext_a", "vendor_a")):
        raise SystemExit("C13.1 super lpdump does not contain the expected A-slot logical partitions")
    raw_super.unlink()

    # Verify exact fstab result in both normal-boot copies and confirm recovery
    # fstabs were not part of the patch.
    if original_first_stage == patched_first_stage or original_vendor_fstab == patched_vendor_fstab:
        raise SystemExit("The normal-boot fstabs did not change")
    for name in ("boot.img", "dtbo.img", "vbmeta_system.img", "system_ext_c13.img"):
        if sha256_file(OUT_IMAGES / name) != sha256_file(C13_IMAGES / name):
            raise SystemExit(f"C13.1 unexpectedly changed inherited {name}")
    if len(list(OUT_IMAGES.iterdir())) < 6:
        raise SystemExit("C13.1 six-image set is incomplete")

    manifest = OUT_ROOT / "C13_1_DATA_GUARD_BUILD.txt"
    rows = [
        "THYME-OS4 Candidate 13.1 data-guard host build",
        "Device operations: none; no ADB/Fastboot commands were issued.",
        "Fstab change: removed only `check` and `formattable` from normal-boot /metadata and /data entries in vendor_boot first-stage CPIO and vendor_a /etc/fstab.qcom.",
        "Kept: file systems, mount timing, mount options, encryption flags, SELinux policy, kernel, cmdline, Recovery fstab, and BCB behavior.",
        f"First-stage fstab CPIO SHA256 after patch: {cpio_hash.upper()}",
        f"Runtime fstab ext4 data blocks: {blocks}; block size: {block_size}; original and patched lengths: {len(original_vendor_fstab)} bytes.",
        "e2fsck -fn on the patched raw vendor ext4 completed with no reported filesystem errors.",
        "C13 remains preserved in its original directory; C13.1 is isolated under work/stage_c_thyme_os4_candidate_13_1_data_guard/.",
        "The variant is not a read-only system: normal writable mounts and vold/init runtime writes remain possible.",
        "",
        "Images:",
    ]
    for item in sorted(OUT_IMAGES.iterdir()):
        rows.append(f"{item.name}\t{item.stat().st_size}\t{sha256_file(item)}")
    manifest.write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(f"[DONE] C13.1 images and manifest: {OUT_IMAGES} / {manifest}", flush=True)
    for row in rows[-len(list(OUT_IMAGES.iterdir())):]:
        print(row, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
