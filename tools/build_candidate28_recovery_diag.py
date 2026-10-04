#!/usr/bin/env python3
"""Build C28 as a C27-preserving init/recovery and logger diagnostic."""

from __future__ import annotations

import errno
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
C27_WORK = Path("/path/to/thyme-os4-build/c27_netd_zygote_cycle_break_20260929_run1")
C27_TREE = C27_WORK / "system_tree"
C28_WORK = Path("/path/to/thyme-os4-build/c28_recovery_zygote_diag_20260929_run4")
C28_TREE = C28_WORK / "system_tree"
C27_DIR = ROOT / "work/stage_c27_netd_zygote_cycle_break_20260929_run1"
C27_IMAGES = C27_DIR / "images"
C28_DIR = ROOT / "work/stage_c28_recovery_zygote_diag_20260929_run4"
C28_IMAGES = C28_DIR / "images"
C28_REPORT_DIR = ROOT / "work/reports/20260929_C28_RECOVERY_ZYGOTE_DIAGNOSTIC"
TEMPLATE_DIR = ROOT / "tools/candidate28_recovery_diag"
IMAGE_NAMES = ("boot.img", "vendor_boot.img", "dtbo.img", "vbmeta.img",
               "vbmeta_system.img", "super.img")
SMALL_INHERITED = ("boot.img", "vendor_boot.img", "dtbo.img", "vbmeta.img")
CANDIDATE = "Candidate 28 Recovery/Zygote persistent startup diagnostics"
BASE = "Candidate 27 netd-to-Zygote restart-cycle fix and diagnostic"
IMPORT_C25 = "import /system/etc/init/c25_bootdiag.rc"
IMPORT_C27 = "import /system/etc/init/c27_zygote_diag.rc"
IMPORT_C28 = "import /system/etc/init/c28_recovery_diag.rc"
NETD_RESTART_COMMANDS = ("onrestart restart zygote", "onrestart restart zygote_secondary")
SYSTEM_INIT = "system/etc/init/hw/init.rc"
CONTEXTS = "system/etc/selinux/plat_file_contexts"
NETD_RC = "system/etc/init/netd.rc"
C27_RC = "system/etc/init/c27_zygote_diag.rc"
C27_HELPER = "system/bin/c27_zygote_diag"
C28_RC = "system/etc/init/c28_recovery_diag.rc"
C28_HELPER = "system/bin/c28_recovery_diag"
EXPECTED_RECOVERY_ACTIONS = (
    ("on property:persist.vendor.radio.write.cache=1 && property:persist.vendor.ssr.restart_level=ALL_ENABLE\n"
     "  rebootrecovery --bad_nv", "C28_RECOVERY_BAD_NV_VENDOR.txt",
     "candidate=C28 event=rebootrecovery_bad_nv source=vendor_radio "
     "write_cache=${persist.vendor.radio.write.cache} ssr=${persist.vendor.ssr.restart_level}"),
    ("on property:persist.radio.write.cache=1\n"
     "  rebootrecovery --bad_nv", "C28_RECOVERY_BAD_NV_RADIO.txt",
     "candidate=C28 event=rebootrecovery_bad_nv source=radio "
     "write_cache=${persist.radio.write.cache}"),
)


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
        error = result.stderr.decode("utf-8", errors="replace")
        raise subprocess.CalledProcessError(result.returncode, command, error)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(result.stdout)
    return result.stdout


def load_c27_manifest() -> tuple[dict[str, object], dict[str, dict[str, object]]]:
    manifest_path = C27_IMAGES / "BUILD_MANIFEST.json"
    require_file(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("candidate") != BASE:
        raise RuntimeError("C27 manifest does not identify the expected base.")
    if set(manifest.get("images", {})) != set(IMAGE_NAMES):
        raise RuntimeError("C27 manifest does not contain exactly six images.")
    if manifest.get("flash_scope_prepared") != ["super", "vbmeta_system_a"]:
        raise RuntimeError("C27 manifest has an unexpected flash scope.")
    checked: dict[str, dict[str, object]] = {}
    for name in SMALL_INHERITED + ("vbmeta_system.img",):
        path = C27_IMAGES / name
        expected = manifest["images"][name]
        require_file(path, int(expected["bytes"]))
        actual = sha256(path)
        if actual != str(expected["sha256"]).upper():
            raise RuntimeError(f"C27 inherited image differs from its manifest: {name}")
        checked[name] = {"bytes": path.stat().st_size, "sha256": actual}
    require_file(C27_IMAGES / "super.img", int(manifest["images"]["super.img"]["bytes"]))
    return manifest, checked


def hardlink_or_copy(source: str, destination: str) -> str:
    try:
        os.link(source, destination, follow_symlinks=False)
    except OSError as exc:
        if exc.errno not in (errno.EXDEV, errno.EPERM, errno.EACCES, errno.EOPNOTSUPP):
            raise
        shutil.copy2(source, destination, follow_symlinks=False)
    return destination


def clone_c27_tree() -> None:
    require_file(C27_TREE / SYSTEM_INIT)
    require_file(C27_TREE / NETD_RC)
    if C28_TREE.exists() or C28_TREE.is_symlink():
        raise FileExistsError(f"Refusing to overwrite C28 system tree: {C28_TREE}")
    shutil.copytree(C27_TREE, C28_TREE, symlinks=True, copy_function=hardlink_or_copy)


def replace_file(path: Path, content: bytes, mode: int) -> None:
    if path.exists() or path.is_symlink():
        path.unlink()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    os.chmod(path, mode)


def patch_init_rc() -> dict[str, object]:
    path = C28_TREE / SYSTEM_INIT
    text = path.read_text(encoding="utf-8")
    if text.count(IMPORT_C25) != 1 or text.count(IMPORT_C27) != 1 or IMPORT_C28 in text:
        raise RuntimeError("C27 C25/C27 init import baseline is not exact.")
    before_recovery_count = text.count("rebootrecovery --bad_nv")
    if before_recovery_count != 2:
        raise RuntimeError(f"Expected exactly two audited --bad_nv commands, got {before_recovery_count}.")
    text = text.replace(IMPORT_C27, IMPORT_C28)
    changed_actions: list[str] = []
    for original, marker_name, marker_value in EXPECTED_RECOVERY_ACTIONS:
        if text.count(original) != 1:
            raise RuntimeError(f"Expected one exact Recovery action block: {original!r}")
        marker = (f'  write /metadata/thyme_os4_diag/{marker_name} "{marker_value}"\n'
                  "  rebootrecovery --bad_nv")
        text = text.replace(original, original.split("\n")[0] + "\n" + marker, 1)
        changed_actions.append(marker_name)
    if text.count("rebootrecovery --bad_nv") != before_recovery_count:
        raise RuntimeError("C28 changed the number of explicit Recovery commands.")
    if text.count(IMPORT_C25) != 1 or IMPORT_C27 in text or text.count(IMPORT_C28) != 1:
        raise RuntimeError("C28 init import transition is not exact.")
    replace_file(path, (text.rstrip("\n") + "\n").encode("utf-8"),
                 stat.S_IMODE(path.stat().st_mode))
    return {"c25_import_retained": True, "c27_import_removed": True,
            "c28_import_added": True, "explicit_recovery_markers": changed_actions,
            "rebootrecovery_count_before_after": [before_recovery_count,
                                                    text.count("rebootrecovery --bad_nv")],
            "recovery_conditions_changed": False}


def install_c28_tree() -> dict[str, object]:
    init_info = patch_init_rc()
    c27_rc = C28_TREE / C27_RC
    c27_helper = C28_TREE / C27_HELPER
    require_file(c27_rc)
    require_file(c27_helper)
    c27_rc.unlink()
    c27_helper.unlink()

    rc_path = C28_TREE / C28_RC
    helper_path = C28_TREE / C28_HELPER
    if rc_path.exists() or helper_path.exists():
        raise FileExistsError("C28 diagnostic files already exist in the cloned system tree.")
    shutil.copyfile(TEMPLATE_DIR / "c28_recovery_diag.rc", rc_path)
    os.chmod(rc_path, 0o644)

    contexts_path = C28_TREE / CONTEXTS
    contexts = contexts_path.read_text(encoding="utf-8")
    old_contexts = (
        "/system/bin/c27_zygote_diag u:object_r:shell_exec:s0",
        "/system/etc/init/c27_zygote_diag\\.rc u:object_r:system_file:s0",
    )
    for entry in old_contexts:
        if contexts.count(entry) != 1:
            raise RuntimeError(f"C27 file context not found exactly once: {entry}")
        contexts = contexts.replace(entry, "")
    new_contexts = (
        "/system/bin/c28_recovery_diag u:object_r:shell_exec:s0",
        "/system/etc/init/c28_recovery_diag\\.rc u:object_r:system_file:s0",
    )
    if any(context.split()[0] in contexts for context in new_contexts):
        raise RuntimeError("C28 runtime file contexts already exist in the C27 tree.")
    replace_file(contexts_path, (contexts.rstrip("\n") + "\n" +
                                 "\n".join(new_contexts) + "\n").encode("utf-8"),
                 stat.S_IMODE(contexts_path.stat().st_mode))

    netd_rc = C28_TREE / NETD_RC
    netd_text = netd_rc.read_text(encoding="utf-8")
    if any(line.strip() in NETD_RESTART_COMMANDS for line in netd_text.splitlines()):
        raise RuntimeError("C27 netd-to-Zygote callbacks unexpectedly reappeared.")
    if netd_text.count("service netd /system/bin/netd") != 1:
        raise RuntimeError("C28 base has an unexpected number of netd service definitions.")

    policy = C28_TREE / "system/etc/selinux/plat_sepolicy.cil"
    c27_policy_hash = sha256(C27_TREE / "system/etc/selinux/plat_sepolicy.cil")
    if sha256(policy) != c27_policy_hash:
        raise RuntimeError("C28 changed the C27 platform policy; no policy changes are intended.")
    return {"init_rc": init_info, "old_diagnostic_files_removed": [C27_RC, C27_HELPER],
            "new_diagnostic_files_added": [C28_RC, C28_HELPER],
            "old_file_contexts_removed": list(old_contexts),
            "new_file_contexts_added": list(new_contexts),
            "netd_service_definitions": 1,
            "netd_to_zygote_callbacks_absent": list(NETD_RESTART_COMMANDS),
            "plat_sepolicy_sha256": c27_policy_hash, "plat_sepolicy_changed": False}


def compile_helper(stage: Path) -> tuple[Path, dict[str, object]]:
    ndk = Path("/path/to/thyme-os4-build/toolchains/android-ndk-r29/toolchains/llvm/prebuilt/linux-x86_64")
    clang = ndk / "bin/clang++"
    sysroot = ndk / "sysroot"
    source = TEMPLATE_DIR / "c28_recovery_diag.cpp"
    binary = stage / "c28_recovery_diag"
    require_file(clang)
    require_file(sysroot / "usr/include/sys/system_properties.h")
    header = (sysroot / "usr/include/sys/system_properties.h").read_text(encoding="utf-8")
    if "__system_property_wait(" not in header or "__system_property_area_serial" not in header:
        raise RuntimeError("Configured Android NDK lacks the required property wait API.")
    command = [str(clang), "--target=aarch64-linux-android35", f"--sysroot={sysroot}",
               "-O2", "-fPIE", "-pie", "-static-libstdc++", "-D_FORTIFY_SOURCE=2",
               "-Wall", "-Wextra", "-Werror", "-o", str(binary), str(source), "-llog"]
    run(command, stage / "compile_c28_recovery_diag.log")
    os.chmod(binary, 0o755)
    readelf = shutil.which("llvm-readelf") or shutil.which("readelf")
    if not readelf:
        raise FileNotFoundError("readelf is required to validate the C28 helper ELF.")
    elf = run([readelf, "-h", binary], stage / "c28_recovery_diag_elf_header.txt")
    dynamic = run([readelf, "-d", binary], stage / "c28_recovery_diag_dynamic_deps.txt")
    if "AArch64" not in elf or "PIE" not in dynamic or "liblog.so" not in dynamic or \
            "libc++_shared.so" in dynamic:
        raise RuntimeError("C28 helper ELF architecture or dynamic dependency validation failed.")
    return binary, {"bytes": binary.stat().st_size, "sha256": sha256(binary),
                    "architecture": "AArch64", "needed": ["liblog.so"],
                    "cxx_runtime": "statically linked libc++", "source_sha256": sha256(source)}


def install_helper(binary: Path) -> None:
    destination = C28_TREE / C28_HELPER
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(destination)
    shutil.copy2(binary, destination)
    os.chmod(destination, 0o755)


def inventory(root: Path) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for path in root.rglob("*"):
        if path.is_file() or path.is_symlink():
            result[path.relative_to(root).as_posix()] = path
    return result


def audit_tree_delta() -> dict[str, object]:
    before = inventory(C27_TREE)
    after = inventory(C28_TREE)
    expected_removed = {C27_RC, C27_HELPER}
    expected_added = {C28_RC, C28_HELPER}
    expected_modified = {SYSTEM_INIT, CONTEXTS}
    removed = set(before) - set(after)
    added = set(after) - set(before)
    common = set(before) & set(after)
    modified: set[str] = set()
    for relative in common:
        old, new = before[relative], after[relative]
        if old.is_symlink() or new.is_symlink():
            if not (old.is_symlink() and new.is_symlink() and
                    os.readlink(old) == os.readlink(new)):
                modified.add(relative)
            continue
        old_stat, new_stat = old.stat(), new.stat()
        if old_stat.st_dev == new_stat.st_dev and old_stat.st_ino == new_stat.st_ino:
            continue
        if old_stat.st_size != new_stat.st_size or sha256(old) != sha256(new):
            modified.add(relative)
    if removed != expected_removed or added != expected_added or modified != expected_modified:
        raise RuntimeError(f"C28 tree delta exceeded the allowlist: removed={sorted(removed)} "
                           f"added={sorted(added)} modified={sorted(modified)}")

    init_text = (C28_TREE / SYSTEM_INIT).read_text(encoding="utf-8")
    normalized = init_text.replace(IMPORT_C28, IMPORT_C27)
    for _, marker_name, marker_value in EXPECTED_RECOVERY_ACTIONS:
        marker_line = f'  write /metadata/thyme_os4_diag/{marker_name} "{marker_value}"\n'
        if normalized.count(marker_line) != 1:
            raise RuntimeError(f"Expected recovery marker missing from C28 init: {marker_name}")
        normalized = normalized.replace(marker_line, "", 1)
    if normalized != (C27_TREE / SYSTEM_INIT).read_text(encoding="utf-8"):
        raise RuntimeError("C28 init.rc contains a change beyond the approved import and markers.")
    return {"removed": sorted(removed), "added": sorted(added),
            "modified": sorted(modified), "unexpected_changes": []}


def build_system(builder, stage: Path) -> tuple[Path, dict[str, object]]:
    init_rc = C28_TREE / SYSTEM_INIT
    service_rc = C28_TREE / C28_RC
    helper = C28_TREE / C28_HELPER
    netd_rc = C28_TREE / NETD_RC
    for path in (init_rc, service_rc, helper, netd_rc):
        require_file(path)
    init_text = init_rc.read_text(encoding="utf-8")
    if init_text.count(IMPORT_C25) != 1 or IMPORT_C27 in init_text or init_text.count(IMPORT_C28) != 1:
        raise RuntimeError("C28 system init import assertions failed.")
    rc_text = service_rc.read_text(encoding="utf-8")
    required_markers = (
        "C28_POST_FS_DATA.txt", "C28_NETD_RUNNING.txt", "C28_NETD_RESTARTING.txt",
        "C28_ZYGOTE_RUNNING.txt", "C28_ZYGOTE_RESTARTING.txt",
        "C28_ZYGOTE_SECONDARY_RUNNING.txt", "C28_BOOT_COMPLETED.txt",
        "C28_SYS_POWERCTL.txt", "C28_SHUTDOWN.txt", "start c28_logcat",
        "start c28_zygote_watch", "seclabel u:r:shell:s0",
    )
    for marker in required_markers:
        if marker not in rc_text:
            raise RuntimeError(f"C28 init diagnostic configuration lacks {marker}.")
    helper_source = (TEMPLATE_DIR / "c28_recovery_diag.cpp").read_text(encoding="utf-8")
    if "-r " in helper_source or "-n " in helper_source:
        raise RuntimeError("C28 helper must not use logcat rotation options.")
    if "C28_LOGCAT_START" not in helper_source or "C28_LOGCAT_EXEC_FAILED" not in helper_source:
        raise RuntimeError("C28 helper lacks immediate START/exec-failure persistence.")
    if any(line.strip() in NETD_RESTART_COMMANDS for line in netd_rc.read_text(encoding="utf-8").splitlines()):
        raise RuntimeError("C28 netd-to-Zygote callbacks unexpectedly reappeared.")

    base_contexts = builder.C1 / "configs_retained/system/file_contexts"
    fs_config_source = builder.C1 / "configs_retained/system/fs_config"
    require_file(base_contexts)
    require_file(fs_config_source)
    contexts_path = stage / "system_file_contexts_c28"
    contexts = base_contexts.read_text(encoding="utf-8")
    context_additions = (
        "/system/system/bin/c25_bootdiag u:object_r:shell_exec:s0",
        "/system/system/etc/init/c25_bootdiag\\.rc u:object_r:system_file:s0",
        "/system/system/bin/c28_recovery_diag u:object_r:shell_exec:s0",
        "/system/system/etc/init/c28_recovery_diag\\.rc u:object_r:system_file:s0",
    )
    contexts += "\n" + "\n".join(context_additions) + "\n"
    contexts_path.write_text(contexts, encoding="utf-8", newline="\n")

    source_lines = fs_config_source.read_text(encoding="utf-8").splitlines()
    rebased: list[str] = []
    for line in source_lines:
        fields = line.split(maxsplit=1)
        if not fields or fields[0] == "/":
            rebased.append(line)
        else:
            rebased.append("system/" + fields[0].lstrip("/") +
                           (" " + fields[1] if len(fields) > 1 else ""))
    known = {line.split()[0].lstrip("/") for line in rebased
             if line.strip() and not line.lstrip().startswith("#")}
    added: list[str] = []
    for entry in sorted(C28_TREE.rglob("*"), key=lambda p: p.relative_to(C28_TREE).as_posix()):
        relative = "system/" + entry.relative_to(C28_TREE).as_posix()
        if relative in known:
            continue
        st = entry.lstat()
        added.append(f"{relative} {st.st_uid} {st.st_gid} {stat.S_IMODE(st.st_mode):04o}")
        known.add(relative)
    fs_config = stage / "system_fs_config_c28"
    fs_config.write_text("\n".join(rebased + added) + "\n", encoding="utf-8", newline="\n")

    raw = stage / "system_c28.raw.erofs"
    image = stage / "system_c28.img"
    builder.run([builder.MKFS, "-zlz4hc", "-T", "0", "-U", builder.SYSTEM_UUID,
                 "--mount-point=/system", f"--fs-config-file={fs_config}",
                 f"--file-contexts={contexts_path}", raw, C28_TREE],
                log=stage / "mkfs_system_c28.log")
    builder.run([builder.FSCK, "-d0", raw], log=stage / "fsck_system_c28.log")
    shutil.copy2(raw, image)
    builder.run(["python3", builder.AVBTOOL, "add_hashtree_footer", "--image", image,
                 "--partition_size", str(builder.SYSTEM_SIZE), "--partition_name", "system",
                 "--hash_algorithm", "sha256", "--salt", builder.SYSTEM_SALT,
                 "--algorithm", "NONE", "--do_not_generate_fec"],
                log=stage / "avb_system_c28.log")
    require_file(image, builder.SYSTEM_SIZE)

    expected_readback = {
        "/system/etc/init/hw/init.rc": (
            IMPORT_C28, "persist.vendor.radio.write.cache=1",
            "persist.vendor.ssr.restart_level=ALL_ENABLE", "persist.radio.write.cache=1",
            "C28_RECOVERY_BAD_NV_VENDOR.txt", "C28_RECOVERY_BAD_NV_RADIO.txt",
            "rebootrecovery --bad_nv"),
        "/system/etc/init/c28_recovery_diag.rc": tuple(required_markers),
        "/system/etc/init/netd.rc": ("service netd /system/bin/netd",),
        "/system/etc/selinux/plat_file_contexts": (
            "/system/bin/c28_recovery_diag", "/system/etc/init/c28_recovery_diag\\.rc"),
        "/system/bin/c28_recovery_diag": ("C28ZygoteDiag", "C28_LOGCAT_START",
                                           "C28_LOGCAT_CHILD", "C28_LOGCAT_EXEC_FAILED",
                                           "child_exit_code", "file_sync_error"),
    }
    checks: dict[str, object] = {}
    readback_dir = stage / "erofs_readback"
    for erofs_path, tokens in expected_readback.items():
        destination = readback_dir / erofs_path.lstrip("/").replace("/", "_")
        content = run_bytes([builder.DUMP, "--cat", f"--path={erofs_path}", raw], destination)
        if erofs_path.endswith("c28_recovery_diag"):
            if not content.startswith(b"\x7fELF") or hashlib.sha256(content).hexdigest().upper() != sha256(helper):
                raise RuntimeError("C28 helper raw EROFS readback is not byte-identical to the compiled ELF.")
            readback_text = content.decode("latin-1")
        else:
            readback_text = content.decode("utf-8", errors="replace")
        missing = [token for token in tokens if token not in readback_text]
        if missing:
            raise RuntimeError(f"C28 final EROFS is missing {erofs_path} markers: {missing}")
        if erofs_path == "/system/etc/init/netd.rc":
            for forbidden in NETD_RESTART_COMMANDS:
                if forbidden.encode() in content:
                    raise RuntimeError(f"C28 final EROFS unexpectedly contains {forbidden}.")
        checks[erofs_path] = {"tokens": list(tokens), "bytes": len(content),
                              "sha256": hashlib.sha256(content).hexdigest().upper()}
        if erofs_path == "/system/etc/init/hw/init.rc":
            init_readback = content.decode("utf-8", errors="strict")
            if init_readback.count("rebootrecovery --bad_nv") != 2:
                raise RuntimeError("C28 final EROFS changed the explicit bad-NV Recovery command count.")
            for marker_name in ("C28_RECOVERY_BAD_NV_VENDOR.txt", "C28_RECOVERY_BAD_NV_RADIO.txt"):
                marker_position = init_readback.find(marker_name)
                next_recovery = init_readback.find("rebootrecovery --bad_nv", marker_position)
                if marker_position < 0 or next_recovery < 0:
                    raise RuntimeError(f"C28 final EROFS does not place {marker_name} before its Recovery command.")
    if "C27".encode() in (readback_dir / "system_etc_init_c28_recovery_diag.rc").read_bytes():
        raise RuntimeError("C28 service RC unexpectedly retains a C27 service name.")

    verify_input = image.parent / "system.img"
    if verify_input.exists() or verify_input.is_symlink():
        raise FileExistsError(f"Refusing to overwrite AVB verification sibling: {verify_input}")
    verify_input.symlink_to(image)
    builder.run(["python3", builder.AVBTOOL, "verify_image", "--image", image],
                log=stage / "avb_verify_system_c28.log")
    verify_input.unlink()
    return image, {"file_context_additions": list(context_additions),
                   "new_fs_config_paths": ["system/system/bin/c28_recovery_diag",
                                            "system/system/etc/init/c28_recovery_diag.rc"],
                   "final_erofs_readback": checks,
                   "system_image_bytes": image.stat().st_size,
                   "system_image_sha256": sha256(image),
                   "netd_callbacks_retained_as_removed": True,
                   "no_selinux_cil_change": True}


def main() -> None:
    if "microsoft" not in Path("/proc/sys/kernel/osrelease").read_text().lower():
        raise RuntimeError("Run this builder inside WSL Ubuntu.")
    storage: dict[str, float] = {}
    for drive, mount in (("C", "/mnt/c"), ("D", "/mnt/d"), ("E", "/mnt/e")):
        usage = shutil.disk_usage(mount)
        free_gib = round(usage.free / (1024 ** 3), 2)
        storage[f"{drive}_free_gib"] = free_gib
        print(f"[SPACE] {drive}: free={free_gib:.2f} GiB", flush=True)
        if usage.free < 50 * (1024 ** 3):
            raise RuntimeError(f"{drive}: free space is below the 50 GiB project gate; no build started.")

    c27_manifest, inherited = load_c27_manifest()
    require_file(C27_TREE / C27_RC)
    require_file(C27_TREE / C27_HELPER)
    require_file(C27_TREE / NETD_RC)
    require_file(TEMPLATE_DIR / "c28_recovery_diag.rc")
    require_file(TEMPLATE_DIR / "c28_recovery_diag.cpp")
    if C28_DIR.exists() or C28_WORK.exists():
        raise FileExistsError("C28 output path exists; refusing to overwrite any previous attempt.")

    c23 = load_module("candidate23_builder_for_c28", ROOT / "tools/build_candidate23_sf_prime_skip.py")
    c24 = load_module("candidate24_builder_for_c28", ROOT / "tools/build_candidate24_framework_display_diag.py")
    for tool in (c23.MKFS, c23.FSCK, c23.DUMP, c23.LPMAKE, c23.SIMG2IMG, c23.LPDUMP, c23.AVBTOOL):
        require_file(tool)
    for executable in (c23.MKFS, c23.FSCK, c23.DUMP, c23.LPMAKE, c23.SIMG2IMG, c23.LPDUMP):
        if not os.access(executable, os.X_OK):
            raise PermissionError(f"Build tool is not executable: {executable}")

    C28_DIR.mkdir(parents=True, exist_ok=False)
    C28_IMAGES.mkdir(parents=True, exist_ok=False)
    C28_WORK.mkdir(parents=True, exist_ok=False)
    stage = C28_WORK / "staging"
    stage.mkdir(parents=True, exist_ok=False)
    clone_c27_tree()
    tree_changes = install_c28_tree()
    helper, helper_info = compile_helper(stage)
    install_helper(helper)
    tree_delta = audit_tree_delta()

    print("[C28] Building diagnostics on the unmodified C27 startup baseline.", flush=True)
    system_image, system_info = build_system(c23, stage)
    c23.C23_IMAGES = C27_IMAGES
    vbmeta_info = c24.rebuild_vbmeta_system_c24(c23, system_image,
                                                C28_IMAGES / "vbmeta_system.img", stage)
    c23.C23_IMAGES = C28_IMAGES
    super_image, logical_hashes = c23.build_super(system_image, stage)
    if logical_hashes != c27_manifest.get("logical_input_hashes", {}):
        raise RuntimeError("A non-system logical partition source differs from the C27 manifest.")
    for name in SMALL_INHERITED:
        shutil.copy2(C27_IMAGES / name, C28_IMAGES / name)
        if sha256(C28_IMAGES / name) != inherited[name]["sha256"]:
            raise RuntimeError(f"Inherited C27 image changed while copying: {name}")

    image_entries: dict[str, dict[str, object]] = {}
    for name in IMAGE_NAMES:
        path = C28_IMAGES / name
        require_file(path)
        image_entries[name] = {"bytes": path.stat().st_size, "sha256": sha256(path)}
    manifest = {
        "candidate": CANDIDATE,
        "base": BASE,
        "changes": [
            "Replaces only the C27 diagnostic helper/RC with C28 diagnostics; C27 system behavior and netd callback removal remain unchanged.",
            "Adds init built-in metadata markers for post-fs-data, netd/zygote/bootanim/surfaceflinger service transitions, boot-complete, sys.powerctl, shutdown, and immediately before the two existing --bad_nv Recovery actions. Their conditions and commands are unchanged.",
            "Fixes the C27 helper's first-write gap: logger status START is written and fsync'd immediately after status open, before statvfs/pipe/fork; helper PID and child PID are persisted before the child launch gate opens; exec errno is reported through a dedicated pipe; wait status validity, exit code, signal, stderr and stop reason are captured.",
            "Uses one logcat output file, existing shell SELinux domain and the C26-proven -b all buffer selection; no -r/-n rotation; 8-minute and metadata-aware 24 MiB caps with periodic file sync.",
        ],
        "evidence_basis": [
            "C27 init's post-fs-data marker was present, but four helper-created diagnostic files were zero bytes. C27 source created the logger status file before statvfs/plan completion and wrote START only after those steps; the watcher also opened its event/tail files and sampled properties before its first START record.",
            "C26's shell-domain logcat invocation produced about 8.56 MB in metadata, proving that logd access and the target metadata path worked in that run. C27 did not preserve enough status to distinguish pre-write termination, write/fsync failure, or abrupt reset; this remains unknown.",
            "Final C27 init tree has exactly two explicit rebootrecovery --bad_nv actions in system/etc/init/hw/init.rc, gated by the vendor-radio/SSR and radio write-cache properties. C27 did not save their runtime values. Other scanned RC reboot_on_failure paths request normal reboot or bootloader, not an explicit Recovery target. The trigger cause remains unconfirmed.",
        ],
        "diagnostic_limits": [
            "Init write markers are separate files but init's built-in write does not expose an fsync result; marker absence cannot by itself distinguish an untriggered action from a very early interruption.",
            "C28 has not been run on the device. Its init markers, helper launch, logd access, persistence, and ability to capture sys.powerctl remain unverified until the next authorized startup.",
            "The targeted K40 system cache does not include system/etc/init/hw/init.rc. No K40 statement is made about these two triggers; C28 does not alter them.",
        ],
        "recovery_path_scan": {
            "source": "work/reports/20260929_C28_RECOVERY_ZYGOTE_DIAGNOSTIC/c27_recovery_init_scan.json",
            "direct_recovery_actions": [
                {"rc": "/system/etc/init/hw/init.rc",
                 "trigger": "persist.vendor.radio.write.cache=1 && persist.vendor.ssr.restart_level=ALL_ENABLE",
                 "command": "rebootrecovery --bad_nv"},
                {"rc": "/system/etc/init/hw/init.rc", "trigger": "persist.radio.write.cache=1",
                 "command": "rebootrecovery --bad_nv"},
            ],
            "C27_runtime_trigger_values": "not recorded",
            "root_cause": "unconfirmed; C28 adds pre-action markers without changing either condition",
        },
        "tree_changes": tree_changes,
        "tree_delta": tree_delta,
        "runtime_helper": helper_info,
        "system_build": system_info,
        "vbmeta_system_update": vbmeta_info,
        "logical_input_hashes": logical_hashes,
        "flash_scope_prepared": ["super", "vbmeta_system_a"],
        "images": image_entries,
        "c27_baseline": {"checked_images": inherited,
                         "logical_input_hashes": c27_manifest.get("logical_input_hashes", {})},
        "host_storage_gate": storage,
    }
    manifest_path = C28_IMAGES / "BUILD_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")

    C28_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = C28_DIR / "C28_RECOVERY_ZYGOTE_DIAGNOSTIC_BUILD_REPORT.md"
    report = (
        "# Candidate 28 Recovery/Zygote 可靠启动留证构建报告\n\n"
        "## C27 诊断文件为空的结论\n\n"
        "C26 的 `c26_zygote_diag --logcat` 在 `shell` SELinux 域直接 exec `/system/bin/logcat -b all -v threadtime,monotonic -f <file> -r 1024 -n 3`，并在同一 metadata 路径产生约 8.56 MB 日志。C27 仍使用 `shell` 用户/组和 `u:r:shell:s0`，也能创建相同 metadata 目录下的文件；其平台策略没有变化，因此现有材料不支持将零字节归因于 shell/logd/metadata 权限缺失。\n\n"
        "C27 将 logcat 放进 helper 的子进程管道，并由父进程转写单一文件。源代码中 status 文件在 START 前已经创建；START 要等 statvfs、容量计划和字符串构造后才写。watcher 的 events/tails 文件也在 START 写入前创建，并先打开多个文件、读取属性。C27 最终只有零字节文件，无法知道是早期退出、写入/fsync 出错还是突然重启。故‘为什么零字节’只能定位到源码留证窗口不足，不能从这次设备证据确定实际发生了哪种运行时情况。\n\n"
        "C28 在 status open 后立即用栈缓冲写入 `C28_LOGCAT_START` 并 fsync，之后才执行 statvfs、建立 pipes 或 fork；父进程先持久化 child PID，再放行 child；exec 失败通过专用 errno pipe 立即记录 `C28_LOGCAT_EXEC_FAILED`。logcat 采用 C26 已工作的 `-b all`，取消 `-r/-n`，维持单文件、8 分钟和最多 24 MiB，并每 1 秒或 128 KiB 对捕获文件 fdatasync。\n\n"
        "## C27 Recovery 路径\n\n"
        "对最终 C27 的 system、system_ext、product、vendor、odm、mi_ext init RC 进行有界扫描。显式 `rebootrecovery` 只发现 system init 的两条 `--bad_nv` action：`persist.vendor.radio.write.cache=1 && persist.vendor.ssr.restart_level=ALL_ENABLE`，以及 `persist.radio.write.cache=1`。其他 `reboot_on_failure` 项请求普通 reboot 或 bootloader；它们不能直接证明进入 PixelOS Recovery。C27 未保存上述属性值，也未保存 `sys.powerctl`，所以 Recovery 根因仍未确认。C28 在两条原始命令前分别写独立 marker，并增加 `sys.powerctl` 和 `on shutdown` marker；不会改变条件或重启命令。\n\n"
        "C28 init RC 另对 post-fs-data、netd 与两个 Zygote 状态、bootanim/surfaceflinger、诊断服务、`sys.boot_completed=1` 写入彼此独立的文件。C27 删除的 netd→Zygote `onrestart` 回调继续保持移除；netd 的兼容性检查/失败行为没有改变。没有改动 ART、Zygote、GPU、HWC、Framework、SELinux CIL、fstab、加密、内核或硬件适配。\n\n"
        "## K40 定点对照\n\n"
        "已检查的 K40 成功包缓存中只有此前图形相关的部分 system 文件，没有 `system/etc/init/hw/init.rc`。本次没有为了读取一份 RC 展开整套成功包，因此不声称 K40 移植保留或删除了 `--bad_nv` 条件。C28 的变更是观测现有供体触发条件，不复制 K40 固件或设备专属文件。\n\n"
        "## 构建与验证\n\n"
        f"C28 基于 C27 的 system tree 硬链接克隆；静态树差异 allowlist：`{', '.join(tree_delta['modified'])}`，移除 C27 helper/RC 并加入 C28 helper/RC。C27 netd callback 状态、其余非系统 LP 输入及 boot/vendor_boot/dtbo/vbmeta 继承。最终 EROFS fsck、marker/策略路径 readback、helper 原始 ELF 字节一致性、system AVB hashtree、vbmeta_system descriptor 更新和 LP 布局验证见 BUILD_MANIFEST。\n\n"
        "仅允许的刷写范围：`super`、`vbmeta_system_a`。构建器不访问设备。本报告不代表 C28 已经刷写或真机验证。\n\n"
        "## 镜像 SHA-256\n\n"
        "| 镜像 | 字节 | SHA-256 |\n|---|---:|---|\n" +
        "\n".join(f"| `{name}` | {entry['bytes']} | `{entry['sha256']}` |"
                  for name, entry in image_entries.items()) + "\n"
    )
    report_path.write_text(report, encoding="utf-8", newline="\n")
    print(f"[C28] Build complete: {C28_IMAGES}", flush=True)
    print(f"[C28] Manifest: {manifest_path}", flush=True)


if __name__ == "__main__":
    main()
