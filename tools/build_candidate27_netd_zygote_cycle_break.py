#!/usr/bin/env python3
"""Build C27 on C25 with bounded, persistent Zygote/logcat first-exit capture."""

from __future__ import annotations

import hashlib
import errno
import argparse
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
C26_WORK = Path("/path/to/thyme-os4-build/c26_zygote_diag_20260929_run2")
C26_TREE = C26_WORK / "system_tree"
C27_WORK = Path("/path/to/thyme-os4-build/c27_netd_zygote_cycle_break_20260929_run1")
C27_TREE = C27_WORK / "system_tree"
C26_DIR = ROOT / "work/stage_c26_zygote_diag_20260929_run2"
C26_IMAGES = C26_DIR / "images"
C27_DIR = ROOT / "work/stage_c27_netd_zygote_cycle_break_20260929_run1"
C27_IMAGES = C27_DIR / "images"
TEMPLATE_DIR = ROOT / "tools/candidate27_netd_zygote_diag"
IMAGE_NAMES = ("boot.img", "vendor_boot.img", "dtbo.img", "vbmeta.img",
               "vbmeta_system.img", "super.img")
SMALL_INHERITED = ("boot.img", "vendor_boot.img", "dtbo.img", "vbmeta.img")
CANDIDATE = "Candidate 27 netd-to-Zygote restart-cycle fix and diagnostic"
BASE = "Candidate 26 Zygote first-exit diagnostic"
IMPORT_C25 = "import /system/etc/init/c25_bootdiag.rc"
IMPORT_C26 = "import /system/etc/init/c26_zygote_diag.rc"
IMPORT_C27 = "import /system/etc/init/c27_zygote_diag.rc"
EXPECTED_C26_NETD_RC_SHA256 = "51039198C9EC69111B1F7F1C8257AE12EE0A677C14599A87416C5B24B112948B"
NETD_RESTART_COMMANDS = ("onrestart restart zygote", "onrestart restart zygote_secondary")


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load builder module: {path}")
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


def verify_c26_base() -> tuple[dict[str, object], dict[str, dict[str, object]]]:
    manifest_path = C26_IMAGES / "BUILD_MANIFEST.json"
    require_file(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("candidate") != BASE:
        raise RuntimeError("C26 manifest does not identify the expected diagnostic baseline.")
    if set(manifest.get("images", {})) != set(IMAGE_NAMES):
        raise RuntimeError("C26 manifest does not contain the six expected images.")
    if manifest.get("flash_scope_prepared") != ["super", "vbmeta_system_a"]:
        raise RuntimeError("C26 manifest has an unexpected flash scope.")
    checked: dict[str, dict[str, object]] = {}
    for name in SMALL_INHERITED + ("vbmeta_system.img",):
        path = C26_IMAGES / name
        expected = manifest["images"][name]
        require_file(path, int(expected["bytes"]))
        actual = sha256(path)
        if actual != str(expected["sha256"]).upper():
            raise RuntimeError(f"C26 inherited image differs from its manifest: {name}")
        checked[name] = {"bytes": path.stat().st_size, "sha256": actual}
    require_file(C26_IMAGES / "super.img", int(manifest["images"]["super.img"]["bytes"]))
    return manifest, checked


def clone_c26_tree() -> None:
    require_file(C26_TREE / "system/etc/init/hw/init.rc")
    require_file(C26_TREE / "system/etc/init/netd.rc")
    for path in (C27_TREE,):
        if path.exists() or path.is_symlink():
            raise FileExistsError(f"Refusing to overwrite existing C27 tree: {path}")
    def link_or_copy(source: str, destination: str) -> str:
        try:
            os.link(source, destination, follow_symlinks=False)
        except OSError as exc:
            if exc.errno not in (errno.EXDEV, errno.EPERM, errno.EACCES, errno.EOPNOTSUPP):
                raise
            shutil.copy2(source, destination, follow_symlinks=False)
        return destination

    shutil.copytree(C26_TREE, C27_TREE, symlinks=True, copy_function=link_or_copy)


def replace_file(path: Path, content: bytes, mode: int) -> None:
    if path.exists() or path.is_symlink():
        path.unlink()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    os.chmod(path, mode)


def install_c27_tree() -> dict[str, object]:
    init_rc = C27_TREE / "system/etc/init/hw/init.rc"
    init_text = init_rc.read_text(encoding="utf-8")
    if init_text.count(IMPORT_C25) != 1 or init_text.count(IMPORT_C26) != 1 or IMPORT_C27 in init_text:
        raise RuntimeError("C25/C26 init imports are not the expected C27 baseline.")
    init_text = init_text.replace(IMPORT_C26, IMPORT_C27)
    replace_file(init_rc, (init_text.rstrip("\n") + "\n").encode(),
                 stat.S_IMODE(init_rc.stat().st_mode))

    netd_rc = C27_TREE / "system/etc/init/netd.rc"
    netd_original_hash = sha256(netd_rc)
    if netd_original_hash != EXPECTED_C26_NETD_RC_SHA256:
        raise RuntimeError(f"C26 netd.rc changed from the audited input: {netd_original_hash}")
    netd_lines = netd_rc.read_text(encoding="utf-8").splitlines()
    removed: list[str] = []
    netd_lines_out: list[str] = []
    for line in netd_lines:
        if line.strip() in NETD_RESTART_COMMANDS:
            removed.append(line.strip())
        else:
            netd_lines_out.append(line)
    if sorted(removed) != sorted(NETD_RESTART_COMMANDS):
        raise RuntimeError(f"Expected exactly the two audited netd onrestart commands, found: {removed}")
    replace_file(netd_rc, ("\n".join(netd_lines_out) + "\n").encode(),
                 stat.S_IMODE(netd_rc.stat().st_mode))

    c26_rc = C27_TREE / "system/etc/init/c26_zygote_diag.rc"
    c26_helper = C27_TREE / "system/bin/c26_zygote_diag"
    require_file(c26_rc)
    require_file(c26_helper)
    c26_rc.unlink()
    c26_helper.unlink()

    rc_path = C27_TREE / "system/etc/init/c27_zygote_diag.rc"
    helper_path = C27_TREE / "system/bin/c27_zygote_diag"
    if rc_path.exists() or helper_path.exists():
        raise FileExistsError("C27 diagnostic files already exist in the cloned tree.")
    shutil.copyfile(TEMPLATE_DIR / "c27_zygote_diag.rc", rc_path)
    os.chmod(rc_path, 0o644)

    contexts_path = C27_TREE / "system/etc/selinux/plat_file_contexts"
    contexts = contexts_path.read_text(encoding="utf-8")
    old_contexts = (
        "/system/bin/c26_zygote_diag u:object_r:shell_exec:s0",
        "/system/etc/init/c26_zygote_diag\\.rc u:object_r:system_file:s0",
    )
    for old in old_contexts:
        if contexts.count(old) != 1:
            raise RuntimeError(f"C26 runtime context not found exactly once: {old}")
        contexts = contexts.replace(old, "")
    additions = (
        "/system/bin/c27_zygote_diag u:object_r:shell_exec:s0",
        "/system/etc/init/c27_zygote_diag\\.rc u:object_r:system_file:s0",
    )
    if any(entry.split()[0] in contexts for entry in additions):
        raise RuntimeError("C27 runtime file contexts already exist in the C26 tree.")
    replace_file(contexts_path, (contexts.rstrip("\n") + "\n" + "\n".join(additions) + "\n").encode(),
                 stat.S_IMODE(contexts_path.stat().st_mode))

    policy = C27_TREE / "system/etc/selinux/plat_sepolicy.cil"
    mapping_hash = C27_TREE / "system/etc/selinux/plat_sepolicy_and_mapping.sha256"
    return {
        "init_import_added": IMPORT_C27,
        "init_import_retained": IMPORT_C25,
        "init_import_removed": IMPORT_C26,
        "runtime_file_context_additions": list(additions),
        "runtime_file_contexts_removed": list(old_contexts),
        "netd_rc_before_sha256": netd_original_hash,
        "netd_rc_after_sha256": sha256(netd_rc),
        "netd_onrestart_commands_removed": removed,
        "plat_sepolicy_sha256": sha256(policy),
        "plat_sepolicy_and_mapping_sha256_file": mapping_hash.read_text(encoding="ascii").strip(),
        "cil_changed": False,
    }


def compile_helper(stage: Path) -> tuple[Path, dict[str, object]]:
    ndk = Path("/path/to/thyme-os4-build/toolchains/android-ndk-r29/toolchains/llvm/prebuilt/linux-x86_64")
    clang = ndk / "bin/clang++"
    sysroot = ndk / "sysroot"
    source = TEMPLATE_DIR / "c27_zygote_diag.cpp"
    binary = stage / "c27_zygote_diag"
    require_file(clang)
    require_file(sysroot / "usr/include/sys/system_properties.h")
    header = (sysroot / "usr/include/sys/system_properties.h").read_text(encoding="utf-8")
    if "__system_property_wait(" not in header or "__system_property_area_serial" not in header:
        raise RuntimeError("The configured Android NDK does not expose the property wait API.")
    command = [str(clang), "--target=aarch64-linux-android35", f"--sysroot={sysroot}",
               "-O2", "-fPIE", "-pie", "-static-libstdc++", "-D_FORTIFY_SOURCE=2",
               "-Wall", "-Wextra", "-Werror", "-o", str(binary), str(source), "-llog"]
    run(command, stage / "compile_c27_zygote_diag.log")
    os.chmod(binary, 0o755)
    readelf = shutil.which("llvm-readelf") or shutil.which("readelf")
    if not readelf:
        raise FileNotFoundError("readelf is required to validate the C27 helper ELF.")
    elf = run([readelf, "-h", binary], stage / "c27_zygote_diag_elf_header.txt")
    dynamic = run([readelf, "-d", binary], stage / "c27_zygote_diag_dynamic_deps.txt")
    if "AArch64" not in elf or "PIE" not in dynamic or "liblog.so" not in dynamic or "libc++_shared.so" in dynamic:
        raise RuntimeError("C27 helper ELF architecture or dynamic dependency check failed.")
    return binary, {"bytes": binary.stat().st_size, "sha256": sha256(binary),
                    "architecture": "AArch64", "needed": ["liblog.so"],
                    "cxx_runtime": "statically linked libc++",
                    "source_sha256": sha256(source)}


def install_helper(binary: Path) -> None:
    dest = C27_TREE / "system/bin/c27_zygote_diag"
    if dest.exists() or dest.is_symlink():
        raise FileExistsError(dest)
    shutil.copy2(binary, dest)
    os.chmod(dest, 0o755)


def build_system(builder, stage: Path) -> tuple[Path, dict[str, object]]:
    init_rc = C27_TREE / "system/etc/init/hw/init.rc"
    service_rc = C27_TREE / "system/etc/init/c27_zygote_diag.rc"
    helper = C27_TREE / "system/bin/c27_zygote_diag"
    netd_rc = C27_TREE / "system/etc/init/netd.rc"
    for path in (init_rc, service_rc, helper, netd_rc):
        require_file(path)
    init_text = init_rc.read_text(encoding="utf-8")
    if init_text.count(IMPORT_C25) != 1 or IMPORT_C26 in init_text or init_text.count(IMPORT_C27) != 1:
        raise RuntimeError("C25/C26/C27 init import transition is not correct.")
    netd_text = netd_rc.read_text(encoding="utf-8")
    if any(line.strip() in NETD_RESTART_COMMANDS for line in netd_text.splitlines()):
        raise RuntimeError("C27 netd.rc still contains a removed netd-to-Zygote restart command.")

    file_contexts = builder.C1 / "configs_retained/system/file_contexts"
    fs_config_source = builder.C1 / "configs_retained/system/fs_config"
    require_file(file_contexts)
    require_file(fs_config_source)
    file_contexts_c27 = stage / "system_file_contexts_c27"
    contexts = file_contexts.read_text(encoding="utf-8")
    context_additions = (
        "/system/system/bin/c25_bootdiag u:object_r:shell_exec:s0",
        "/system/system/etc/init/c25_bootdiag\\.rc u:object_r:system_file:s0",
        "/system/system/bin/c27_zygote_diag u:object_r:shell_exec:s0",
        "/system/system/etc/init/c27_zygote_diag\\.rc u:object_r:system_file:s0",
    )
    contexts += "\n" + "\n".join(context_additions) + "\n"
    file_contexts_c27.write_text(contexts, encoding="utf-8", newline="\n")

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
    for entry in sorted(C27_TREE.rglob("*"), key=lambda p: p.relative_to(C27_TREE).as_posix()):
        relative = "system/" + entry.relative_to(C27_TREE).as_posix()
        if relative in known:
            continue
        st = entry.lstat()
        added.append(f"{relative} {st.st_uid} {st.st_gid} {stat.S_IMODE(st.st_mode):04o}")
        known.add(relative)
    fs_config = stage / "system_fs_config_c27"
    fs_config.write_text("\n".join(rebased + added) + "\n", encoding="utf-8", newline="\n")

    raw = stage / "system_c27.raw.erofs"
    image = stage / "system_c27.img"
    builder.run([builder.MKFS, "-zlz4hc", "-T", "0", "-U", builder.SYSTEM_UUID,
                 "--mount-point=/system", f"--fs-config-file={fs_config}",
                 f"--file-contexts={file_contexts_c27}", raw, C27_TREE],
                log=stage / "mkfs_system_c27.log")
    builder.run([builder.FSCK, "-d0", raw], log=stage / "fsck_system_c27.log")
    shutil.copy2(raw, image)
    builder.run(["python3", builder.AVBTOOL, "add_hashtree_footer", "--image", image,
                 "--partition_size", str(builder.SYSTEM_SIZE), "--partition_name", "system",
                 "--hash_algorithm", "sha256", "--salt", builder.SYSTEM_SALT,
                 "--algorithm", "NONE", "--do_not_generate_fec"], log=stage / "avb_system_c27.log")
    require_file(image, builder.SYSTEM_SIZE)

    checks: dict[str, object] = {}
    expectations = (
        ("/system/etc/init/hw/init.rc", IMPORT_C27),
        ("/system/etc/init/netd.rc", "service netd /system/bin/netd"),
        ("/system/etc/init/c27_zygote_diag.rc", "/system/bin/c27_zygote_diag --logcat"),
        ("/system/etc/init/c27_zygote_diag.rc", "start c27_logcat"),
        ("/system/etc/init/c27_zygote_diag.rc", "start c27_zygote_watch"),
        ("/system/etc/init/c27_zygote_diag.rc", "seclabel u:r:shell:s0"),
        ("/system/bin/c27_zygote_diag", "C27ZygoteDiag"),
        ("/system/bin/c27_zygote_diag", "C27_LOGCAT_START"),
        ("/system/bin/c27_zygote_diag", "C27_LOGCAT_END"),
        ("/system/bin/c27_zygote_diag", "byte_cap"),
        ("/system/etc/selinux/plat_file_contexts", "/metadata/thyme_os4_diag"),
    )
    for erofs_path, token in expectations:
        output_path = stage / ("dump_" + erofs_path.strip("/").replace("/", "_") + "_c27.bin")
        builder.run([builder.DUMP, "--cat", f"--path={erofs_path}", raw], log=output_path)
        content = output_path.read_bytes()
        if token.encode() not in content:
            raise RuntimeError(f"C27 final EROFS is missing expected content: {erofs_path}: {token}")
        checks[erofs_path] = {"contains": token, "bytes": len(content)}
    netd_dump = stage / "dump_system_etc_init_netd_rc_c27_negative.bin"
    builder.run([builder.DUMP, "--cat", "--path=/system/etc/init/netd.rc", raw], log=netd_dump)
    netd_final = netd_dump.read_bytes()
    for forbidden in NETD_RESTART_COMMANDS:
        if forbidden.encode() in netd_final:
            raise RuntimeError(f"C27 final EROFS unexpectedly retains {forbidden} in netd.rc.")
    checks["/system/etc/init/netd.rc_removed_commands"] = {
        "absent": list(NETD_RESTART_COMMANDS), "bytes": len(netd_final)}
    helper_dump = stage / "dump_system_bin_c27_helper_negative.bin"
    builder.run([builder.DUMP, "--cat", "--path=/system/bin/c27_zygote_diag", raw], log=helper_dump)
    if b"init.svc_debug_pid.zygote" in helper_dump.read_bytes():
        raise RuntimeError("C27 final helper unexpectedly reads denied init.svc_debug_pid properties.")

    if IMPORT_C25.encode() not in (C27_TREE / "system/etc/init/hw/init.rc").read_bytes():
        raise RuntimeError("C27 failed to retain the C25 init import.")
    build_prop = (C27_TREE / "system/build.prop").read_bytes()
    for required in (b"service.sf.prime_shader_cache=0", b"persist.graphics.egl=angle"):
        if required not in build_prop:
            raise RuntimeError(f"C27 failed to retain expected inherited property: {required.decode()}")
    policy_hash = sha256(C27_TREE / "system/etc/selinux/plat_sepolicy.cil")
    expected_policy_hash = sha256(C26_TREE / "system/etc/selinux/plat_sepolicy.cil")
    if policy_hash != expected_policy_hash:
        raise RuntimeError("C27 changed C26 platform policy; no policy change is intended.")

    verify_input = image.parent / "system.img"
    if verify_input.exists() or verify_input.is_symlink():
        raise FileExistsError(f"Refusing to overwrite AVB verification sibling: {verify_input}")
    verify_input.symlink_to(image)
    builder.run(["python3", builder.AVBTOOL, "verify_image", "--image", image],
                log=stage / "avb_verify_system_c27.log")
    verify_input.unlink()

    return image, {"file_context_additions": list(context_additions),
                   "new_fs_config_paths": ["system/system/bin/c27_zygote_diag",
                                            "system/system/etc/init/c27_zygote_diag.rc"],
                   "final_erofs_readback": checks,
                   "system_image_bytes": image.stat().st_size,
                   "system_image_sha256": sha256(image),
                   "plat_sepolicy_sha256": policy_hash,
                    "plat_cil_unchanged_from_c26": True}


def main() -> None:
    if "microsoft" not in Path("/proc/sys/kernel/osrelease").read_text().lower():
        raise RuntimeError("Run this builder inside WSL Ubuntu.")

    storage = {}
    for drive, mount in (("C", "/mnt/c"), ("D", "/mnt/d"), ("E", "/mnt/e")):
        usage = shutil.disk_usage(mount)
        free_gib = round(usage.free / (1024 ** 3), 2)
        storage[f"{drive}_free_gib"] = free_gib
        print(f"[SPACE] {drive}: free={free_gib:.2f} GiB", flush=True)
        if usage.free < 50 * (1024 ** 3):
            raise RuntimeError(f"{drive}: free space is below the 50 GiB project gate; no build started.")

    c26_manifest, inherited = verify_c26_base()
    require_file(C26_TREE / "system/etc/init/c26_zygote_diag.rc")
    require_file(C26_TREE / "system/bin/c26_zygote_diag")
    require_file(C26_TREE / "system/etc/init/netd.rc")
    c23 = load_module("candidate23_builder_for_c27", ROOT / "tools/build_candidate23_sf_prime_skip.py")
    c24 = load_module("candidate24_builder_for_c27", ROOT / "tools/build_candidate24_framework_display_diag.py")
    for tool in (c23.MKFS, c23.FSCK, c23.DUMP, c23.LPMAKE,
                 c23.SIMG2IMG, c23.LPDUMP, c23.AVBTOOL):
        require_file(tool)
    for executable in (c23.MKFS, c23.FSCK, c23.DUMP, c23.LPMAKE, c23.SIMG2IMG, c23.LPDUMP):
        if not os.access(executable, os.X_OK):
            raise PermissionError(f"Build tool is not executable: {executable}")
    if C27_DIR.exists() or C27_WORK.exists():
        raise FileExistsError("C27 output already exists; refusing to overwrite a prior build attempt.")
    C27_DIR.mkdir(parents=True, exist_ok=False)
    C27_IMAGES.mkdir(parents=True, exist_ok=False)
    C27_WORK.mkdir(parents=True, exist_ok=False)
    stage = C27_WORK / "staging"
    stage.mkdir(parents=True, exist_ok=False)
    clone_c26_tree()
    policy_info = install_c27_tree()
    helper, helper_info = compile_helper(stage)
    install_helper(helper)

    print("[C27] Building an evidence-based netd/Zygote cycle break and bounded diagnostics on C26.", flush=True)
    system_image, system_info = build_system(c23, stage)
    c24.C23_IMAGES = C26_IMAGES
    vbmeta_info = c24.rebuild_vbmeta_system_c24(c23, system_image,
                                                C27_IMAGES / "vbmeta_system.img", stage)
    c23.C23_IMAGES = C27_IMAGES
    super_image, logical_hashes = c23.build_super(system_image, stage)
    if logical_hashes != c26_manifest.get("logical_input_hashes", {}):
        raise RuntimeError("A non-system logical partition input differs from the C26 manifest.")
    for name in SMALL_INHERITED:
        shutil.copy2(C26_IMAGES / name, C27_IMAGES / name)
        if sha256(C27_IMAGES / name) != inherited[name]["sha256"]:
            raise RuntimeError(f"Inherited C26 image changed while copying: {name}")

    entries = {}
    for name in IMAGE_NAMES:
        path = C27_IMAGES / name
        require_file(path)
        entries[name] = {"bytes": path.stat().st_size, "sha256": sha256(path)}
    manifest = {
        "candidate": CANDIDATE,
        "base": BASE,
        "changes": [
            "Based on C26 and removes only netd.rc callbacks that restarted both Zygote services when netd was restarted; netd itself retains its existing crash/restart behavior and compatibility gate.",
            "Replaces the C26 rotating logcat logger with a single-file, 8-minute, byte-capped logger supervised by the native helper; status records child exit, signal, stderr, elapsed time, output size, cap, and stop reason.",
            "The helper starts at post-fs-data, watches Zygote/netd service state, captures bounded crash/system/main logcat tails, and records the existing C25 persistent sampler state without reading denied init.svc_debug_pid properties.",
            "Uses existing shell labels and policy; no SELinux CIL, kernel, fstab, data-encryption, graphics, or hardware partition changes.",
        ],
        "evidence_basis": [
            "C26 netd PID 1046 aborts at monotonic 14.409s because the 25Q2+ tethering code rejects Linux 4.19; within 100ms init sends SIGKILL to Zygote PID 1060 and secondary PID 1061 process groups, followed by both service state transitions to stopping. C26 netd.rc contains the matching onrestart restart zygote and onrestart restart zygote_secondary callbacks.",
            "The saved trace proves init issued SIGKILL after netd restart. It does not contain Zygote waitpid status, so the precise observed exit status remains unknown; no Zygote fatal/tombstone was captured.",
            "K40 OS4.0.0.8 package and C26 share the same netd binary and netd.rc, SDK37/vendor API30; the package embeds a 4.19.325 kernel string, but no runtime uname or K40 netd log proves that kernel was running. The static/runtime discrepancy remains unresolved.",
        ],
        "diagnostic_limits": [
            "The logcat child is limited to 8 minutes and available metadata space minus a 12 MiB reserve (8 MiB for the inherited C25 sampler, 1.5 MiB for C27 event/tail files, and 2.5 MiB headroom), capped at 24 MiB; the watcher and tail files also have fixed caps.",
            "The watcher uses the existing shell SELinux domain/policy and does not read init.svc_debug_pid.*. Helper and logger exit status are persisted; Android tombstones are not directly read because standalone cannot decrypt /data.",
            "C27 is an experiment: netd is still expected to abort on the 4.19 kernel. Removing the reverse restart callbacks tests whether Zygote/system_server can progress independently; networking may remain unavailable.",
        ],
        "k40_runtime_comparison": {
            "report": "work/reports/20260929_C27_NETD_ZYGOTE_CYCLE_BREAK/runtime_comparison.txt",
            "result": "K40's packaged netd binary and netd.rc match C26, and its package includes a Linux 4.19.325 kernel string. Its successful runtime under this netd compatibility gate is not proven from available runtime logs. The same netd.rc callback therefore establishes a relevant mechanism but not evidence that K40 removed it.",
        },
        "runtime_helper": helper_info,
        "policy": policy_info,
        "system_build": system_info,
        "vbmeta_system_update": vbmeta_info,
        "logical_input_hashes": logical_hashes,
        "flash_scope_prepared": ["super", "vbmeta_system_a"],
        "images": entries,
        "c26_baseline": {"checked_images": inherited,
                         "logical_input_hashes": c26_manifest.get("logical_input_hashes", {})},
        "host_storage_gate": storage,
    }
    manifest_path = C27_IMAGES / "BUILD_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    report = C27_DIR / "C27_ZYGOTE_DIAGNOSTIC_BUILD_REPORT.md"
    report.write_text(
        "# Candidate 27 netd/Zygote 重启耦合实验与构建报告\n\n"
        "## C26 根因证据\n\n"
        "C26 中 netd（PID 1046）因 25Q2+ 对 Linux <5.4 的检查 SIGABRT。约 94 ms 后 init 向首次 Zygote（PID 1060）进程组发送 SIGKILL，并对 secondary Zygote（PID 1061）做同样处理。随后两个服务状态从 running 转 stopping，netd 转 restarting。实际 C26 `netd.rc` 含 `onrestart restart zygote` 和 `onrestart restart zygote_secondary`，与顺序一致。保存日志能证明 init 发出 SIGKILL，但没有 waitpid status，故 Zygote 最终 wait status/exit code 未知；没有捕获归属 Zygote 的 fatal 或 tombstone。\n\n"
        "## C27 改动\n\n"
        "以 C26 为基线，只从 netd.rc 移除上述两条反向重启回调；netd 的 Android 25Q2/Linux 4.19 检查、崩溃与自身重启行为保留。因此网络服务可能仍不可用。此项修复/实验直接针对 C26 已观察到的 init SIGKILL 链，目标是让 Zygote 和 system_server 不再因 netd 重启被 init 一并杀掉。\n\n"
        "同时用有界 logger 替代 C26 旋转式 logcat：post-fs-data 后启动，捕获 crash/main/system/events，单一 metadata 文件，无轮转/删除；最长 8 分钟，容量为可用空间扣 12 MiB 后最多 24 MiB（为 C25 采样最多 8 MiB、C27 event/tail 文件约 1.5 MiB 和额外余量预留），状态文件记录真实子进程退出码、信号、stderr、时长、字节数和停止原因。Zygote watcher 仍使用现有 shell 域和 SELinux policy，不读取此前触发 AVC 的 `init.svc_debug_pid.zygote*`。\n\n"
        "## K40 对照及边界\n\n"
        "指定的 K40 OS4.0.0.8 包中 netd 二进制与 netd.rc 均与 C26 相同；包内 boot kernel 字符串是 Linux 4.19.325，但这不是 K40 正在运行时的 uname。K40 成功运行与静态 25Q2 内核门槛之间仍有未解决差异，不用推测填补。现有证据不足以把该回调删除归因于 K40 移植做法；C27 是基于 C26 的直接事件链做隔离验证。\n\n"
        "## 构建/设备边界\n\n"
        "若构建成功，只重建 system、配套 vbmeta_system 和 super，继承 boot、vendor_boot、dtbo、vbmeta。预定刷写范围为 `super` 与 `vbmeta_system_a`。本任务不启动 C26/C27，不运行 set_active，不刷写或改 A/B 元数据；首次启动前需另行取得 A 槽预算恢复授权。\n",
        encoding="utf-8", newline="\n")
    print(f"[C27] Build complete: {C27_IMAGES}", flush=True)
    print(f"[C27] Manifest: {manifest_path}", flush=True)


if __name__ == "__main__":
    main()
