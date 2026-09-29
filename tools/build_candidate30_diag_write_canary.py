#!/usr/bin/env python3
"""Build C30 on C29 with an isolated diagnostic domain and write canaries."""

from __future__ import annotations

import hashlib
import importlib.util
import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
C29_STAGE = ROOT / "work/stage_c29_pid1_zygote_diag_20260929_run6"
C29_IMAGES = C29_STAGE / "images"
C29_WORK = Path("/root/10s_os4_build/c29_pid1_zygote_diag_20260929_run6")
C29_TREE = C29_WORK / "system_tree"
C30_STAGE = ROOT / "work/stage_c30_diag_write_canary_20260930_run1"
C30_IMAGES = C30_STAGE / "images"
C30_REPORT = ROOT / "work/reports/20260930_C29_WRITE_AUDIT_C30_CANARY_DIAG"
C30_WORK = Path("/root/10s_os4_build/c30_diag_write_canary_20260930_run1")
C30_TREE = C30_WORK / "system_tree"
TEMPLATE = ROOT / "tools/candidate30_diag_write_canary"
SOURCE = TEMPLATE / "c30_diag.cpp"
SERVICE_RC = TEMPLATE / "c30_diag.rc"
SYSTEM_INIT = "system/etc/init/hw/init.rc"
FILE_CONTEXTS = "system/etc/selinux/plat_file_contexts"
PROPERTY_CONTEXTS = "system/etc/selinux/plat_property_contexts"
PLAT_CIL = "system/etc/selinux/plat_sepolicy.cil"
NETD_RC = "system/etc/init/netd.rc"
PRIMARY_RC = "system/etc/init/hw/init.zygote64.rc"
SECONDARY_RC = "system/etc/init/hw/init.zygote64_32.rc"
C29_RC = "system/etc/init/c29_pid1_zygote_diag.rc"
C29_HELPER = "system/bin/c29_pid1_zygote_diag"
C30_RC = "system/etc/init/c30_diag.rc"
C30_HELPER = "system/bin/c30_diag"
IMPORT_C25 = "import /system/etc/init/c25_bootdiag.rc"
IMPORT_C29 = "import /system/etc/init/c29_pid1_zygote_diag.rc"
IMPORT_C30 = "import /system/etc/init/c30_diag.rc"
NETD_CALLBACKS = ("onrestart restart zygote", "onrestart restart zygote_secondary")
IMAGE_NAMES = ("boot.img", "vendor_boot.img", "dtbo.img", "vbmeta.img",
               "vbmeta_system.img", "super.img")
INHERITED_SMALL = ("boot.img", "vendor_boot.img", "dtbo.img", "vbmeta.img")
CANDIDATE = "Candidate 30 dedicated-domain write canary and ordered startup diagnostics"
BASE = "Candidate 29 PID1/Zygote ordered diagnostic baseline"

POLICY_FRAGMENT = r"""
(type c30_diag)
(roletype object_r c30_diag)
(type c30_diag_exec)
(roletype object_r c30_diag_exec)
(typetransition init c30_diag_exec process c30_diag)
(allow init c30_diag_exec (file (read getattr map execute open)))
(allow init c30_diag (process (transition siginh rlimitinh)))
(allow c30_diag c30_diag_exec (file (read getattr map execute open entrypoint)))
(allow c30_diag c25_diag_data_file (dir (search open read write add_name getattr)))
(allow c30_diag c25_diag_data_file (file (create open read write append getattr setattr)))
(typetransition c30_diag c25_diag_data_file file c25_diag_data_file)
(allow c30_diag metadata_file (dir (search)))
(allow c30_diag init_service_status_prop (file (read getattr map open)))
(allow c30_diag boot_status_prop (file (read getattr map open)))
(allow c30_diag powerctl_prop (file (read getattr map open)))
(allow c30_diag proc_random (file (read getattr open)))
(allow c30_diag logcat_exec (file (read getattr map execute open execute_no_trans)))
(allow c30_diag logd_socket (sock_file (write)))
(allow c30_diag logd (unix_stream_socket (connectto)))
(allow c30_diag self (process (fork sigchld signal sigkill)))
""".strip()


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


def load_c29_manifest() -> tuple[dict[str, object], dict[str, dict[str, object]]]:
    path = C29_IMAGES / "BUILD_MANIFEST.json"
    require_file(path)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("candidate") != "Candidate 29 PID1/Zygote ordered fatal diagnostics":
        raise RuntimeError("C29 manifest does not identify the requested baseline.")
    if set(manifest.get("images", {})) != set(IMAGE_NAMES):
        raise RuntimeError("C29 manifest does not contain exactly six images.")
    if manifest.get("flash_scope_prepared") != ["super", "vbmeta_system_a"]:
        raise RuntimeError("C29 flash-scope metadata differs from the expected baseline.")
    checked: dict[str, dict[str, object]] = {}
    for name in INHERITED_SMALL + ("vbmeta_system.img",):
        image = C29_IMAGES / name
        expected = manifest["images"][name]
        require_file(image, int(expected["bytes"]))
        actual = sha256(image)
        if actual != str(expected["sha256"]).upper():
            raise RuntimeError(f"C29 inherited image differs from its manifest: {name}")
        checked[name] = {"bytes": image.stat().st_size, "sha256": actual}
    require_file(C29_IMAGES / "super.img", int(manifest["images"]["super.img"]["bytes"]))
    return manifest, checked


def replace_file(path: Path, content: bytes, mode: int) -> None:
    if path.exists() or path.is_symlink():
        path.unlink()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    os.chmod(path, mode)


def add_attribute_member(cil: str, attribute: str, member: str) -> str:
    prefix = f"(typeattributeset {attribute} ("
    starts = [i for i in range(len(cil)) if cil.startswith(prefix, i)]
    if len(starts) != 1:
        raise RuntimeError(f"Expected exactly one CIL typeattributeset for {attribute}, got {len(starts)}")
    start = starts[0]
    end = cil.find("\n", start)
    if end < 0:
        end = len(cil)
    line = cil[start:end]
    if member in line:
        raise RuntimeError(f"CIL member already exists: {member} in {attribute}")
    if not line.endswith("))"):
        raise RuntimeError(f"Unexpected CIL attribute-set syntax for {attribute}")
    updated = line[:-2] + " " + member + "))"
    return cil[:start] + updated + cil[end:]


def compose_policy(cil: str) -> str:
    for declaration in ("(type c30_diag)", "(type c30_diag_exec)"):
        if declaration in cil:
            raise RuntimeError(f"C30 type already exists in base policy: {declaration}")
    for attribute, member in (("domain", "c30_diag"), ("coredomain", "c30_diag"),
                              ("exec_type", "c30_diag_exec"), ("file_type", "c30_diag_exec"),
                              ("system_file_type", "c30_diag_exec")):
        cil = add_attribute_member(cil, attribute, member)
    return cil.rstrip("\n") + "\n\n" + POLICY_FRAGMENT + "\n"


def validate_policy_content(source: str, stage: Path) -> dict[str, object]:
    cap = "(policycap functionfs_seclabel)"
    if source.count(cap) != 1:
        raise RuntimeError(f"Expected one host-unsupported policycap, got {source.count(cap)}")
    check_cil = stage / "c30_plat_sepolicy_check.cil"
    check_cil.write_text(source.replace(cap + "\n", "", 1), encoding="utf-8", newline="\n")
    compiled = stage / "c30_plat_sepolicy_check.bin"
    run(["secilc", "-m", "-M", "true", "-G", "-c", "35", "-o", compiled, check_cil],
        stage / "secilc_c30_neverallow.log")
    data_file = run(["sesearch", "-A", "-s", "c30_diag", "-t", "c25_diag_data_file",
                     "-c", "file", compiled], stage / "sesearch_c30_metadata_file.log")
    data_dir = run(["sesearch", "-A", "-s", "c30_diag", "-t", "c25_diag_data_file",
                    "-c", "dir", compiled], stage / "sesearch_c30_metadata_dir.log")
    props = run(["sesearch", "-A", "-s", "c30_diag", "-c", "file", compiled],
                stage / "sesearch_c30_properties_and_files.log")
    required_file_perms = ("create", "open", "read", "write", "append", "getattr", "setattr")
    required_dir_perms = ("search", "open", "read", "write", "add_name", "getattr")
    if not all(f" {perm}" in data_file for perm in required_file_perms):
        raise RuntimeError("C30 metadata file permissions did not survive secilc validation.")
    if not all(f" {perm}" in data_dir for perm in required_dir_perms):
        raise RuntimeError("C30 metadata directory permissions did not survive secilc validation.")
    for token in ("init_service_status_prop", "boot_status_prop", "powerctl_prop",
                  "proc_random", "logcat_exec"):
        if token not in props:
            raise RuntimeError(f"C30 property/process diagnostic permission missing: {token}")
    if "allow c30_diag proc (" in source:
        raise RuntimeError("C30 must not grant generic /proc access; system_server is identified from logcat.")
    return {"secilc_exit": 0, "policy_version": 35, "neverallow_checks": "enabled",
            "platform_cil_bytes": len(source.encode("utf-8")), "compiled_policy_bytes": compiled.stat().st_size,
            "metadata_file_rules": data_file.splitlines(), "metadata_dir_rules": data_dir.splitlines(),
            "read_property_and_process_rules": [line for line in props.splitlines()
                if any(word in line for word in ("init_service_status_prop", "boot_status_prop",
                                                  "powerctl_prop", "proc_random", "logcat_exec"))]}


def validate_policy(stage: Path) -> dict[str, object]:
    source = (C30_TREE / PLAT_CIL).read_text(encoding="utf-8")
    return validate_policy_content(source, stage)


def patch_init_and_tree() -> dict[str, object]:
    init_path = C30_TREE / SYSTEM_INIT
    init_text = init_path.read_text(encoding="utf-8")
    if init_text.count(IMPORT_C25) != 1 or init_text.count(IMPORT_C29) != 1 or IMPORT_C30 in init_text:
        raise RuntimeError("C29 init-import baseline is not exact.")
    init_updated = init_text.replace(IMPORT_C29, IMPORT_C30, 1)
    replace_file(init_path, (init_updated.rstrip("\n") + "\n").encode("utf-8"),
                 stat.S_IMODE(init_path.stat().st_mode))

    old_rc = C30_TREE / C29_RC
    old_helper = C30_TREE / C29_HELPER
    require_file(old_rc)
    require_file(old_helper)
    old_rc.unlink()
    old_helper.unlink()
    rc_path = C30_TREE / C30_RC
    helper_path = C30_TREE / C30_HELPER
    if rc_path.exists() or helper_path.exists():
        raise FileExistsError("C30 diagnostic files already exist in cloned C29 tree.")
    shutil.copy2(SERVICE_RC, rc_path)
    os.chmod(rc_path, 0o644)

    contexts_path = C30_TREE / FILE_CONTEXTS
    contexts = contexts_path.read_text(encoding="utf-8")
    old_entries = (
        "/system/bin/c29_pid1_zygote_diag u:object_r:shell_exec:s0",
        "/system/etc/init/c29_pid1_zygote_diag\\.rc u:object_r:system_file:s0",
    )
    for entry in old_entries:
        if contexts.count(entry) != 1:
            raise RuntimeError(f"Expected one C29 file context entry: {entry}")
        contexts = contexts.replace(entry, "", 1)
    new_entries = (
        "/system/bin/c30_diag u:object_r:c30_diag_exec:s0",
        "/system/etc/init/c30_diag\\.rc u:object_r:system_file:s0",
    )
    if any(entry.split()[0] in contexts for entry in new_entries):
        raise RuntimeError("C30 file context entry already exists in C29 baseline.")
    replace_file(contexts_path, (contexts.rstrip("\n") + "\n" + "\n".join(new_entries) + "\n").encode(),
                 stat.S_IMODE(contexts_path.stat().st_mode))

    property_path = C30_TREE / PROPERTY_CONTEXTS
    properties = property_path.read_text(encoding="utf-8")
    property_entries = (
        "init.svc.netd u:object_r:init_service_status_prop:s0 exact string",
        "init.svc.zygote_secondary u:object_r:init_service_status_prop:s0 exact string",
    )
    for entry in property_entries:
        key = entry.split()[0]
        if any(line.split() and line.split()[0] == key for line in properties.splitlines()):
            raise RuntimeError(f"C30 property context already has exact entry: {key}")
    replace_file(property_path, (properties.rstrip("\n") + "\n" + "\n".join(property_entries) + "\n").encode(),
                 stat.S_IMODE(property_path.stat().st_mode))

    cil_path = C30_TREE / PLAT_CIL
    cil = compose_policy(cil_path.read_text(encoding="utf-8"))
    replace_file(cil_path, cil.encode("utf-8"), stat.S_IMODE(cil_path.stat().st_mode))

    rc_text = rc_path.read_text(encoding="utf-8")
    if "seclabel u:r:shell:s0" in rc_text or "start c29_" in rc_text:
        raise RuntimeError("C30 RC must use a policy transition and must not start C29 services.")
    netd = (C30_TREE / NETD_RC).read_text(encoding="utf-8")
    if any(line.strip() in NETD_CALLBACKS for line in netd.splitlines()):
        raise RuntimeError("C30 unexpectedly restored netd-to-Zygote callbacks.")
    if sha256(C30_TREE / PRIMARY_RC) != sha256(C29_TREE / PRIMARY_RC):
        raise RuntimeError("C30 changed primary Zygote critical configuration.")
    if sha256(C30_TREE / SECONDARY_RC) != sha256(C29_TREE / SECONDARY_RC):
        raise RuntimeError("C30 changed the secondary Zygote callback.")
    return {"init_import": {"removed": IMPORT_C29, "added": IMPORT_C30, "c25_retained": True},
            "removed": [C29_RC, C29_HELPER], "added": [C30_RC, C30_HELPER],
            "file_contexts_removed": list(old_entries), "file_contexts_added": list(new_entries),
            "property_contexts_added": list(property_entries), "plat_policy_fragment": POLICY_FRAGMENT,
            "netd_zygote_callbacks_remain_absent": True,
            "primary_zygote_critical_unchanged": True, "secondary_zygote_rc_unchanged": True}


def compile_helper(stage: Path) -> tuple[Path, dict[str, object]]:
    ndk = Path("/root/10s_os4_build/toolchains/android-ndk-r29/toolchains/llvm/prebuilt/linux-x86_64")
    clang = ndk / "bin/clang++"
    sysroot = ndk / "sysroot"
    require_file(clang)
    require_file(sysroot / "usr/include/sys/system_properties.h")
    binary = stage / "c30_diag"
    command = [str(clang), "--target=aarch64-linux-android35", f"--sysroot={sysroot}",
               "-std=c++17", "-O2", "-fPIE", "-pie", "-static-libstdc++",
               "-D_FORTIFY_SOURCE=2", "-Wall", "-Wextra", "-Werror", "-o",
               str(binary), str(SOURCE), "-llog"]
    run(command, stage / "compile_c30_diag.log")
    os.chmod(binary, 0o755)
    readelf = shutil.which("llvm-readelf") or shutil.which("readelf")
    if not readelf:
        raise FileNotFoundError("readelf is required for the C30 helper ELF checks.")
    elf = run([readelf, "-h", binary], stage / "c30_helper_elf_header.txt")
    dynamic = run([readelf, "-d", binary], stage / "c30_helper_dynamic_deps.txt")
    if "AArch64" not in elf or "PIE" not in dynamic or "liblog.so" not in dynamic or \
            "libc++_shared.so" in dynamic:
        raise RuntimeError("C30 helper ELF architecture or dependency validation failed.")
    return binary, {"bytes": binary.stat().st_size, "sha256": sha256(binary),
                    "architecture": "AArch64 PIE", "needed": ["liblog.so"],
                    "cxx_runtime": "statically linked libc++", "source_sha256": sha256(SOURCE)}


def inventory(root: Path) -> dict[str, Path]:
    found: dict[str, Path] = {}
    for path in root.rglob("*"):
        if path.is_file() or path.is_symlink():
            found[path.relative_to(root).as_posix()] = path
    return found


def audit_delta() -> dict[str, object]:
    before = inventory(C29_TREE)
    after = inventory(C30_TREE)
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
    expected_removed = {C29_RC, C29_HELPER}
    expected_added = {C30_RC, C30_HELPER}
    expected_modified = {SYSTEM_INIT, FILE_CONTEXTS, PROPERTY_CONTEXTS, PLAT_CIL}
    if removed != expected_removed or added != expected_added or modified != expected_modified:
        raise RuntimeError(f"C30 tree delta exceeded allowlist: removed={sorted(removed)}, "
                           f"added={sorted(added)}, modified={sorted(modified)}")
    init_text = (C30_TREE / SYSTEM_INIT).read_text(encoding="utf-8")
    if init_text.replace(IMPORT_C30, IMPORT_C29, 1) != \
            (C29_TREE / SYSTEM_INIT).read_text(encoding="utf-8"):
        raise RuntimeError("C30 init.rc changed beyond its single diagnostic import.")
    return {"removed": sorted(removed), "added": sorted(added),
            "modified": sorted(modified), "unexpected_changes": []}


def build_system(builder, stage: Path, policy_info: dict[str, object]) -> tuple[Path, dict[str, object]]:
    init_rc = C30_TREE / SYSTEM_INIT
    service_rc = C30_TREE / C30_RC
    helper = C30_TREE / C30_HELPER
    netd_rc = C30_TREE / NETD_RC
    for path in (init_rc, service_rc, helper, netd_rc):
        require_file(path)
    init_text = init_rc.read_text(encoding="utf-8")
    if init_text.count(IMPORT_C25) != 1 or IMPORT_C29 in init_text or init_text.count(IMPORT_C30) != 1:
        raise RuntimeError("C30 init import assertions failed.")
    rc_text = service_rc.read_text(encoding="utf-8")
    required_rc = ("C30_INIT_HELPER_RUNNING.txt", "C30_INIT_HELPER_STOPPED.txt",
                   "start c30_diag", "user shell", "group shell log")
    if any(token not in rc_text for token in required_rc) or "seclabel " in rc_text:
        raise RuntimeError("C30 init service RC is incomplete or pins a generic domain.")
    source_text = SOURCE.read_text(encoding="utf-8")
    for token in ("C30_CANARY_WRITE", "C30_CANARY_FDATASYNC", "C30_CANARY_APPEND",
                  "fdatasync", "CLOCK_BOOTTIME", "O_APPEND", "system_server_first_seen",
                  "am_proc_start", "SystemServer:", "C30_LOGCAT_START", "C30_LOGCAT_END"):
        if token not in source_text:
            raise RuntimeError(f"C30 helper lacks required diagnostic behavior: {token}")
    if 'opendir("/proc")' in source_text or 'readdir(proc)' in source_text or '"/proc/" +' in source_text:
        raise RuntimeError("C30 must identify system_server from logcat, not scan generic /proc entries.")
    if "pread(logger->reader_fd" not in source_text:
        raise RuntimeError("C30 must parse the concurrently captured logcat through a read-only fd.")
    if '"-r"' in source_text or '"-n"' in source_text:
        raise RuntimeError("C30 logcat must not use file rotation.")
    if "init.svc_debug.no_fatal.zygote" in source_text or "init.svc_debug.no_fatal.zygote" in rc_text:
        raise RuntimeError("C30 must not change Zygote critical escalation behavior.")
    if any(line.strip() in NETD_CALLBACKS for line in netd_rc.read_text(encoding="utf-8").splitlines()):
        raise RuntimeError("C30 unexpectedly restored netd-to-Zygote callbacks.")

    base_contexts = builder.C1 / "configs_retained/system/file_contexts"
    fs_config_source = builder.C1 / "configs_retained/system/fs_config"
    require_file(base_contexts)
    require_file(fs_config_source)
    contexts_path = stage / "system_file_contexts_c30"
    context_additions = (
        "/system/system/bin/c25_bootdiag u:object_r:shell_exec:s0",
        "/system/system/etc/init/c25_bootdiag\\.rc u:object_r:system_file:s0",
        "/system/system/bin/c30_diag u:object_r:c30_diag_exec:s0",
        "/system/system/etc/init/c30_diag\\.rc u:object_r:system_file:s0",
    )
    contexts_path.write_text(base_contexts.read_text(encoding="utf-8").rstrip("\n") +
        "\n" + "\n".join(context_additions) + "\n", encoding="utf-8", newline="\n")
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
    for entry in sorted(C30_TREE.rglob("*"), key=lambda p: p.relative_to(C30_TREE).as_posix()):
        relative = "system/" + entry.relative_to(C30_TREE).as_posix()
        if relative in known:
            continue
        st = entry.lstat()
        added.append(f"{relative} {st.st_uid} {st.st_gid} {stat.S_IMODE(st.st_mode):04o}")
        known.add(relative)
    fs_config = stage / "system_fs_config_c30"
    fs_config.write_text("\n".join(rebased + added) + "\n", encoding="utf-8", newline="\n")

    raw = stage / "system_c30.raw.erofs"
    image = stage / "system_c30.img"
    builder.run([builder.MKFS, "-zlz4hc", "-T", "0", "-U", builder.SYSTEM_UUID,
                 "--mount-point=/system", f"--fs-config-file={fs_config}",
                 f"--file-contexts={contexts_path}", raw, C30_TREE],
                log=stage / "mkfs_system_c30.log")
    builder.run([builder.FSCK, "-d0", raw], log=stage / "fsck_system_c30.log")
    shutil.copy2(raw, image)
    builder.run(["python3", builder.AVBTOOL, "add_hashtree_footer", "--image", image,
                 "--partition_size", str(builder.SYSTEM_SIZE), "--partition_name", "system",
                 "--hash_algorithm", "sha256", "--salt", builder.SYSTEM_SALT,
                 "--algorithm", "NONE", "--do_not_generate_fec"],
                log=stage / "avb_system_c30.log")
    require_file(image, builder.SYSTEM_SIZE)

    property_entries = ("init.svc.netd u:object_r:init_service_status_prop:s0 exact string",
                        "init.svc.zygote_secondary u:object_r:init_service_status_prop:s0 exact string")
    cil_tokens = ("(type c30_diag)", "(type c30_diag_exec)",
                  "(typetransition init c30_diag_exec process c30_diag)",
                  "(allow c30_diag c25_diag_data_file (file (create open read write append getattr setattr)))")
    checks_to_read = {
        "/system/etc/init/hw/init.rc": (IMPORT_C30, IMPORT_C25),
        "/system/etc/init/c30_diag.rc": required_rc,
        "/system/etc/selinux/plat_file_contexts": (
            "/system/bin/c30_diag u:object_r:c30_diag_exec:s0", "/system/etc/init/c30_diag\\.rc"),
        "/system/etc/selinux/plat_property_contexts": property_entries,
        "/system/etc/selinux/plat_sepolicy.cil": cil_tokens,
        "/system/etc/init/netd.rc": ("service netd /system/bin/netd",),
        "/system/bin/c30_diag": ("C30Diag", "C30_CANARY_WRITE", "C30_CANARY_FDATASYNC",
            "C30_CANARY_APPEND", "C30_LOGCAT_EXEC", "system_server_first_seen", "fdatasync"),
    }
    readback: dict[str, object] = {}
    readback_dir = stage / "erofs_readback"
    for erofs_path, tokens in checks_to_read.items():
        out = readback_dir / erofs_path.lstrip("/").replace("/", "_")
        content = run_bytes([builder.DUMP, "--cat", f"--path={erofs_path}", raw], out)
        if erofs_path.endswith("c30_diag"):
            if not content.startswith(b"\x7fELF") or hashlib.sha256(content).hexdigest().upper() != sha256(C30_TREE / C30_HELPER):
                raise RuntimeError("Final C30 EROFS helper readback is not byte-identical to compiled ELF.")
            text = content.decode("latin-1")
        else:
            text = content.decode("utf-8", errors="replace")
        missing = [token for token in tokens if token not in text]
        if missing:
            raise RuntimeError(f"Final EROFS readback missing {erofs_path} tokens: {missing}")
        readback[erofs_path] = {"bytes": len(content), "sha256": hashlib.sha256(content).hexdigest().upper(),
                                "required_tokens": list(tokens)}
        if erofs_path == "/system/etc/init/netd.rc":
            for callback in NETD_CALLBACKS:
                if callback.encode() in content:
                    raise RuntimeError("C30 final system image restored a netd-to-Zygote callback.")
    verify_link = image.parent / "system.img"
    if verify_link.exists() or verify_link.is_symlink():
        raise FileExistsError(f"Refusing existing AVB verification sibling: {verify_link}")
    verify_link.symlink_to(image)
    builder.run(["python3", builder.AVBTOOL, "verify_image", "--image", image],
                log=stage / "avb_verify_system_c30.log")
    verify_link.unlink()
    return image, {"system_image_bytes": image.stat().st_size, "system_image_sha256": sha256(image),
        "final_erofs_readback": readback, "new_file_contexts": list(context_additions),
        "new_fs_config_paths": ["system/system/bin/c30_diag", "system/system/etc/init/c30_diag.rc"],
        "platform_policy_validation": policy_info}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight-only", action="store_true",
                        help="Compile the helper and C30 platform policy in /tmp without cloning/building images.")
    args = parser.parse_args()
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

    c29_manifest, inherited = load_c29_manifest()
    for path in (C29_TREE / SYSTEM_INIT, C29_TREE / C29_RC, C29_TREE / C29_HELPER,
                 C29_TREE / NETD_RC, SOURCE, SERVICE_RC):
        require_file(path)
    if args.preflight_only:
        with tempfile.TemporaryDirectory(prefix="thyme-c30-preflight-") as temporary:
            temp = Path(temporary)
            helper, helper_info = compile_helper(temp)
            policy = compose_policy((C29_TREE / PLAT_CIL).read_text(encoding="utf-8"))
            policy_info = validate_policy_content(policy, temp)
            if "seclabel" in SERVICE_RC.read_text(encoding="utf-8"):
                raise RuntimeError("C30 RC contains a pinned generic seclabel.")
            print(json.dumps({"preflight": "passed", "helper": helper_info,
                              "policy": policy_info}, ensure_ascii=False, indent=2))
        return
    if C30_STAGE.exists() or C30_WORK.exists():
        raise FileExistsError("C30 run1 output already exists; refusing overwrite.")
    C30_STAGE.mkdir(parents=True, exist_ok=False)
    C30_IMAGES.mkdir(parents=True, exist_ok=False)
    C30_WORK.mkdir(parents=True, exist_ok=False)
    stage = C30_WORK / "staging"
    stage.mkdir(parents=True, exist_ok=False)
    c23 = load_module("candidate23_builder_for_c30", ROOT / "tools/build_candidate23_sf_prime_skip.py")
    c24 = load_module("candidate24_builder_for_c30", ROOT / "tools/build_candidate24_framework_display_diag.py")
    c28 = load_module("candidate28_builder_for_c30", ROOT / "tools/build_candidate28_recovery_diag.py")
    for tool in (c23.MKFS, c23.FSCK, c23.DUMP, c23.LPMAKE, c23.SIMG2IMG,
                 c23.LPDUMP, c23.AVBTOOL):
        require_file(tool)
    for executable in (c23.MKFS, c23.FSCK, c23.DUMP, c23.LPMAKE, c23.SIMG2IMG, c23.LPDUMP):
        if not os.access(executable, os.X_OK):
            raise PermissionError(f"Build tool is not executable: {executable}")

    shutil.copytree(C29_TREE, C30_TREE, symlinks=True, copy_function=c28.hardlink_or_copy)
    changes = patch_init_and_tree()
    helper, helper_info = compile_helper(stage)
    shutil.copy2(helper, C30_TREE / C30_HELPER)
    os.chmod(C30_TREE / C30_HELPER, 0o755)
    tree_delta = audit_delta()
    policy_info = validate_policy(stage)

    print("[C30] Building dedicated-domain diagnostic system on the C29 baseline.", flush=True)
    system_image, system_info = build_system(c23, stage, policy_info)
    c24.C23_IMAGES = C29_IMAGES
    vbmeta_info = c24.rebuild_vbmeta_system_c24(c23, system_image,
        C30_IMAGES / "vbmeta_system.img", stage)
    c23.C23_IMAGES = C30_IMAGES
    super_image, logical_hashes = c23.build_super(system_image, stage)
    if logical_hashes != c29_manifest.get("logical_input_hashes", {}):
        raise RuntimeError("A non-system logical partition input differs from the C29 baseline.")
    for name in INHERITED_SMALL:
        shutil.copy2(C29_IMAGES / name, C30_IMAGES / name)
        if sha256(C30_IMAGES / name) != inherited[name]["sha256"]:
            raise RuntimeError(f"Inherited C29 image changed: {name}")
    entries: dict[str, dict[str, object]] = {}
    for name in IMAGE_NAMES:
        image = C30_IMAGES / name
        require_file(image)
        entries[name] = {"bytes": image.stat().st_size, "sha256": sha256(image)}
    manifest = {
        "candidate": CANDIDATE, "base": BASE,
        "changes": [
            "Replaces the C29 generic shell-domain logger with a c30_diag/c30_diag_exec domain transition.",
            "Runs three separate metadata write canaries before creating ordered-event or logcat payloads; outcomes also go to Android log, while init independently writes helper-running and helper-stopped markers.",
            "After canaries pass, records CLOCK_BOOTTIME/boot_id helper PID and init service/property transitions using O_APPEND plus fdatasync; identifies system_server from logcat am_proc_start or SystemServer tag lines without reading /proc.",
            "Starts a non-rotating crash/system/main/events logcat capture only after canaries pass, capped at 60 seconds and at most 8 MiB while retaining 2 MiB metadata reserve; status, stderr, exit code, signal, and stop reason are recorded.",
            "Preserves C29 Android behavior: netd-to-Zygote callbacks remain removed; primary Zygote critical policy, secondary callback, netd version check, GPU/HWC, kernel, fstab, and encryption are unchanged.",
        ],
        "evidence_basis": [
            "C29 event and logcat status payloads were created but recovered as zero bytes; the original metadata inode labels and C29 merged platform policy provide the intended c25_diag_data_file type and shell write/append access.",
            "C26 files in the same metadata directory and c25_diag_data_file type contain durable non-empty payloads, so no concrete SELinux denial or generic missing-write grant was identified.",
            "C30 adds syscall-level write/fdatasync/append outcomes to Android log and init built-in lifecycle markers as channels independent of the helper's metadata file payload.",
        ],
        "diagnostic_limits": [
            "C29 recovered zero-byte inodes cannot distinguish write failure, fdatasync failure, or process death after open; C30 canaries are not yet runtime-tested.",
            "The host secilc check validates the C30 platform CIL with neverallow enabled after removing only the host-unsupported functionfs_seclabel policycap; it is not a live vendor+platform device policy load.",
            "No C30 flash or boot was performed in this milestone.",
        ],
        "tree_changes": changes, "tree_delta": tree_delta, "runtime_helper": helper_info,
        "system_build": system_info, "vbmeta_system_update": vbmeta_info,
        "logical_input_hashes": logical_hashes,
        "flash_scope_prepared": ["super", "vbmeta_system_a"],
        "inherited_images_checked": inherited, "images": entries,
        "host_storage_gate": storage,
    }
    (C30_IMAGES / "BUILD_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    C30_REPORT.mkdir(parents=True, exist_ok=True)
    report = [
        "# C29 零字节诊断写入审计与 C30 构建报告", "",
        "## C29 metadata/ext4 与 SELinux 核验", "",
        "C29 的 events、logcat status 文件 inode 均为 0 字节/0 block，实际 SELinux xattr 是 `u:object_r:c25_diag_data_file:s0`；父目录同为该 type。文件 UID/GID 为 2000:2000、mode 0660；目录 UID/GID 为 0:2000、mode 0770。C29 最终 `plat_file_contexts` 和 shell→c25 type transition 一致。实际 C29 `plat_sepolicy.cil` 对 shell 授予文件 create/open/read/write/append/getattr/setattr 与目录 search/open/read/write/add_name/getattr；C29 platform CIL 用 secilc policy version 35、neverallow enabled 验证通过。未发现应再扩大 shell 权限的证据。", "",
        "同一恢复出的 metadata 中 C26 events/logcat 是非空且具有相同 c25 label，说明 shell 域对该目录/类型曾成功持久写入并同步。C29 inode 空值更符合首个 payload write 未成功、fdatasync 未成功，或 helper 在 open 后、payload 写入前退出这一组可能性；当前 inode与C29源码不能区分这些路径。没有 errno、直接 AVC 或对应 C29 pstore，因此根因仍未闭环。", "",
        "## Unified First-Response Standalone", "",
        "新 Standalone 在创建基本 proc/sysfs/tmpfs 和必要字符设备后，先只读挂载并复制 `/sys/fs/pstore`，随后按唯一 PARTNAME 与 major/minor/块设备/容量核验 raw metadata 并比对 source/copy SHA，再按原规则只读导出 misc。最后单独保存 `standalone_dmesg.txt`，生成 FILE_MANIFEST/SHA256SUMS，才建立 RAM FAT32 UMS。它不会 replay metadata journal，也不会对持久分区写入。主机 `salvage_c13_diag.py` 负责全卷完整复制与逐文件校验。此处为静态/构建验证，尚未 RAM 启动验证。", "",
        "## C30 改动与验证", "",
        "C30 使用专用 `c30_diag` 域和 `c30_diag_exec` 入口转换。helper 启动后先做独立 write、write+fdatasync、create+sync+append+sync 三个 canary；结果发到 Android log。init built-in 独立写 helper running/stopped markers。只有 canary 全部通过后才创建 ordered events/logcat；事件使用 CLOCK_BOOTTIME、boot_id、helper PID、服务属性和 system_server 首 PID，逐条 O_APPEND+fdatasync。logcat 只采 crash/system/main/events、不轮转、最多 60 秒/8 MiB。", "",
        "C30 平台 CIL 的 secilc/neverallow、目标权限查询、AArch64 PIE ELF、最终 EROFS readback、fsck、AVB system/vbmeta_system 描述符和 LP 布局验证结果记录在 BUILD_MANIFEST.json。此为主机侧构建/静态验证；没有刷写或启动 C30，canary、真实 service 事件、PID 顺序、system_server 及 critical escalation 尚未实机验证。", "",
        f"构建时磁盘门禁：`{storage}`。C29 非系统 LP 输入与 C30 对照一致。", "",
        "| 镜像 | 字节 | SHA-256 |", "|---|---:|---|",
    ]
    report += [f"| `{name}` | {entries[name]['bytes']} | `{entries[name]['sha256']}` |" for name in IMAGE_NAMES]
    report += ["", "C30 仅为诊断 Candidate；当前未刷写。", ""]
    (C30_STAGE / "C29_WRITE_AUDIT_C30_BUILD_REPORT.md").write_text(
        "\n".join(report), encoding="utf-8", newline="\n")
    print(f"[C30] Build complete: {C30_IMAGES}", flush=True)
    for name in IMAGE_NAMES:
        print(f"  {name}: {entries[name]['bytes']} bytes SHA256={entries[name]['sha256']}", flush=True)


if __name__ == "__main__":
    main()
