#!/usr/bin/env python3
"""Compare the actual C21 vendor Vulkan/Adreno ABI with the cached K40 OS4 bundle."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


ROOT = Path("/mnt/e/RVK/10S_OS4")
STAGE = Path("/root/10s_os4_build/c22_k40_vulkan_migration_20260927")
ACTUAL = STAGE / "thyme_actual_vendor_libs"
K40 = STAGE / "k40_graphics_deps"
SYSTEM = Path("/root/10s_os4_build/c21_k40_vk_renderengine_20260927_run1/system_tree/system")


def readelf(*args: str) -> str:
    return subprocess.check_output(["readelf", *args], text=True, errors="replace")


def needed(path: Path) -> list[str]:
    output = readelf("-d", str(path))
    return re.findall(r"Shared library: \[(.*?)\]", output)


def symbols(path: Path, wanted: str) -> set[str]:
    output = readelf("--dyn-syms", "--wide", str(path))
    found: set[str] = set()
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 8 or not parts[0].rstrip(":").isdigit():
            continue
        is_undefined = parts[6] == "UND"
        if (wanted == "undefined") != is_undefined:
            continue
        name = parts[7].split("@", 1)[0]
        if name:
            found.add(name)
    return found


def report_pair(target_name: str, old: Path, new: Path) -> None:
    old_exports = symbols(old, "defined")
    new_exports = symbols(new, "defined")
    print(f"PAIR {target_name}: old_exports={len(old_exports)} new_exports={len(new_exports)}")
    missing = sorted(old_exports - new_exports)
    print(f"  old exports absent from K40: {len(missing)}")
    if missing:
        print("  samples:", ", ".join(missing[:20]))


def main() -> None:
    k40_vk = K40 / "vulkan.adreno.so"
    k40_gsl = K40 / "libgsl.so"
    k40_glnext = K40 / "libllvm-glnext.so"
    k40_utils = K40 / "libadreno_utils.so"
    k40_qgl = K40 / "libllvm-qgl.so"
    k40_qcom = K40 / "libllvm-qcom.so"
    current_vk = ACTUAL / "vulkan.adreno.so"
    current_gsl = ACTUAL / "libgsl.so"
    current_glnext = ACTUAL / "libllvm-glnext.so"
    current_utils = ACTUAL / "libadreno_utils.so"

    for path in (k40_vk, k40_gsl, k40_glnext, k40_utils, k40_qgl, k40_qcom,
                 current_vk, current_gsl, current_glnext, current_utils):
        if not path.is_file():
            raise FileNotFoundError(path)

    print("C21 actual Vulkan NEEDED:", ", ".join(needed(current_vk)))
    print("K40 Vulkan NEEDED:", ", ".join(needed(k40_vk)))
    print("C21 GSL NEEDED:", ", ".join(needed(current_gsl)))
    print("K40 GSL NEEDED:", ", ".join(needed(k40_gsl)))
    print("K40 LLVM-GN NEEDED:", ", ".join(needed(k40_glnext)))
    print("K40 LLVM-QGL NEEDED:", ", ".join(needed(k40_qgl)))
    print("K40 LLVM-QCOM NEEDED:", ", ".join(needed(k40_qcom)))

    for name, old, new in (
        ("libgsl.so", current_gsl, k40_gsl),
        ("libllvm-glnext.so", current_glnext, k40_glnext),
        ("libadreno_utils.so", current_utils, k40_utils),
    ):
        report_pair(name, old, new)

    driver_undefined = symbols(k40_vk, "undefined")
    gsl_exports = symbols(k40_gsl, "defined")
    print("K40 Vulkan undefined symbols supplied by K40 GSL:",
          len(driver_undefined & gsl_exports))
    print("K40 Vulkan undefined GSL-like names missing from C21 GSL:",
          ", ".join(sorted((driver_undefined & gsl_exports) - symbols(current_gsl, "defined"))[:30]))

    system_candidates = [SYSTEM / "lib64", SYSTEM / "lib64/vndk-35", SYSTEM / "lib64/vndk-36"]
    for library in ("libdmabufheap.so", "libbase.so", "libsync.so"):
        matches = [str(directory / library) for directory in system_candidates
                   if (directory / library).is_file()]
        print(f"SYSTEM {library}:", ", ".join(matches) if matches else "MISSING")


if __name__ == "__main__":
    main()
