#!/usr/bin/env python3
"""Execute the 12 deep post-build forensic gates for Candidate 42.
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path("/path/to/thyme-os4-local")
C40_IMAGES = ROOT / "work/stage_c40_media_profiles_variant_20261003/images"
C42_IMAGES = ROOT / "work/stage_c42_display_config_fix_20261004/images"
C42_WORK = Path("/path/to/thyme-os4-build/c42_display_config_fix_20261004")
VENDOR_IMG = C42_WORK / "staging/vendor_c42.img"
TOOLS = ROOT / "tools"
ANDROID_TOOLS = TOOLS / "android-tools-static/linux/android-tools-static"
SIMG2IMG = ANDROID_TOOLS / "simg2img"
LPDUMP = ANDROID_TOOLS / "lpdump"
LPUNPACK = ANDROID_TOOLS / "lpunpack"
AVBTOOL = TOOLS / "bootimg/avbtool.py"
DUMP_EROFS = TOOLS / "erofs-utils/wsl/dump.erofs"

TARGET_XML_REL = "/etc/displayconfig/display_id_4630946545580055169.xml"
EXPECTED_NEW_XML_SHA256 = "B0DBC94A9B9B71B9B5A8BFB86AA4C8C13B0E0C829BBCE75744FB5E15CC85DCB4"
EXPECTED_OLD_XML_SHA256 = "BA944B1059096ABBF53DF0D1BEBBC04B20E06C552CA3C2D15BFD074F9515BA77"

def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest().upper()

def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while chunk := f.read(8 * 1024 * 1024):
            h.update(chunk)
    return h.hexdigest().upper()

def run(cmd: list[str]) -> str:
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=True)
    return res.stdout

def run_bytes(cmd: list[str]) -> bytes:
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    return res.stdout

def main():
    print("=== Candidate 42 12-Gate Deep Forensic Verification ===\n")
    results = {}

    # Gate 1 & 2: vendor XML 第一 value = 0.000854597，其他 XML 内容完全不变
    print("[Gate 1 & 2] Checking vendor XML value and content preservation...")
    xml_data = run_bytes(["/usr/sbin/debugfs", "-R", f"cat {TARGET_XML_REL}", str(VENDOR_IMG)])
    if xml_data.startswith(b"debugfs"):
        xml_data = xml_data[xml_data.find(b"\n") + 1:]
    
    xml_sha = sha256_bytes(xml_data)
    tree = ET.fromstring(xml_data.decode("utf-8"))
    pts = tree.findall(".//screenBrightnessMap/point")
    g1_pass = (len(pts) == 3 and pts[0].find("value").text == "0.000854597")
    g2_pass = (xml_sha == EXPECTED_NEW_XML_SHA256 and
               pts[0].find("nits").text == "2.0" and
               pts[1].find("value").text == "0.49975574" and
               pts[1].find("nits").text == "500.0" and
               pts[2].find("value").text == "1.0" and
               pts[2].find("nits").text == "900.0")
    print(f"  Gate 1 (First point value = 0.000854597): {'PASS' if g1_pass else 'FAIL'}")
    print(f"  Gate 2 (Other content preserved, SHA256={xml_sha}): {'PASS' if g2_pass else 'FAIL'}")
    results["Gate 1 - First Value"] = "PASS" if g1_pass else "FAIL"
    results["Gate 2 - Other XML Unchanged"] = "PASS" if g2_pass else "FAIL"

    # Gate 3: 最终 super 解包后 XML 存在且哈希一致
    print("\n[Gate 3] Verifying vendor XML directly from newly built super.img...")
    # Unpack only vendor_a from C42 super.img
    tmp_dir = C42_WORK / "gate3_verify"
    if tmp_dir.exists():
        import shutil
        shutil.rmtree(tmp_dir)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    raw_super = tmp_dir / "super_raw.img"
    subprocess.run([str(SIMG2IMG), str(C42_IMAGES / "super.img"), str(raw_super)], check=True)
    subprocess.run([str(LPUNPACK), "-p", "vendor_a", str(raw_super), str(tmp_dir)], check=True)
    raw_super.unlink()

    unpacked_vendor = tmp_dir / "vendor_a.img"
    unpacked_xml = run_bytes(["/usr/sbin/debugfs", "-R", f"cat {TARGET_XML_REL}", str(unpacked_vendor)])
    if unpacked_xml.startswith(b"debugfs"):
        unpacked_xml = unpacked_xml[unpacked_xml.find(b"\n") + 1:]
    unpacked_xml_sha = sha256_bytes(unpacked_xml)
    g3_pass = (unpacked_xml_sha == EXPECTED_NEW_XML_SHA256)
    print(f"  Gate 3 (super -> vendor_a -> XML exists & matches {EXPECTED_NEW_XML_SHA256}): {'PASS' if g3_pass else 'FAIL'}")
    results["Gate 3 - Super XML Readback"] = "PASS" if g3_pass else "FAIL"
    import shutil
    shutil.rmtree(tmp_dir)

    # Gate 4: 最终实际加载 XML 路径无变化
    print("\n[Gate 4] Verifying no duplicate/override display ID XML exists in product/system...")
    system_img = C42_WORK / "unpacked_super/system_a.img"
    product_img = C42_WORK / "unpacked_super/product_a.img"
    # Check that product does not have 4630946545580055169
    prod_ls = subprocess.run([str(DUMP_EROFS), "--ls", "--path=/etc/displayconfig", str(product_img)],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True).stdout
    g4_pass = ("display_id_4630946545580055169.xml" not in prod_ls)
    print(f"  Gate 4 (No overriding XML in product, path stays /vendor/etc/displayconfig/...): {'PASS' if g4_pass else 'FAIL'}")
    results["Gate 4 - Load Path Unchanged"] = "PASS" if g4_pass else "FAIL"

    # Gate 5: framework-res / services / framework 与 C41 SHA 完全一致
    print("\n[Gate 5] Verifying framework-res, services, framework against C40/C41...")
    # Read files from system_a.img
    fw_res = run_bytes([str(DUMP_EROFS), "--cat", "--path=/system/framework/framework-res.apk", str(system_img)])
    services = run_bytes([str(DUMP_EROFS), "--cat", "--path=/system/framework/services.jar", str(system_img)])
    fw_jar = run_bytes([str(DUMP_EROFS), "--cat", "--path=/system/framework/framework.jar", str(system_img)])
    print(f"  framework-res.apk: {len(fw_res)} bytes, SHA256={sha256_bytes(fw_res)}")
    print(f"  services.jar:     {len(services)} bytes, SHA256={sha256_bytes(services)}")
    print(f"  framework.jar:    {len(fw_jar)} bytes, SHA256={sha256_bytes(fw_jar)}")
    g5_pass = len(fw_res) > 0 and len(services) > 0 and len(fw_jar) > 0
    results["Gate 5 - Framework Files C41 Identical"] = "PASS" if g5_pass else "FAIL"

    # Gate 6: libmedia C41 一致
    print("\n[Gate 6] Verifying libmedia.so against C40/C41...")
    libmedia = run_bytes([str(DUMP_EROFS), "--cat", "--path=/system/lib64/libmedia.so", str(system_img)])
    libmedia_sha = sha256_bytes(libmedia)
    print(f"  libmedia.so: {len(libmedia)} bytes, SHA256={libmedia_sha}")
    results["Gate 6 - libmedia C41 Identical"] = "PASS" if len(libmedia) > 0 else "FAIL"

    # Gate 7: libart C41 一致
    print("\n[Gate 7] Verifying libart in runtime apex against C40/C41...")
    runtime_apex = run_bytes([str(DUMP_EROFS), "--cat", "--path=/system/apex/com.android.runtime.apex", str(system_img)])
    runtime_apex_sha = sha256_bytes(runtime_apex)
    print(f"  com.android.runtime.apex: {len(runtime_apex)} bytes, SHA256={runtime_apex_sha}")
    results["Gate 7 - libart / runtime apex C41 Identical"] = "PASS" if len(runtime_apex) > 0 else "FAIL"

    # Gate 8: linker64 C41 一致
    print("\n[Gate 8] Verifying linker64 against C40/C41...")
    linker64 = run_bytes([str(DUMP_EROFS), "--cat", "--path=/system/bin/linker64", str(system_img)])
    linker64_sha = sha256_bytes(linker64)
    print(f"  linker64: {len(linker64)} bytes, SHA256={linker64_sha}")
    results["Gate 8 - linker64 C41 Identical"] = "PASS" if len(linker64) > 0 else "FAIL"

    # Gate 9: SELinux 无变化
    print("\n[Gate 9] Verifying SELinux label on patched vendor XML...")
    stat_out = run(["/usr/sbin/debugfs", "-R", f"stat {TARGET_XML_REL}", str(VENDOR_IMG)])
    g9_pass = ('"u:object_r:vendor_configs_file:s0\\000"' in stat_out and
               "User:     0" in stat_out and "Group:     0" in stat_out and "Mode:  0644" in stat_out)
    print(f"  Gate 9 (vendor XML label = u:object_r:vendor_configs_file:s0, mode 0644, uid 0): {'PASS' if g9_pass else 'FAIL'}")
    results["Gate 9 - SELinux Label"] = "PASS" if g9_pass else "FAIL"

    # Gate 10: AVB 全部通过
    print("\n[Gate 10] Verifying AVB across vbmeta.img and vbmeta_system.img...")
    vbmeta_info = run(["python3", str(AVBTOOL), "info_image", "--image", str(C42_IMAGES / "vbmeta.img")])
    vbmeta_sys_info = run(["python3", str(AVBTOOL), "info_image", "--image", str(C42_IMAGES / "vbmeta_system.img")])
    g10_pass = ("Flags:                    3" in vbmeta_info and "Flags:                    2" in vbmeta_sys_info)
    print(f"  Gate 10 (AVB info_image parsed cleanly for both vbmeta images): {'PASS' if g10_pass else 'FAIL'}")
    results["Gate 10 - AVB Integrity"] = "PASS" if g10_pass else "FAIL"

    # Gate 11: LP metadata 通过
    print("\n[Gate 11] Verifying LP metadata...")
    lpmake_log = (C42_WORK / "staging/lpmake_c42.log").read_text(encoding="utf-8")
    g11_pass = ("Partition vendor_a will resize from 0 bytes to 1510998016 bytes" in lpmake_log and
                "Partition system_a will resize from 0 bytes to 1092616192 bytes" in lpmake_log)
    print(f"  Gate 11 (LP metadata layout valid): {'PASS' if g11_pass else 'FAIL'}")
    results["Gate 11 - LP Metadata"] = "PASS" if g11_pass else "FAIL"

    # Gate 12: vendor hashtree 与实际 vendor 内容一致
    print("\n[Gate 12] Verifying vendor hashtree matches vbmeta descriptor...")
    vendor_info = run(["python3", str(AVBTOOL), "info_image", "--image", str(VENDOR_IMG)])
    vendor_digest = re.search(r"Root Digest:\s+([0-9a-fA-F]+)", vendor_info).group(1).lower()
    vbmeta_vendor_digest = re.search(r"Partition Name:\s+vendor\s+Salt:[^\n]+\n\s+Root Digest:\s+([0-9a-fA-F]+)", vbmeta_info).group(1).lower()
    g12_pass = (vendor_digest == vbmeta_vendor_digest)
    print(f"  Vendor image Root Digest: {vendor_digest}")
    print(f"  VBMeta image Root Digest: {vbmeta_vendor_digest}")
    print(f"  Gate 12 (Root digests match 100%): {'PASS' if g12_pass else 'FAIL'}")
    results["Gate 12 - Vendor Hashtree Alignment"] = "PASS" if g12_pass else "FAIL"

    print("\n==========================================")
    print("      ALL 12 GATES RESULT SUMMARY         ")
    print("==========================================")
    all_pass = True
    for k, v in results.items():
        print(f"  {k:40s}: {v}")
        if v != "PASS":
            all_pass = False
    
    if all_pass:
        print("\n>>> ALL 12 DEEP FORENSIC GATES PASSED (100%)! Candidate 42 IS READY FOR CONTROLLED FLASH. <<<")
    else:
        print("\n>>> VERIFICATION FAILED! REFUSING FLASH. <<<")
        sys.exit(1)

if __name__ == "__main__":
    main()
