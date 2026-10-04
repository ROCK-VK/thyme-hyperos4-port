#!/usr/bin/env python3
"""Build C32-DIAG: one fixed native abort in the existing zygote domain."""

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
C31_WORK = WSL_BUILD / "c31_diag_zygote_critical_20261001_run1"
C31_TREE = C31_WORK / "system_tree"
C32_STAGE = ROOT / "work/stage_c32_diag_zygote_domain_canary_20261001_run3"
C32_IMAGES = C32_STAGE / "images"
C32_WORK = WSL_BUILD / "c32_diag_zygote_domain_canary_20261001_run3"
C32_TREE = C32_WORK / "system_tree"
REPORT_DIR = ROOT / "reports/c32_diag_zygote_domain_canary_20261001"
SOURCE = ROOT / "tools/candidate32_zygote_canary/c32_zygote_canary.c"
INIT_APPEND = ROOT / "tools/candidate32_zygote_canary/init.rc.append"

SYSTEM_INIT = "system/etc/init/hw/init.rc"
FILE_CONTEXTS = "system/etc/selinux/plat_file_contexts"
PLAT_CIL = "system/etc/selinux/plat_sepolicy.cil"
PROPERTY_CONTEXTS = "system/etc/selinux/plat_property_contexts"
PRIMARY_ZYGOTE_RC = "system/etc/init/hw/init.zygote64.rc"
SECONDARY_ZYGOTE_RC = "system/etc/init/hw/init.zygote64_32.rc"
NETD_RC = "system/etc/init/netd.rc"
TOMBSTONED_RC = "system/etc/init/tombstoned.rc"
CANARY_REL = "system/bin/c32_zygote_canary"
CANARY_RUNTIME_PATH = "/system/bin/c32_zygote_canary"
CANARY_FILE_CONTEXT = "/system/bin/c32_zygote_canary\tu:object_r:zygote_exec:s0"
CANARY_MKFS_CONTEXT = "/system/system/bin/c32_zygote_canary u:object_r:zygote_exec:s0"
IMPORT_C25 = "import /system/etc/init/c25_bootdiag.rc"
IMPORT_C30 = "import /system/etc/init/c30_diag.rc"
IMAGE_NAMES = ("super.img", "vbmeta_system.img")
INHERITED_SMALL = ("boot.img", "vendor_boot.img", "dtbo.img", "vbmeta.img")
CANDIDATE = "Candidate 32-DIAG zygote-domain crash-dump isolation canary"
BASE_CANDIDATE = "Candidate 31-DIAG primary Zygote critical escalation causal capture"
C32_PREFIX = "THYME_C32_CANARY"

NDK_VERSION = "28.2.13676358"
_ndk_override = os.environ.get("THYME_NDK_TOOLCHAIN_ROOT") or os.environ.get("ANDROID_NDK_TOOLCHAIN_ROOT")
if _ndk_override:
    NDK_ROOT = Path(_ndk_override)
else:
    _ndk_candidates = sorted(Path("/mnt/c/Users").glob(
        f"*/AppData/Local/Android/Sdk/ndk/{NDK_VERSION}/toolchains/llvm/prebuilt/windows-x86_64"))
    if len(_ndk_candidates) != 1:
        raise RuntimeError(
            "Set THYME_NDK_TOOLCHAIN_ROOT to the Android NDK 28.2.13676358 "
            "windows-x86_64 LLVM toolchain directory when it is not uniquely discoverable."
        )
    NDK_ROOT = _ndk_candidates[0]
NDK_SYSROOT = NDK_ROOT / "sysroot"
NDK_CLANG = NDK_ROOT / "bin/clang.exe"
ANDROID_API = "30"


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


def wsl_path_to_windows(path: Path) -> str:
    value = path.resolve().as_posix()
    match = re.match(r"^/mnt/([a-z])/(.*)$", value, re.IGNORECASE)
    if not match:
        raise RuntimeError(f"Expected a Windows-mounted WSL path, got: {value}")
    tail = match.group(2).replace("/", "\\")
    return match.group(1).upper() + ":\\" + tail


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


def inventory(root: Path) -> dict[str, Path]:
    return {item.relative_to(root).as_posix(): item for item in root.rglob("*")
            if item.is_file() or item.is_symlink()}


def tree_delta(before_root: Path, after_root: Path) -> dict[str, list[str]]:
    before, after = inventory(before_root), inventory(after_root)
    removed = set(before) - set(after)
    added = set(after) - set(before)
    modified: set[str] = set()
    for rel in set(before) & set(after):
        old, new = before[rel], after[rel]
        if old.is_symlink() or new.is_symlink():
            if not (old.is_symlink() and new.is_symlink() and os.readlink(old) == os.readlink(new)):
                modified.add(rel)
        elif old.stat().st_dev == new.stat().st_dev and old.stat().st_ino == new.stat().st_ino:
            continue
        elif old.stat().st_size != new.stat().st_size or sha256(old) != sha256(new):
            modified.add(rel)
    return {"removed": sorted(removed), "added": sorted(added), "modified": sorted(modified)}


def atomic_replace(path: Path, content: bytes) -> None:
    mode = stat.S_IMODE(path.stat().st_mode)
    temp = path.with_name(path.name + ".c32tmp")
    if temp.exists() or temp.is_symlink():
        raise FileExistsError(temp)
    temp.write_bytes(content)
    os.chmod(temp, mode)
    os.replace(temp, path)


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


def load_c31_manifest() -> dict[str, object]:
    path = C31_IMAGES / "BUILD_MANIFEST.json"
    require_file(path)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("candidate") != BASE_CANDIDATE or \
            manifest.get("base") != "Candidate 30 dedicated-domain write canary and ordered startup diagnostics":
        raise RuntimeError("C31 manifest does not match the intended C32 source baseline.")
    if manifest.get("flash_scope_prepared") != ["super", "vbmeta_system_a"]:
        raise RuntimeError("C31 baseline flash scope differs from the approved Candidate scope.")
    if manifest.get("source_delta", {}).get("unexpected_changes") != []:
        raise RuntimeError("C31 baseline manifest contains an unexpected source change.")
    if set(manifest.get("images", {})) != {"boot.img", "vendor_boot.img", "dtbo.img",
                                               "vbmeta.img", "vbmeta_system.img", "super.img"}:
        raise RuntimeError("C31 baseline image manifest is incomplete.")
    required_readbacks = manifest.get("system_build", {}).get("final_erofs_readback", {})
    for erofs_path in (
        "/system/etc/init/hw/init.rc", "/system/etc/init/hw/init.zygote64.rc",
        "/system/etc/init/hw/init.zygote64_32.rc", "/system/etc/init/netd.rc",
        "/system/etc/init/c30_diag.rc",
        "/system/etc/selinux/plat_sepolicy.cil",
        "/system/etc/selinux/plat_property_contexts",
    ):
        if erofs_path not in required_readbacks:
            raise RuntimeError(f"C31 final readback manifest lacks {erofs_path}.")
        tree_path = C31_TREE / "system" / erofs_path.removeprefix("/system/")
        require_file(tree_path)
        if sha256(tree_path) != str(required_readbacks[erofs_path]["sha256"]).upper():
            raise RuntimeError(f"C31 current tree differs from its final EROFS readback: {erofs_path}")
    for rel in ("system/bin/c30_diag", FILE_CONTEXTS):
        require_file(C31_TREE / rel)
    for name in INHERITED_SMALL:
        item = manifest["images"][name]
        require_file(C31_IMAGES / name, int(item["bytes"]))
        if sha256(C31_IMAGES / name) != str(item["sha256"]).upper():
            raise RuntimeError(f"C31 small inherited image changed since its manifest: {name}")
    return manifest


def validate_c31_transition(c31_manifest: dict[str, object]) -> dict[str, object]:
    init = (C31_TREE / SYSTEM_INIT).read_text(encoding="utf-8")
    primary = (C31_TREE / PRIMARY_ZYGOTE_RC).read_text(encoding="utf-8")
    tombstoned = (C31_TREE / TOMBSTONED_RC).read_text(encoding="utf-8")
    contexts = (C31_TREE / FILE_CONTEXTS).read_text(encoding="utf-8")
    cil = (C31_TREE / PLAT_CIL).read_text(encoding="utf-8")
    property_contexts = (C31_TREE / PROPERTY_CONTEXTS).read_text(encoding="utf-8")
    tokens = (
        "/system/bin/app_process64\tu:object_r:zygote_exec:s0",
        "(allow init zygote_exec (file (read getattr map execute open)))",
        "(allow zygote zygote_exec (file (read getattr map execute open entrypoint)))",
        "(typetransition init zygote_exec process zygote)",
    )
    c31_platform_line = "on property:init.svc.tombstoned=running"
    if tokens[0] not in contexts:
        raise RuntimeError("C31 does not label app_process64 with zygote_exec.")
    for token in tokens[1:]:
        if token not in cil:
            raise RuntimeError(f"C31 platform CIL lacks existing transition permission: {token}")
    if "service zygote /system/bin/app_process64" not in primary or "seclabel " in primary:
        raise RuntimeError("C31 zygote service differs from file-type based domain transition assumptions.")
    if "start tombstoned" not in init or "service tombstoned /system/bin/tombstoned" not in tombstoned:
        raise RuntimeError("C31 tombstoned service/start definition is missing.")
    if c31_platform_line in init:
        raise RuntimeError("C31 unexpectedly already contains a C32 tombstoned trigger.")
    if not re.search(r"(?m)^init\.svc\.tombstoned\s+u:object_r:init_service_status_prop:s0 exact string\s*$",
                     property_contexts):
        raise RuntimeError("C31 does not use the expected exact tombstoned status property context.")
    if not re.search(r"(?m)^init\.svc_debug_pid\.\s+u:object_r:init_svc_debug_prop:s0\s*$",
                     property_contexts):
        raise RuntimeError("C31 lacks the init service PID property prefix.")
    return {
        "zygote_exec_context_exists": True,
        "init_exec_transition_exists": True,
        "new_selinux_allow_rules": False,
        "service_seclabel_override": False,
        "tombstoned_start_rc": TOMBSTONED_RC,
        "tombstoned_start_in_main_init": True,
        "tombstoned_status_context": "init_service_status_prop",
        "init_svc_debug_pid_context": "init_svc_debug_prop prefix",
        "runtime_domain_confirmation": "successful tombstone SELinux label; no zygote /proc/self/attr/current read permission was found in the compiled C31 platform policy",
        "C31_baseline_candidate": c31_manifest["candidate"],
    }


def validate_init_append(base_init: str) -> dict[str, object]:
    patch = INIT_APPEND.read_bytes()
    if b"\r" in patch or not patch.endswith(b"\n"):
        raise RuntimeError("C32 init fragment must be LF-terminated UTF-8.")
    text = patch.decode("utf-8")
    if C32_PREFIX in base_init:
        raise RuntimeError("C31 init.rc already contains C32 markers; refusing to append twice.")
    if base_init.count(IMPORT_C25) != 1 or base_init.count(IMPORT_C30) != 1:
        raise RuntimeError("C31 init imports are not in their expected inherited state.")
    required = (
        "service c32_zygote_canary /system/bin/c32_zygote_canary",
        "    disabled", "    oneshot", "    user root",
        "on boot && property:init.svc.tombstoned=running",
        "start c32_zygote_canary",
        "on property:init.svc_debug_pid.c32_zygote_canary=*",
        "on property:init.svc.c32_zygote_canary=running",
        "on property:init.svc.c32_zygote_canary=stopped && property:init.svc_debug_pid.c32_zygote_canary=*",
        "THYME_C32_CANARY event=boot",
        "THYME_C32_CANARY event=trigger",
        "THYME_C32_CANARY event=running",
        "THYME_C32_CANARY event=stopped",
    )
    missing = [token for token in required if token not in text]
    if missing:
        raise RuntimeError(f"C32 init fragment lacks required one-shot behavior: {missing}")
    if text.count("start c32_zygote_canary") != 1 or text.count(
            "on boot && property:init.svc.tombstoned=running") != 1:
        raise RuntimeError("C32 must have exactly one tombstoned-ready start action.")
    service = text.split("service c32_zygote_canary", 1)[1].split("\non ", 1)[0]
    if any(token in service for token in ("critical", "onrestart", "seclabel", "restart ")):
        raise RuntimeError("C32 canary service must not be critical, restartable, or pinned with seclabel.")
    if text.count("THYME_C32_CANARY") < 5:
        raise RuntimeError("C32 lifecycle markers are incomplete.")
    return {"patch_sha256": hashlib.sha256(patch).hexdigest().upper(),
            "patch_bytes": len(patch), "required_tokens": list(required),
            "one_shot_start_action_count": 1,
            "service_flags": ["disabled", "oneshot", "non-critical", "no onrestart", "no seclabel"]}


def compile_canary(stage: Path) -> tuple[Path, dict[str, object]]:
    require_file(SOURCE)
    require_file(NDK_CLANG)
    readelf = shutil.which("readelf")
    if not readelf:
        raise FileNotFoundError("WSL readelf is required for the C32 native canary.")
    for path in (
        NDK_SYSROOT / "usr/include/android/log.h",
        NDK_SYSROOT / "usr/include/android/set_abort_message.h",
        NDK_SYSROOT / f"usr/lib/aarch64-linux-android/{ANDROID_API}/libc.so",
        NDK_SYSROOT / f"usr/lib/aarch64-linux-android/{ANDROID_API}/liblog.so",
    ):
        require_file(path)
    binary = stage / "c32_zygote_canary"
    with tempfile.TemporaryDirectory(prefix="thyme-c32-canary-", dir=ROOT / "work") as temp_name:
        windows_output = Path(temp_name) / "c32_zygote_canary"
        command = [
            NDK_CLANG, "--target=aarch64-linux-android" + ANDROID_API,
            f"--sysroot={wsl_path_to_windows(NDK_SYSROOT)}", "-fuse-ld=lld", "-fPIE", "-pie", "-O2",
            "-Wall", "-Wextra", "-Werror", "-fstack-protector-strong",
            "-D_FORTIFY_SOURCE=2", "-Wl,--dynamic-linker=/system/bin/linker64",
            "-Wl,--build-id=sha1", "-Wl,-z,relro,-z,now", "-Wl,-z,noexecstack",
            "-Wl,--no-undefined", wsl_path_to_windows(SOURCE), "-llog", "-lc",
            "-o", wsl_path_to_windows(windows_output),
        ]
        run(command, stage / "compile_canary.log")
        require_file(windows_output)
        shutil.copy2(windows_output, binary)
    require_file(binary)
    header = run([readelf, "-h", binary], stage / "canary_elf_header.txt")
    program = run([readelf, "-l", binary], stage / "canary_elf_program_headers.txt")
    dynamic = run([readelf, "-d", binary], stage / "canary_elf_dynamic.txt")
    symbols = run([readelf, "--dyn-syms", "--wide", binary], stage / "canary_elf_dynamic_symbols.txt")
    if "AArch64" not in header or "DYN (Position-Independent Executable file)" not in header:
        raise RuntimeError("C32 canary must be an AArch64 PIE ELF.")
    if "/system/bin/linker64" not in program:
        raise RuntimeError("C32 canary has the wrong Android dynamic-linker interpreter.")
    if "liblog.so" not in dynamic or "libc.so" not in dynamic:
        raise RuntimeError("C32 canary dynamic dependencies must include the expected libc/liblog interface.")
    if "libc++_shared.so" in dynamic or "libstdc++" in dynamic:
        raise RuntimeError("C32 canary unexpectedly depends on a C++ runtime.")
    if "android_set_abort_message" not in symbols or "__android_log_write" not in symbols:
        raise RuntimeError("C32 canary is missing the expected Bionic/liblog imports.")
    needed = sorted(set(re.findall(r"Shared library: \[([^]]+)\]", dynamic)))
    if set(needed) - {"libc.so", "liblog.so", "libdl.so"}:
        raise RuntimeError(f"C32 canary has unexpected NEEDED libraries: {needed}")
    return binary, {
        "bytes": binary.stat().st_size, "sha256": sha256(binary),
        "architecture": "AArch64", "elf_type": "PIE / ET_DYN",
        "interpreter": "/system/bin/linker64", "needed": needed,
        "api_level_target": int(ANDROID_API),
        "cxx_runtime": "none",
        "source_sha256": sha256(SOURCE),
        "fixed_abort_message": "THYME_C32_CANARY_ABORT",
        "domain_read": "not attempted; C31 zygote has no explicit permission for the relevant proc attribute read; domain is verified from tombstone SELinux label",
        "compile_command": [os.fspath(x) for x in command],
    }


def apply_source_delta(c28, c31_manifest: dict[str, object], canary_binary: Path,
                       stage: Path) -> dict[str, object]:
    shutil.copytree(C31_TREE, C32_TREE, symlinks=True, copy_function=c28.hardlink_or_copy)
    base_init_path = C32_TREE / SYSTEM_INIT
    base_init = base_init_path.read_text(encoding="utf-8")
    init_info = validate_init_append(base_init)
    atomic_replace(base_init_path, (base_init.rstrip("\n") + "\n" +
                                    INIT_APPEND.read_text(encoding="utf-8")).encode("utf-8"))

    file_contexts_path = C32_TREE / FILE_CONTEXTS
    old_contexts = file_contexts_path.read_text(encoding="utf-8")
    if CANARY_FILE_CONTEXT in old_contexts:
        raise RuntimeError("C31 platform file_contexts already has the C32 entry.")
    if "/system/bin/app_process64\tu:object_r:zygote_exec:s0" not in old_contexts:
        raise RuntimeError("C31 platform file_contexts lacks the reference zygote_exec rule.")
    new_contexts = old_contexts.rstrip("\n") + "\n" + CANARY_FILE_CONTEXT + "\n"
    atomic_replace(file_contexts_path, new_contexts.encode("utf-8"))
    shutil.copy2(canary_binary, C32_TREE / CANARY_REL)
    os.chmod(C32_TREE / CANARY_REL, 0o755)

    delta = tree_delta(C31_TREE, C32_TREE)
    expected = {
        "removed": [],
        "added": [CANARY_REL],
        "modified": [SYSTEM_INIT, FILE_CONTEXTS],
    }
    if delta != expected:
        raise RuntimeError(f"C31->C32 system tree delta exceeds the three-file allowlist: {delta}")
    if sha256(C31_TREE / PLAT_CIL) != sha256(C32_TREE / PLAT_CIL) or \
            sha256(C31_TREE / PROPERTY_CONTEXTS) != sha256(C32_TREE / PROPERTY_CONTEXTS):
        raise RuntimeError("C32 modified policy CIL or property contexts unexpectedly.")
    if sha256(C32_TREE / PRIMARY_ZYGOTE_RC) != sha256(C31_TREE / PRIMARY_ZYGOTE_RC) or \
            sha256(C32_TREE / SECONDARY_ZYGOTE_RC) != sha256(C31_TREE / SECONDARY_ZYGOTE_RC) or \
            sha256(C32_TREE / NETD_RC) != sha256(C31_TREE / NETD_RC):
        raise RuntimeError("C32 changed Zygote/netd service definitions unexpectedly.")
    for name in INHERITED_SMALL:
        item = c31_manifest["images"][name]
        if sha256(C31_IMAGES / name) != str(item["sha256"]).upper():
            raise RuntimeError(f"C31 inherited boot image mismatch: {name}")
    return {"tree_delta": delta, "init_patch": init_info,
            "new_platform_file_context": CANARY_FILE_CONTEXT,
            "new_mkfs_file_context": CANARY_MKFS_CONTEXT,
            "policy_cil_sha256_unchanged": sha256(C32_TREE / PLAT_CIL),
            "property_contexts_sha256_unchanged": sha256(C32_TREE / PROPERTY_CONTEXTS),
            "protected_netd_zygote_rcs_unchanged": True,
            "inherited_boot_images_checked": list(INHERITED_SMALL),
            "source_file_sha256": sha256(SOURCE),
            "compiled_canary_sha256": sha256(C32_TREE / CANARY_REL)}


def build_system(c23, c31_manifest: dict[str, object], stage: Path,
                 canary_info: dict[str, object]) -> dict[str, object]:
    base_contexts = c23.C1 / "configs_retained/system/file_contexts"
    fs_config_source = c23.C1 / "configs_retained/system/fs_config"
    require_file(base_contexts)
    require_file(fs_config_source)
    additions = (
        "/system/system/bin/c25_bootdiag u:object_r:shell_exec:s0",
        "/system/system/etc/init/c25_bootdiag\\.rc u:object_r:system_file:s0",
        "/system/system/bin/c30_diag u:object_r:c30_diag_exec:s0",
        "/system/system/etc/init/c30_diag\\.rc u:object_r:system_file:s0",
        CANARY_MKFS_CONTEXT,
    )
    contexts = base_contexts.read_text(encoding="utf-8").rstrip("\n") + "\n" + "\n".join(additions) + "\n"
    contexts_path = stage / "system_file_contexts_c32"
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
    for item in sorted(C32_TREE.rglob("*"), key=lambda p: p.relative_to(C32_TREE).as_posix()):
        rel = "system/" + item.relative_to(C32_TREE).as_posix()
        if rel in known:
            continue
        st = item.lstat()
        added.append(f"{rel} {st.st_uid} {st.st_gid} {stat.S_IMODE(st.st_mode):04o}")
        known.add(rel)
    fs_config = stage / "system_fs_config_c32"
    fs_config.write_text("\n".join(rebased + added) + "\n", encoding="utf-8", newline="\n")
    expected_fs_entry = "system/system/bin/c32_zygote_canary 0 0 0755"
    if expected_fs_entry not in fs_config.read_text(encoding="utf-8"):
        raise RuntimeError("C32 canary fs_config entry is missing or has unexpected ownership/mode.")

    raw = stage / "system_c32_diag.raw.erofs"
    image = stage / "system_c32_diag.img"
    c23.run([c23.MKFS, "-zlz4hc", "-T", "0", "-U", c23.SYSTEM_UUID,
             "--mount-point=/system", f"--fs-config-file={fs_config}",
             f"--file-contexts={contexts_path}", raw, C32_TREE],
            log=stage / "mkfs_system_c32_diag.log")
    c23.run([c23.FSCK, "-d0", raw], log=stage / "fsck_system_c32_diag.log")
    shutil.copy2(raw, image)
    c23.run(["python3", c23.AVBTOOL, "add_hashtree_footer", "--image", image,
             "--partition_size", str(c23.SYSTEM_SIZE), "--partition_name", "system",
             "--hash_algorithm", "sha256", "--salt", c23.SYSTEM_SALT,
             "--algorithm", "NONE", "--do_not_generate_fec"],
             log=stage / "avb_system_c32_diag.log")
    require_file(image, c23.SYSTEM_SIZE)

    expected_readbacks = {
        "/system/etc/init/hw/init.rc": (
            IMPORT_C25, IMPORT_C30, "setprop init.svc_debug.no_fatal.zygote true",
            "THYME_C31DIAG event=critical_gate", "THYME_C32_CANARY event=trigger",
            "service c32_zygote_canary /system/bin/c32_zygote_canary",
            "on boot && property:init.svc.tombstoned=running", "    disabled", "    oneshot"),
        "/system/etc/selinux/plat_file_contexts": (
            "/system/bin/app_process64\tu:object_r:zygote_exec:s0", CANARY_FILE_CONTEXT),
        "/system/etc/selinux/plat_sepolicy.cil": (
            "(typetransition init zygote_exec process zygote)",),
        "/system/etc/selinux/plat_property_contexts": (
            "init.svc.tombstoned", "init.svc_debug_pid."),
        "/system/etc/init/tombstoned.rc": ("service tombstoned /system/bin/tombstoned",),
        "/system/etc/init/c30_diag.rc": ("service c30_diag /system/bin/c30_diag",),
        "/system/bin/c30_diag": (),
        "/system/etc/init/hw/init.zygote64.rc": (
            "service zygote /system/bin/app_process64", "critical window="),
        "/system/etc/init/netd.rc": ("service netd /system/bin/netd",),
        CANARY_RUNTIME_PATH: (),
    }
    readbacks: dict[str, object] = {}
    for path, tokens in expected_readbacks.items():
        data = run_bytes([c23.DUMP, "--cat", f"--path={path}", raw])
        if path in {CANARY_RUNTIME_PATH, "/system/bin/c30_diag"}:
            tree_rel = CANARY_REL if path == CANARY_RUNTIME_PATH else "system/bin/c30_diag"
            if data != (C32_TREE / tree_rel).read_bytes():
                raise RuntimeError(f"C32 final EROFS executable does not match the source tree: {path}")
            if path == CANARY_RUNTIME_PATH and hashlib.sha256(data).hexdigest().upper() != canary_info["sha256"]:
                raise RuntimeError("C32 final EROFS canary does not match the compiled AArch64 ELF.")
        else:
            content = data.decode("utf-8", errors="replace")
            missing = [token for token in tokens if token not in content]
            if missing:
                raise RuntimeError(f"Final C32 EROFS readback missing {path} tokens: {missing}")
        readbacks[path] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest().upper(),
                           "required_tokens": list(tokens)}

    verify_link = image.parent / "system.img"
    if verify_link.exists() or verify_link.is_symlink():
        raise FileExistsError(verify_link)
    verify_link.symlink_to(image)
    try:
        c23.run(["python3", c23.AVBTOOL, "verify_image", "--image", image],
                log=stage / "avb_verify_system_c32_diag.log")
    finally:
        verify_link.unlink(missing_ok=True)
    return {
        "system_image_bytes": image.stat().st_size,
        "system_image_sha256": sha256(image),
        "final_erofs_readback": readbacks,
        "new_files": [CANARY_REL],
        "changed_files": [FILE_CONTEXTS, SYSTEM_INIT],
        "mkfs_file_context_additions": list(additions),
        "new_fs_config_paths": ["system/" + CANARY_REL],
        "new_selinux_policy_rules": False,
        "canary_binary": canary_info,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight-only", action="store_true",
                        help="Compile and statically validate C32 without cloning or building partition images.")
    args = parser.parse_args()
    if "microsoft" not in Path("/proc/sys/kernel/osrelease").read_text().lower():
        raise RuntimeError("Run this builder inside Ubuntu WSL.")

    c31 = load_module("candidate31_builder_for_c32", ROOT / "tools/build_candidate31_diag_critical_escalation.py")
    c23 = load_module("candidate23_builder_for_c32", ROOT / "tools/build_candidate23_sf_prime_skip.py")
    c24 = load_module("candidate24_builder_for_c32", ROOT / "tools/build_candidate24_framework_display_diag.py")
    c28 = load_module("candidate28_builder_for_c32", ROOT / "tools/build_candidate28_recovery_diag.py")
    for tool in (c23.MKFS, c23.FSCK, c23.DUMP, c23.LPMAKE, c23.SIMG2IMG, c23.LPDUMP, c23.AVBTOOL):
        require_file(tool)
    for tool in (c23.MKFS, c23.FSCK, c23.DUMP, c23.LPMAKE, c23.SIMG2IMG, c23.LPDUMP):
        if not os.access(tool, os.X_OK):
            raise PermissionError(f"Build tool is not executable: {tool}")
    c31_manifest = load_c31_manifest()
    transition_info = validate_c31_transition(c31_manifest)
    base_init = (C31_TREE / SYSTEM_INIT).read_text(encoding="utf-8")
    init_info = validate_init_append(base_init)
    if not args.preflight_only and (C32_STAGE.exists() or C32_WORK.exists()):
        raise FileExistsError("C32 run3 output already exists; refusing to overwrite.")

    if args.preflight_only:
        with tempfile.TemporaryDirectory(prefix="thyme-c32-canary-preflight-") as temp_name:
            temp = Path(temp_name)
            binary, canary_info = compile_canary(temp)
            if not canary_info["sha256"] or binary.stat().st_size <= 0:
                raise RuntimeError("C32 preflight ELF output is empty.")
            print(json.dumps({"preflight": "passed", "transition": transition_info,
                              "init": init_info, "canary": canary_info},
                             ensure_ascii=False, indent=2), flush=True)
        return

    storage = check_space()
    C32_STAGE.mkdir(parents=True, exist_ok=False)
    C32_IMAGES.mkdir(parents=True, exist_ok=False)
    C32_WORK.mkdir(parents=True, exist_ok=False)
    stage = C32_WORK / "staging"
    stage.mkdir(parents=True, exist_ok=False)

    canary, canary_info = compile_canary(stage)
    source_delta = apply_source_delta(c28, c31_manifest, canary, stage)
    system_info = build_system(c23, c31_manifest, stage, canary_info)
    c24.C23_IMAGES = C31_IMAGES
    vbmeta_info = c24.rebuild_vbmeta_system_c24(c23, stage / "system_c32_diag.img",
                                                C32_IMAGES / "vbmeta_system.img", stage)
    c23.C23_IMAGES = C32_IMAGES
    super_image, logical_hashes = c23.build_super(stage / "system_c32_diag.img", stage)
    if logical_hashes != c31_manifest.get("logical_input_hashes", {}):
        raise RuntimeError("C32 changed one or more non-system logical partition inputs from C31.")
    entries: dict[str, dict[str, object]] = {}
    for name in IMAGE_NAMES:
        image = C32_IMAGES / name
        require_file(image)
        entries[name] = {"bytes": image.stat().st_size, "sha256": sha256(image)}

    manifest = {
        "candidate": CANDIDATE,
        "base": BASE_CANDIDATE,
        "classification": "diagnostic-only; not a system boot fix",
        "purpose": "Test the debuggerd -> crash_dump -> tombstoned path for a single native SIGABRT process entering the existing zygote SELinux domain.",
        "diagnostic_limits": [
            "Canary success proves only that a minimal native process in zygote domain can produce a tombstone; it does not reproduce ART, seccomp, namespace, Zygote pre-fork state, inherited FDs, credentials/capabilities, signal handler setup, linker namespaces, or Zygote startup ordering.",
            "Canary failure does not by itself identify zygote SELinux policy as root cause; it must be separated into domain transition, executable/linker, debuggerd/crash_dump, tombstoned, and runtime failure.",
            "The process does not read /proc/self/attr/current because the C31 policy has no explicit zygote read rule for that path; runtime SELinux label is to be read from the tombstone if one is produced.",
        ],
        "changes": [
            "Adds one AArch64 PIE binary with process comm main; logs start/PID/expected-domain markers, sets the fixed abort message THYME_C32_CANARY_ABORT, and calls abort exactly once.",
            "Adds one disabled, oneshot, non-critical init service with no onrestart or seclabel override; starts only from the one-time boot event when init.svc.tombstoned=running.",
            "Adds init kmsg markers for boot readiness, trigger, service PID/running/stopped. Existing init -> zygote transition via zygote_exec is reused; no new SELinux allow, CIL, or property-context rule is added.",
            "Preserves C31 no_fatal.zygote and all C31/C30 inherited startup, diagnostics, netd, ART, graphics, kernel, fstab, encryption, and logical partition inputs.",
        ],
        "evidence_basis": {
            "C31": "C31 runtime showed primary Zygote PID 1059 as the first main SIGABRT PID and only the generic crash_dump helper EOF message; no matching Bionic/debuggerd source/build/signing chain was found for patching the Xiaomi runtime linker64.",
            "SELinux_transition": transition_info,
            "init_trigger": "C31 starts tombstoned in post-fs-data before zygote-start; Android init boot event is later. The combined boot + tombstoned-running trigger is checked once at boot and cannot retrigger on later tombstoned property changes.",
        },
        "source_delta": source_delta["tree_delta"],
        "source_delta_expected": {"removed": [], "added": [CANARY_REL],
                                   "modified": [SYSTEM_INIT, FILE_CONTEXTS]},
        "init_change": source_delta["init_patch"],
        "platform_file_context": CANARY_FILE_CONTEXT,
        "mkfs_file_context": CANARY_MKFS_CONTEXT,
        "new_selinux_allow_rules": False,
        "transition": transition_info,
        "system_build": system_info,
        "vbmeta_system_update": vbmeta_info,
        "logical_input_hashes": logical_hashes,
        "flash_scope_prepared": ["super", "vbmeta_system_a"],
        "inherited_images": {name: c31_manifest["images"][name] for name in INHERITED_SMALL},
        "images": entries,
        "host_storage_gate": storage,
        "device_operations": "none during build; dedicated flash script is separate and does not reboot",
    }
    (C32_IMAGES / "BUILD_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    REPORT_DIR.mkdir(parents=True, exist_ok=False)
    report = [
        "# C32-DIAG 构建与静态门禁报告", "",
        "## 目标与边界", "",
        "C32 只用一个最小 native AArch64 进程，在现有 `zygote_exec` → `zygote` transition 下主动 SIGABRT，区分普通 zygote-domain native 进程的 crash dump 能力与真实 Zygote 的 ART/seccomp/namespace 等专属上下文。它不是正式修复。成功不证明真实 Zygote 的完整 dump 路径正常；失败也不单独证明 SELinux 是根因。", "",
        "不直接 patch Xiaomi runtime APEX 的 linker64：C31 已有 ELF 中 handler 线索，但没有匹配其实际 build revision 的 Bionic/debuggerd 源码、Soong 树及可验证的 APEX payload/container 双签工作流。", "",
        "## 静态可行性", "",
        f"- C31 已有 `zygote_exec` file type、`init -> zygote` type transition 和 init 执行权限：{transition_info}",
        "- 没有增加 SELinux allow/CIL/property-context。C32 只在 `plat_file_contexts` 为新 canary 指向现有 `zygote_exec`，并在 EROFS mkfs file_contexts 输入增加同一最小文件映射。服务不写 `seclabel`，由 init 根据 entrypoint 文件类型执行现有 transition。",
        "- C31 没有 zygote 对 `/proc/self/attr/current` 的明确读取权限，因此 canary 不尝试读取，以免为报告 domain 人为引入 AVC。真实标签由 crash tombstone 的 SELinux label 运行时字段确认；若没有 tombstone，则不能声称动态确认了实际 domain。", "",
        "## 单次触发与进程生命周期", "",
        "- tombstoned 的 service 定义存在；主 init 在 post-fs-data 先执行 `start tombstoned`。C31 启动序列随后触发 zygote-start，再到 boot。",
        "- 触发采用 `on boot && property:init.svc.tombstoned=running`，只在 boot 事件的一次检查中执行；如果 tombstoned 当时没运行就不启动 canary，也不会在它稍后变化时重复启动。",
        "- canary service 为 `disabled + oneshot`，没有 critical、onrestart、seclabel 或 restart。init 从 init.svc_debug_pid/state 事件写 `/dev/kmsg` lifecycle markers；C31 的 C30 logger和pstore路径保留用于持久日志。", "",
        "## Canary ELF", "",
        f"- 输入 source SHA-256：`{canary_info['source_sha256']}`；输出 ELF `{canary_info['bytes']}` bytes，SHA-256 `{canary_info['sha256']}`。",
        f"- AArch64 PIE，interpreter `{canary_info['interpreter']}`，依赖 `{', '.join(canary_info['needed'])}`，NDK target API {ANDROID_API}。进程尝试将 comm 设为 `main`，记录 PID 和预期 domain transition，设置固定 abort message `THYME_C32_CANARY_ABORT`，随后执行一次 `abort()`。",
        "- 本地只完成目标 ELF 静态检查、system EROFS/AVB/LP 构建验证；没有在 ARM64 设备或模拟器实际运行 canary。", "",
        "## C31→C32 变化", "",
        f"- 精确 system tree diff：`{source_delta['tree_delta']}`。",
        "- 没有改 runtime APEX/linker64、debuggerd、crash_dump、tombstoned、zygote service/critical、secondary callback、netd、ART、Framework、GPU/HWC/Vulkan、kernel、fstab、加密或 userdata/metadata。",
        "- C32 system EROFS/fsck、最终文件 readback、ELF 字节一致性、system AVB verify、配套 vbmeta_system descriptor、LP repack/lpdump 和镜像 manifest 均由 BUILD_MANIFEST 记录。", "",
        "## 实机状态", "",
        "本报告生成于主机侧构建阶段。是否刷入和设备实时 Fastboot/A/B 状态由后续受限刷写 transcript 记录；本构建过程不发设备命令，不会自动 reboot。C32 首次启动仍需用户明确说“开始启动”。", "",
        "## 结果解释", "",
        "Result A 需在设备运行后取得 canary PID、SIGABRT、固定 abort message、zygote SELinux label、backtrace/tombstone、crash_dump 与 tombstoned 成功、helper 无异常和相关 AVC 缺失。Result B 需 canary 确认位于 zygote domain 且仍复现 helper EOF；随后仍需定点区分域、exec、linker、helper、tombstoned 与实际上下文。Result C 为无法建立目标 domain，此时该实验无区分力。当前尚无运行结果。", "",
    ]
    (REPORT_DIR / "C32_DIAG_BUILD_FLASH_STATIC_GATE.md").write_text(
        "\n".join(report), encoding="utf-8", newline="\n")
    print(json.dumps({"candidate": CANDIDATE, "system_tree_delta": source_delta["tree_delta"],
                      "transition": transition_info, "system_build": system_info,
                      "vbmeta_system": vbmeta_info, "logical_input_hashes": logical_hashes,
                      "images": entries, "report": str(REPORT_DIR)},
                     ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
