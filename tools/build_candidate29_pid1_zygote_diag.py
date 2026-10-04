#!/usr/bin/env python3
"""Build C29: C28-preserving, time-ordered PID1/Zygote diagnostics."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
C28_STAGE = ROOT / "work/stage_c28_recovery_zygote_diag_20260929_run4"
C28_IMAGES = C28_STAGE / "images"
C28_WORK = Path("/path/to/thyme-os4-build/c28_recovery_zygote_diag_20260929_run4")
C28_TREE = C28_WORK / "system_tree"
C29_STAGE = ROOT / "work/stage_c29_pid1_zygote_diag_20260929_run6"
C29_IMAGES = C29_STAGE / "images"
C29_REPORT = ROOT / "work/reports/20260929_C29_PID1_ZYGOTE_FATAL_DIAGNOSTIC"
C29_WORK = Path("/path/to/thyme-os4-build/c29_pid1_zygote_diag_20260929_run6")
C29_TREE = C29_WORK / "system_tree"
TEMPLATE = ROOT / "tools/candidate29_pid1_zygote_diag"
SOURCE = TEMPLATE / "c29_pid1_zygote_diag.cpp"
SERVICE_RC = TEMPLATE / "c29_pid1_zygote_diag.rc"
SYSTEM_INIT = "system/etc/init/hw/init.rc"
FILE_CONTEXTS = "system/etc/selinux/plat_file_contexts"
NETD_RC = "system/etc/init/netd.rc"
PRIMARY_RC = "system/etc/init/hw/init.zygote64.rc"
SECONDARY_RC = "system/etc/init/hw/init.zygote64_32.rc"
C28_RC = "system/etc/init/c28_recovery_diag.rc"
C28_HELPER = "system/bin/c28_recovery_diag"
C29_RC = "system/etc/init/c29_pid1_zygote_diag.rc"
C29_HELPER = "system/bin/c29_pid1_zygote_diag"
IMPORT_C28 = "import /system/etc/init/c28_recovery_diag.rc"
IMPORT_C29 = "import /system/etc/init/c29_pid1_zygote_diag.rc"
IMPORT_C25 = "import /system/etc/init/c25_bootdiag.rc"
NETD_CALLBACKS = ("onrestart restart zygote", "onrestart restart zygote_secondary")
IMAGE_NAMES = ("boot.img", "vendor_boot.img", "dtbo.img", "vbmeta.img",
               "vbmeta_system.img", "super.img")
INHERITED_SMALL = ("boot.img", "vendor_boot.img", "dtbo.img", "vbmeta.img")
CANDIDATE = "Candidate 29 PID1/Zygote ordered fatal diagnostics"
BASE = "Candidate 28 Recovery/Zygote persistent startup diagnostics"


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


def run_bytes(args: list[str | os.PathLike[str]], output_path: Path) -> bytes:
    command = [os.fspath(value) for value in args]
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        raise subprocess.CalledProcessError(result.returncode, command,
            result.stderr.decode("utf-8", errors="replace"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(result.stdout)
    return result.stdout


def inventory(root: Path) -> dict[str, Path]:
    found: dict[str, Path] = {}
    for path in root.rglob("*"):
        if path.is_file() or path.is_symlink():
            found[path.relative_to(root).as_posix()] = path
    return found


def load_c28_manifest() -> tuple[dict[str, object], dict[str, dict[str, object]]]:
    path = C28_IMAGES / "BUILD_MANIFEST.json"
    require_file(path)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("candidate") != BASE:
        raise RuntimeError("C28 manifest does not identify the requested base.")
    if set(manifest.get("images", {})) != set(IMAGE_NAMES):
        raise RuntimeError("C28 manifest does not contain exactly six images.")
    if manifest.get("flash_scope_prepared") != ["super", "vbmeta_system_a"]:
        raise RuntimeError("C28 flash scope differs from the two allowed targets.")
    checked: dict[str, dict[str, object]] = {}
    for name in INHERITED_SMALL + ("vbmeta_system.img",):
        image = C28_IMAGES / name
        expected = manifest["images"][name]
        require_file(image, int(expected["bytes"]))
        actual = sha256(image)
        if actual != str(expected["sha256"]).upper():
            raise RuntimeError(f"C28 inherited image differs from its manifest: {name}")
        checked[name] = {"bytes": image.stat().st_size, "sha256": actual}
    require_file(C28_IMAGES / "super.img", int(manifest["images"]["super.img"]["bytes"]))
    return manifest, checked


def replace_file(path: Path, content: bytes, mode: int) -> None:
    if path.exists() or path.is_symlink():
        path.unlink()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    os.chmod(path, mode)


def patch_c28_import() -> dict[str, object]:
    path = C29_TREE / SYSTEM_INIT
    original = path.read_text(encoding="utf-8")
    if original.count(IMPORT_C28) != 1 or IMPORT_C29 in original:
        raise RuntimeError("C28 init import baseline is not exact.")
    if original.count("import /system/etc/init/c25_bootdiag.rc") != 1:
        raise RuntimeError("Inherited C25 import count differs from C28.")
    updated = original.replace(IMPORT_C28, IMPORT_C29, 1)
    replace_file(path, updated.encode("utf-8"), stat.S_IMODE(path.stat().st_mode))
    return {"base_import": IMPORT_C28, "candidate_import": IMPORT_C29,
            "only_import_changed": updated == original.replace(IMPORT_C28, IMPORT_C29, 1)}


def install_tree(c28_builder) -> dict[str, object]:
    init_info = patch_c28_import()
    old_rc = C29_TREE / C28_RC
    old_helper = C29_TREE / C28_HELPER
    require_file(old_rc)
    require_file(old_helper)
    old_rc.unlink()
    old_helper.unlink()

    rc_path = C29_TREE / C29_RC
    helper_path = C29_TREE / C29_HELPER
    if rc_path.exists() or helper_path.exists():
        raise FileExistsError("C29 diagnostic files already exist in cloned tree.")
    shutil.copy2(SERVICE_RC, rc_path)
    os.chmod(rc_path, 0o644)

    contexts_path = C29_TREE / FILE_CONTEXTS
    contexts = contexts_path.read_text(encoding="utf-8")
    old_entries = (
        "/system/bin/c28_recovery_diag u:object_r:shell_exec:s0",
        "/system/etc/init/c28_recovery_diag\\.rc u:object_r:system_file:s0",
    )
    for entry in old_entries:
        if contexts.count(entry) != 1:
            raise RuntimeError(f"Expected exactly one C28 file context: {entry}")
        contexts = contexts.replace(entry, "", 1)
    new_entries = (
        "/system/bin/c29_pid1_zygote_diag u:object_r:shell_exec:s0",
        "/system/etc/init/c29_pid1_zygote_diag\\.rc u:object_r:system_file:s0",
    )
    if any(entry.split()[0] in contexts for entry in new_entries):
        raise RuntimeError("C29 file context already exists in base tree.")
    replace_file(contexts_path,
        (contexts.rstrip("\n") + "\n" + "\n".join(new_entries) + "\n").encode(),
        stat.S_IMODE(contexts_path.stat().st_mode))

    netd = (C29_TREE / NETD_RC).read_text(encoding="utf-8")
    if netd.count("service netd /system/bin/netd") != 1 or any(
            line.strip() in NETD_CALLBACKS for line in netd.splitlines()):
        raise RuntimeError("C28 netd service/callback baseline changed unexpectedly.")
    if sha256(C29_TREE / "system/etc/selinux/plat_sepolicy.cil") != \
            sha256(C28_TREE / "system/etc/selinux/plat_sepolicy.cil"):
        raise RuntimeError("C29 must not change SELinux CIL.")
    if sha256(C29_TREE / PRIMARY_RC) != sha256(C28_TREE / PRIMARY_RC):
        raise RuntimeError("C29 must preserve primary Zygote critical policy.")
    if sha256(C29_TREE / SECONDARY_RC) != sha256(C28_TREE / SECONDARY_RC):
        raise RuntimeError("C29 must preserve secondary Zygote restart callback.")
    return {"init_import": init_info, "removed": [C28_RC, C28_HELPER],
            "added": [C29_RC, C29_HELPER], "file_contexts_removed": list(old_entries),
            "file_contexts_added": list(new_entries), "netd_callbacks_still_absent": True,
            "primary_critical_policy_unchanged": True,
            "secondary_callback_unchanged": True, "selinux_cil_unchanged": True}


def compile_helper(stage: Path) -> tuple[Path, dict[str, object]]:
    ndk = Path("/path/to/thyme-os4-build/toolchains/android-ndk-r29/toolchains/llvm/prebuilt/linux-x86_64")
    clang = ndk / "bin/clang++"
    sysroot = ndk / "sysroot"
    require_file(clang)
    require_file(sysroot / "usr/include/sys/system_properties.h")
    binary = stage / "c29_pid1_zygote_diag"
    command = [str(clang), "--target=aarch64-linux-android35", f"--sysroot={sysroot}",
               "-std=c++17", "-O2", "-fPIE", "-pie", "-static-libstdc++",
               "-D_FORTIFY_SOURCE=2", "-Wall", "-Wextra", "-Werror", "-o",
               str(binary), str(SOURCE), "-llog"]
    run(command, stage / "compile_c29_pid1_zygote_diag.log")
    os.chmod(binary, 0o755)
    readelf = shutil.which("llvm-readelf") or shutil.which("readelf")
    if not readelf:
        raise FileNotFoundError("readelf is required to validate the C29 helper ELF.")
    elf = run([readelf, "-h", binary], stage / "c29_helper_elf_header.txt")
    dynamic = run([readelf, "-d", binary], stage / "c29_helper_dynamic_deps.txt")
    if "AArch64" not in elf or "PIE" not in dynamic or "liblog.so" not in dynamic or \
            "libc++_shared.so" in dynamic:
        raise RuntimeError("C29 helper ELF architecture or dependency validation failed.")
    return binary, {"bytes": binary.stat().st_size, "sha256": sha256(binary),
                    "architecture": "AArch64", "needed": ["liblog.so"],
                    "cxx_runtime": "statically linked libc++", "source_sha256": sha256(SOURCE)}


def audit_delta() -> dict[str, object]:
    before = inventory(C28_TREE)
    after = inventory(C29_TREE)
    removed = set(before) - set(after)
    added = set(after) - set(before)
    modified: set[str] = set()
    for rel in set(before) & set(after):
        old, new = before[rel], after[rel]
        if old.is_symlink() or new.is_symlink():
            if not (old.is_symlink() and new.is_symlink() and os.readlink(old) == os.readlink(new)):
                modified.add(rel)
        else:
            a, b = old.stat(), new.stat()
            if a.st_dev == b.st_dev and a.st_ino == b.st_ino:
                continue
            if a.st_size != b.st_size or sha256(old) != sha256(new):
                modified.add(rel)
    expected_removed = {C28_RC, C28_HELPER}
    expected_added = {C29_RC, C29_HELPER}
    expected_modified = {SYSTEM_INIT, FILE_CONTEXTS}
    if removed != expected_removed or added != expected_added or modified != expected_modified:
        raise RuntimeError(f"C29 tree delta exceeded allowlist: removed={sorted(removed)}, "
                           f"added={sorted(added)}, modified={sorted(modified)}")
    base_init = (C28_TREE / SYSTEM_INIT).read_text(encoding="utf-8")
    new_init = (C29_TREE / SYSTEM_INIT).read_text(encoding="utf-8")
    if new_init.replace(IMPORT_C29, IMPORT_C28, 1) != base_init:
        raise RuntimeError("C29 init.rc contains changes beyond its single diagnostic import.")
    return {"removed": sorted(removed), "added": sorted(added),
            "modified": sorted(modified), "unexpected_changes": []}


def build_system(builder, stage: Path) -> tuple[Path, dict[str, object]]:
    init_rc = C29_TREE / SYSTEM_INIT
    service_rc = C29_TREE / C29_RC
    helper = C29_TREE / C29_HELPER
    netd_rc = C29_TREE / NETD_RC
    for path in (init_rc, service_rc, helper, netd_rc):
        require_file(path)
    init_text = init_rc.read_text(encoding="utf-8")
    if init_text.count(IMPORT_C25) != 1 or IMPORT_C28 in init_text or init_text.count(IMPORT_C29) != 1:
        raise RuntimeError("C29 init import assertions failed.")
    rc_text = service_rc.read_text(encoding="utf-8")
    required_tokens = (
        "C29_POST_FS_DATA.txt", "C29_INIT_PRIMARY_RUNNING.txt",
        "C29_INIT_PRIMARY_RESTARTING.txt", "C29_INIT_SECONDARY_RUNNING.txt",
        "C29_INIT_SECONDARY_RESTARTING.txt", "C29_BOOT_COMPLETED.txt",
        "C29_SYS_POWERCTL.txt", "C29_SHUTDOWN.txt", "start c29_logcat",
        "start c29_zygote_watch", "seclabel u:r:shell:s0",
    )
    for token in required_tokens:
        if token not in rc_text:
            raise RuntimeError(f"C29 init RC missing {token}.")
    helper_source = SOURCE.read_text(encoding="utf-8")
    if '"-r"' in helper_source or '"-n"' in helper_source or "-r -n" in helper_source:
        raise RuntimeError("C29 logcat must use a single non-rotating file.")
    for marker in ("C29_LOGCAT_START", "C29_LOGCAT_CHILD", "C29_LOGCAT_EXEC_FAILED",
                   "wait_status_valid", "CLOCK_BOOTTIME", "O_APPEND", "fdatasync",
                   "boot_instance"):
        if marker not in helper_source:
            raise RuntimeError(f"C29 helper lacks required diagnostic behavior: {marker}")
    if any(line.strip() in NETD_CALLBACKS for line in netd_rc.read_text(encoding="utf-8").splitlines()):
        raise RuntimeError("C29 must retain C27 removal of netd-to-Zygote callbacks.")

    base_contexts = builder.C1 / "configs_retained/system/file_contexts"
    fs_config_source = builder.C1 / "configs_retained/system/fs_config"
    require_file(base_contexts)
    require_file(fs_config_source)
    contexts_path = stage / "system_file_contexts_c29"
    contexts = base_contexts.read_text(encoding="utf-8")
    context_additions = (
        "/system/system/bin/c25_bootdiag u:object_r:shell_exec:s0",
        "/system/system/etc/init/c25_bootdiag\\.rc u:object_r:system_file:s0",
        "/system/system/bin/c29_pid1_zygote_diag u:object_r:shell_exec:s0",
        "/system/system/etc/init/c29_pid1_zygote_diag\\.rc u:object_r:system_file:s0",
    )
    contexts += "\n" + "\n".join(context_additions) + "\n"
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
    for entry in sorted(C29_TREE.rglob("*"), key=lambda p: p.relative_to(C29_TREE).as_posix()):
        relative = "system/" + entry.relative_to(C29_TREE).as_posix()
        if relative in known:
            continue
        st = entry.lstat()
        added.append(f"{relative} {st.st_uid} {st.st_gid} {stat.S_IMODE(st.st_mode):04o}")
        known.add(relative)
    fs_config = stage / "system_fs_config_c29"
    fs_config.write_text("\n".join(rebased + added) + "\n", encoding="utf-8", newline="\n")

    raw = stage / "system_c29.raw.erofs"
    image = stage / "system_c29.img"
    builder.run([builder.MKFS, "-zlz4hc", "-T", "0", "-U", builder.SYSTEM_UUID,
                 "--mount-point=/system", f"--fs-config-file={fs_config}",
                 f"--file-contexts={contexts_path}", raw, C29_TREE],
                log=stage / "mkfs_system_c29.log")
    builder.run([builder.FSCK, "-d0", raw], log=stage / "fsck_system_c29.log")
    shutil.copy2(raw, image)
    builder.run(["python3", builder.AVBTOOL, "add_hashtree_footer", "--image", image,
                 "--partition_size", str(builder.SYSTEM_SIZE), "--partition_name", "system",
                 "--hash_algorithm", "sha256", "--salt", builder.SYSTEM_SALT,
                 "--algorithm", "NONE", "--do_not_generate_fec"],
                log=stage / "avb_system_c29.log")
    require_file(image, builder.SYSTEM_SIZE)

    checks_to_read = {
        "/system/etc/init/hw/init.rc": (IMPORT_C29, "C28_RECOVERY_BAD_NV_VENDOR.txt",
            "C28_RECOVERY_BAD_NV_RADIO.txt", "rebootrecovery --bad_nv"),
        "/system/etc/init/c29_pid1_zygote_diag.rc": required_tokens,
        "/system/etc/init/netd.rc": ("service netd /system/bin/netd",),
        "/system/etc/selinux/plat_file_contexts": (
            "/system/bin/c29_pid1_zygote_diag", "/system/etc/init/c29_pid1_zygote_diag\\.rc"),
        "/system/bin/c29_pid1_zygote_diag": ("C29ZygoteDiag", "C29_LOGCAT_START",
            "C29_LOGCAT_CHILD", "C29_LOGCAT_EXEC_FAILED", "process_first_seen",
            "init.svc.zygote", "init.svc.zygote_secondary", "logger_exit"),
    }
    readback: dict[str, object] = {}
    readback_dir = stage / "erofs_readback"
    for erofs_path, tokens in checks_to_read.items():
        out = readback_dir / erofs_path.lstrip("/").replace("/", "_")
        content = run_bytes([builder.DUMP, "--cat", f"--path={erofs_path}", raw], out)
        if erofs_path.endswith("c29_pid1_zygote_diag"):
            if not content.startswith(b"\x7fELF") or hashlib.sha256(content).hexdigest().upper() != sha256(C29_TREE / C29_HELPER):
                raise RuntimeError("Final EROFS helper readback is not byte-identical to compiled ELF.")
            read_text = content.decode("latin-1")
        else:
            read_text = content.decode("utf-8", errors="replace")
        missing = [token for token in tokens if token not in read_text]
        if missing:
            raise RuntimeError(f"Final EROFS readback missing {erofs_path} tokens: {missing}")
        readback[erofs_path] = {"bytes": len(content),
                                "sha256": hashlib.sha256(content).hexdigest().upper(),
                                "required_tokens": list(tokens)}
        if erofs_path == "/system/etc/init/hw/init.rc":
            final = content.decode("utf-8", errors="strict")
            if final.count("rebootrecovery --bad_nv") != 2:
                raise RuntimeError("C29 altered inherited Recovery command count.")
        if erofs_path == "/system/etc/init/netd.rc":
            for callback in NETD_CALLBACKS:
                if callback.encode() in content:
                    raise RuntimeError("C29 netd callbacks unexpectedly reappeared.")

    verify_link = image.parent / "system.img"
    if verify_link.exists() or verify_link.is_symlink():
        raise FileExistsError(f"Refusing existing AVB verification sibling: {verify_link}")
    verify_link.symlink_to(image)
    builder.run(["python3", builder.AVBTOOL, "verify_image", "--image", image],
                log=stage / "avb_verify_system_c29.log")
    verify_link.unlink()
    return image, {"system_image_bytes": image.stat().st_size,
            "system_image_sha256": sha256(image), "final_erofs_readback": readback,
            "new_file_contexts": list(context_additions),
            "new_fs_config_paths": ["system/system/bin/c29_pid1_zygote_diag",
                                     "system/system/etc/init/c29_pid1_zygote_diag.rc"],
            "selinux_cil_changed": False}


def main() -> None:
    if "microsoft" not in Path("/proc/sys/kernel/osrelease").read_text().lower():
        raise RuntimeError("Run this builder inside WSL Ubuntu.")
    storage: dict[str, float] = {}
    for drive, mount in (("C", "/mnt/c"), ("D", "/mnt/d"), ("E", "/mnt/e")):
        usage = shutil.disk_usage(mount)
        free_gib = round(usage.free / (1024 ** 3), 2)
        storage[f"{drive}_free_gib"] = free_gib
        print(f"[SPACE] {drive}: free={free_gib:.2f} GiB", flush=True)
        if usage.free < 50 * 1024 ** 3:
            raise RuntimeError(f"{drive}: below 50 GiB project gate; build not started.")
    c28_manifest, inherited = load_c28_manifest()
    require_file(C28_TREE / SYSTEM_INIT)
    require_file(C28_TREE / C28_RC)
    require_file(C28_TREE / C28_HELPER)
    require_file(C28_TREE / NETD_RC)
    require_file(SOURCE)
    require_file(SERVICE_RC)
    if C29_STAGE.exists() or C29_WORK.exists():
        raise FileExistsError("C29 output exists; refusing to overwrite previous assets.")
    c23 = load_module("candidate23_builder_for_c29", ROOT / "tools/build_candidate23_sf_prime_skip.py")
    c24 = load_module("candidate24_builder_for_c29", ROOT / "tools/build_candidate24_framework_display_diag.py")
    c28 = load_module("candidate28_builder_for_c29", ROOT / "tools/build_candidate28_recovery_diag.py")
    for tool in (c23.MKFS, c23.FSCK, c23.DUMP, c23.LPMAKE, c23.SIMG2IMG,
                 c23.LPDUMP, c23.AVBTOOL):
        require_file(tool)
    for executable in (c23.MKFS, c23.FSCK, c23.DUMP, c23.LPMAKE, c23.SIMG2IMG, c23.LPDUMP):
        if not os.access(executable, os.X_OK):
            raise PermissionError(f"Build tool is not executable: {executable}")

    C29_STAGE.mkdir(parents=True, exist_ok=False)
    C29_IMAGES.mkdir(parents=True, exist_ok=False)
    C29_WORK.mkdir(parents=True, exist_ok=False)
    stage = C29_WORK / "staging"
    stage.mkdir(parents=True, exist_ok=False)
    shutil.copytree(C28_TREE, C29_TREE, symlinks=True, copy_function=c28.hardlink_or_copy)
    tree_changes = install_tree(c28)
    compiled, helper_info = compile_helper(stage)
    shutil.copy2(compiled, C29_TREE / C29_HELPER)
    os.chmod(C29_TREE / C29_HELPER, 0o755)
    tree_delta = audit_delta()

    print("[C29] Building one diagnostic-only system update on the C28 baseline.", flush=True)
    system_image, system_info = build_system(c23, stage)
    c24.C23_IMAGES = C28_IMAGES
    vbmeta_info = c24.rebuild_vbmeta_system_c24(c23, system_image,
        C29_IMAGES / "vbmeta_system.img", stage)
    c23.C23_IMAGES = C29_IMAGES
    super_image, logical_hashes = c23.build_super(system_image, stage)
    if logical_hashes != c28_manifest.get("logical_input_hashes", {}):
        raise RuntimeError("A non-system logical partition input differs from C28.")
    for name in INHERITED_SMALL:
        shutil.copy2(C28_IMAGES / name, C29_IMAGES / name)
        if sha256(C29_IMAGES / name) != inherited[name]["sha256"]:
            raise RuntimeError(f"Inherited C28 image changed: {name}")
    entries: dict[str, dict[str, object]] = {}
    for name in IMAGE_NAMES:
        image = C29_IMAGES / name
        require_file(image)
        entries[name] = {"bytes": image.stat().st_size, "sha256": sha256(image)}
    manifest = {
        "candidate": CANDIDATE, "base": BASE,
        "changes": [
            "Replaces the C28 diagnostic helper/RC with C29 ordered event and persistent logcat diagnostics.",
            "Starts both observers at post-fs-data before the inherited zygote-start trigger; writes monotonic boot-id-tagged service/property events using O_APPEND and fdatasync, alongside init built-in per-state markers.",
            "Runs direct /system/bin/logcat -b all -v threadtime,monotonic -f to one unique metadata file for at most 60 seconds; no -r/-n rotation; RLIMIT_FSIZE caps the file at up to 8 MiB while reserving metadata space; records START, child PID, exec errno, wait status, exit code/signal and stop reason.",
            "Preserves C28/C27 system behavior: no change to Zygote critical policy, secondary onrestart, netd callbacks already removed by C27, SELinux CIL, GPU/HWC, kernel, fstab, data encryption, or user data.",
        ],
        "evidence_basis": [
            "C28 pstore directly records PID 1 writing /proc/sysrq-trigger and a subsequent sysrq panic at about 33.464s; fatal signal and preceding init LOG(FATAL) are absent from saved bytes.",
            "C28 pmsg contains five SIGABRT processes named main in zygote SELinux domain, while metadata markers show primary zygote running/restarting and secondary running but have no timestamps/PID mapping.",
            "Image-derived zygote.critical_window.minute is 10 and C28 primary service has critical window=${zygote.critical_window.minute:-off}; this is a strong candidate escalation chain, not a closed runtime causal mapping.",
            "C26 direct logcat -f produced about 8.56 MB on-device. C28 logger files were empty/stopped without enough runtime status to explain why; C29 reuses direct logcat capture and records the parent/child result.",
        ],
        "diagnostic_limits": [
            "Runtime PID-to-primary/secondary mapping and exact service restart count remain unknown until C29 event/logcat output is recovered.",
            "C29 does not disable critical escalation or alter the secondary callback because their exact causal role is not proven by C28 evidence.",
            "The observer polls init properties every 10ms; very brief transitions could still be missed, with init built-in markers providing a separate state-occurrence channel.",
            "A kernel panic can interrupt status finalization; immediate START and per-event fdatasync preserve whatever was committed beforehand.",
        ],
        "tree_changes": tree_changes, "tree_delta": tree_delta,
        "runtime_helper": helper_info, "system_build": system_info,
        "vbmeta_system_update": vbmeta_info,
        "logical_input_hashes": logical_hashes,
        "flash_scope_prepared": ["super", "vbmeta_system_a"],
        "inherited_images_checked": inherited, "images": entries,
        "host_storage_gate": storage,
    }
    (C29_IMAGES / "BUILD_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    C29_REPORT.mkdir(parents=True, exist_ok=True)
    report = [
        "# Candidate 29 PID1/Zygote 有序故障诊断构建报告", "",
        "## 决策", "",
        "C28 的根本 fatal signal、init LOG(FATAL) 和 PID 1063 身份仍不可见。五个 `main` SIGABRT 与 primary Zygote 的 critical 配置相符，但没有 PID/服务映射、restart 顺序或可见的 critical-process fatal 记录；`zygote_secondary` 的状态 marker 无时间戳。故离线证据尚不足以关闭 critical 或切断 secondary→primary 回调。C29 是诊断版，不是已证明的系统修复。", "",
        "## C29 改动", "",
        "C29 继承 C28，netd→Zygote 两条回调继续保持移除。仅替换系统诊断 RC/helper：在 post-fs-data 启动有序采样与日志器，按 `CLOCK_BOOTTIME`、内核 boot ID、event/service/PID 追加并 fdatasync；每 10 ms 采样 netd、两个 Zygote、`sys.boot_completed`、`sys.powerctl`，并扫描 system_server 首次 PID。init `write` marker 作为第二通道。logcat 沿用 C26 直接 `-f` 路线，单文件、最多 60 秒/8 MiB、无 rotation，并持久记录 helper/child/exec/wait 结果。", "",
        "未修改 Zygote `critical`、secondary `onrestart`、netd 逻辑、SELinux CIL、GPU/HWC、Framework、内核、fstab 或数据加密。", "",
        "## 构建和最终镜像", "",
        f"构建器仅在 C/D/E 均不低于 50 GiB 时启动；本次门禁记录 `{storage}`。C28 非系统逻辑分区输入与 C29 LP 输入逐项哈希相同。刷写范围仅为 `super`、`vbmeta_system_a`。", "",
        "| 镜像 | 字节 | SHA-256 |", "|---|---:|---|",
    ]
    report += [f"| `{name}` | {entries[name]['bytes']} | `{entries[name]['sha256']}` |" for name in IMAGE_NAMES]
    report += ["", "构建器完成 helper AArch64 PIE/依赖检查、system EROFS fsck/readback、helper 字节级 readback、system AVB hashtree/vbmeta_system descriptor 与 LP 布局验证。此为主机验证，不代表 C29 已刷写或已启动。", ""]
    (C29_STAGE / "C29_PID1_ZYGOTE_DIAGNOSTIC_BUILD_REPORT.md").write_text(
        "\n".join(report), encoding="utf-8", newline="\n")
    print(f"[C29] Build complete: {C29_IMAGES}", flush=True)
    for name in IMAGE_NAMES:
        print(f"  {name}: {entries[name]['bytes']} bytes SHA256={entries[name]['sha256']}", flush=True)


if __name__ == "__main__":
    main()
