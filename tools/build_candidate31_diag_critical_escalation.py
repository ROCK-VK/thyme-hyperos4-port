#!/usr/bin/env python3
"""Build C31-DIAG from the verified C30 tree with init-only causal markers."""

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
WSL_BUILD = Path("/path/to/thyme-os4-build")
C30_STAGE = ROOT / "work/stage_c30_diag_write_canary_20260930_run1"
C30_IMAGES = C30_STAGE / "images"
C30_WORK = WSL_BUILD / "c30_diag_write_canary_20260930_run1"
C30_TREE = C30_WORK / "system_tree"
C31_STAGE = ROOT / "work/stage_c31_diag_zygote_critical_20261001_run1"
C31_IMAGES = C31_STAGE / "images"
C31_WORK = WSL_BUILD / "c31_diag_zygote_critical_20261001_run1"
C31_TREE = C31_WORK / "system_tree"
C31_REPORT_DIR = ROOT / "work/reports/candidate31_diag_20261001"
PATCH_FILE = ROOT / "tools/candidate31_critical_diag/init.rc.append"
SYSTEM_INIT = "system/etc/init/hw/init.rc"
PRIMARY_RC = "system/etc/init/hw/init.zygote64.rc"
SECONDARY_RC = "system/etc/init/hw/init.zygote64_32.rc"
NETD_RC = "system/etc/init/netd.rc"
PLAT_CIL = "system/etc/selinux/plat_sepolicy.cil"
PROPERTY_CONTEXTS = "system/etc/selinux/plat_property_contexts"
DIAG_RC = "system/etc/init/c30_diag.rc"
DIAG_HELPER = "system/bin/c30_diag"
IMPORT_C25 = "import /system/etc/init/c25_bootdiag.rc"
IMPORT_C30 = "import /system/etc/init/c30_diag.rc"
NETD_CALLBACKS = ("onrestart restart zygote", "onrestart restart zygote_secondary")
IMAGE_NAMES = ("boot.img", "vendor_boot.img", "dtbo.img", "vbmeta.img",
               "vbmeta_system.img", "super.img")
INHERITED_SMALL = ("boot.img", "vendor_boot.img", "dtbo.img", "vbmeta.img")
CANDIDATE = "Candidate 31-DIAG primary Zygote critical escalation causal capture"
BASE_CANDIDATE = "Candidate 30 dedicated-domain write canary and ordered startup diagnostics"
BASE_NAME = "Candidate 30 dedicated-domain write canary and ordered startup diagnostics"


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


def run_bytes(args: list[str | os.PathLike[str]]) -> bytes:
    result = subprocess.run([os.fspath(value) for value in args],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        raise subprocess.CalledProcessError(result.returncode, args,
            result.stderr.decode("utf-8", errors="replace"))
    return result.stdout


def inventory(root: Path) -> dict[str, Path]:
    return {path.relative_to(root).as_posix(): path for path in root.rglob("*")
            if path.is_file() or path.is_symlink()}


def tree_delta(before_root: Path, after_root: Path) -> dict[str, list[str]]:
    before, after = inventory(before_root), inventory(after_root)
    removed, added = set(before) - set(after), set(after) - set(before)
    modified: set[str] = set()
    for rel in set(before) & set(after):
        old, new = before[rel], after[rel]
        if old.is_symlink() or new.is_symlink():
            if not (old.is_symlink() and new.is_symlink() and os.readlink(old) == os.readlink(new)):
                modified.add(rel)
            continue
        a, b = old.stat(), new.stat()
        if a.st_dev == b.st_dev and a.st_ino == b.st_ino:
            continue
        if a.st_size != b.st_size or sha256(old) != sha256(new):
            modified.add(rel)
    return {"removed": sorted(removed), "added": sorted(added), "modified": sorted(modified)}


def load_c30_manifest() -> dict[str, object]:
    path = C30_IMAGES / "BUILD_MANIFEST.json"
    require_file(path)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("candidate") != BASE_NAME:
        raise RuntimeError("The C30 manifest does not match the expected diagnostic baseline.")
    if manifest.get("base") != "Candidate 29 PID1/Zygote ordered diagnostic baseline":
        raise RuntimeError("C30 base identity differs from the expected lineage.")
    if set(manifest.get("images", {})) != set(IMAGE_NAMES):
        raise RuntimeError("C30 manifest image set is incomplete or unexpected.")
    if manifest.get("flash_scope_prepared") != ["super", "vbmeta_system_a"]:
        raise RuntimeError("C30 flash scope differs from the allowed Candidate scope.")
    if manifest.get("tree_delta", {}).get("unexpected_changes") != []:
        raise RuntimeError("C30 base manifest reports unexpected source changes.")
    for name in (*INHERITED_SMALL, "vbmeta_system.img"):
        item = manifest["images"][name]
        path = C30_IMAGES / name
        require_file(path, int(item["bytes"]))
        if sha256(path) != str(item["sha256"]).upper():
            raise RuntimeError(f"C30 inherited input no longer matches its manifest: {name}")
    return manifest


def atomic_replace(path: Path, content: bytes) -> None:
    mode = stat.S_IMODE(path.stat().st_mode)
    temp = path.with_name(path.name + ".c31tmp")
    if temp.exists():
        raise FileExistsError(temp)
    temp.write_bytes(content)
    os.chmod(temp, mode)
    os.replace(temp, path)


def apply_patch() -> dict[str, object]:
    path = C31_TREE / SYSTEM_INIT
    require_file(path)
    original = path.read_bytes()
    before_sha256 = hashlib.sha256(original).hexdigest().upper()
    original_text = original.decode("utf-8")
    if original_text.count(IMPORT_C25) != 1 or original_text.count(IMPORT_C30) != 1:
        raise RuntimeError("C30 init.rc must retain exactly the C25 and C30 imports.")
    if (b"THYME_C31DIAG" in original or
            b"init.svc_debug.no_fatal.zygote" in original):
        raise RuntimeError("C31-DIAG marker already exists; refusing duplicate patching.")
    patch = PATCH_FILE.read_bytes()
    if not patch.endswith(b"\n") or b"\r" in patch:
        raise RuntimeError("C31 init fragment must be LF-terminated UTF-8.")
    required = (
        b"on early-init\n    setprop init.svc_debug.no_fatal.zygote true",
        b"on zygote-start\n    write /dev/kmsg \"THYME_C31DIAG event=zygote_start",
        b"on property:init.svc.zygote=*",
        b"on property:init.svc.zygote_secondary=*",
        b"on property:init.svc.netd=*",
        b"on property:sys.boot_completed=*",
        b"/dev/kmsg \"THYME_C31DIAG",
    )
    if any(token not in patch for token in required):
        raise RuntimeError("C31 init fragment is missing a required marker or trigger.")
    if not original.endswith(b"\n"):
        original += b"\n"
    atomic_replace(path, original + patch)
    return {"file": SYSTEM_INIT, "before_sha256": before_sha256,
            "after_sha256": sha256(path), "patch_sha256": hashlib.sha256(patch).hexdigest().upper(),
            "patch_bytes": len(patch), "patch_markers": [token.decode("utf-8") for token in required]}


def validate_init_permissions(stage: Path) -> dict[str, object]:
    policy = C30_WORK / "staging/c30_plat_sepolicy_check.bin"
    require_file(policy)
    sesearch = shutil.which("sesearch")
    if not sesearch:
        raise FileNotFoundError("sesearch is required to confirm the existing init permissions.")
    checks = {
        "set_property": [sesearch, "-A", "-s", "init", "-t", "default_prop",
                          "-c", "property_service", "-p", "set", policy],
        "read_service_status_properties": [sesearch, "-A", "-s", "init", "-t",
                                             "init_service_status_prop", "-c", "file", "-p", "read", policy],
        "read_service_pid_properties": [sesearch, "-A", "-s", "init", "-t",
                                         "init_svc_debug_prop", "-c", "file", "-p", "read", policy],
        "write_kmsg": [sesearch, "-A", "-s", "init", "-t", "kmsg_device",
                        "-c", "chr_file", "-p", "write", policy],
    }
    results: dict[str, str] = {}
    for name, command in checks.items():
        result = run(command, stage / f"sesearch_c31_{name}.log").strip()
        if not result:
            raise RuntimeError(f"C30 platform policy lacks required existing init permission: {name}")
        results[name] = result
    if "property_service set" not in results["set_property"] or \
            "read" not in results["read_service_status_properties"] or \
            "read" not in results["read_service_pid_properties"] or \
            "kmsg_device:chr_file" not in results["write_kmsg"] or "write" not in results["write_kmsg"]:
        raise RuntimeError("Existing C30 platform init permission results did not match required operations.")
    return {"policy_input": "C30 platform CIL compiled with secilc/neverallow in C30 build",
            "new_selinux_rules": False, "sesearch": results}


def build_system(c23, stage: Path, c30_manifest: dict[str, object]) -> dict[str, object]:
    for path in (C31_TREE / SYSTEM_INIT, C31_TREE / PRIMARY_RC, C31_TREE / SECONDARY_RC,
                 C31_TREE / NETD_RC, C31_TREE / PLAT_CIL, C31_TREE / PROPERTY_CONTEXTS,
                 C31_TREE / DIAG_RC, C31_TREE / DIAG_HELPER):
        require_file(path)
    for rel in (PRIMARY_RC, SECONDARY_RC, NETD_RC, PLAT_CIL, PROPERTY_CONTEXTS, DIAG_RC, DIAG_HELPER):
        path = C31_TREE / rel
        expected = c30_manifest["system_build"]["final_erofs_readback"].get(
            "/system/" + rel.removeprefix("system/"))
        if expected and sha256(path) != str(expected["sha256"]).upper():
            raise RuntimeError(f"C31 changed a protected C30 file: {rel}")
    init = (C31_TREE / SYSTEM_INIT).read_bytes()
    if init.count(b"THYME_C31DIAG") != PATCH_FILE.read_bytes().count(b"THYME_C31DIAG"):
        raise RuntimeError("C31 init.rc differs from the single approved diagnostic append.")
    if b"init.svc_debug.no_fatal.zygote" in init and init.count(b"THYME_C31DIAG") == 0:
        raise RuntimeError("Unexpected no-fatal property modification outside the approved fragment.")
    netd = (C31_TREE / NETD_RC).read_text(encoding="utf-8")
    if any(line.strip() in NETD_CALLBACKS for line in netd.splitlines()):
        raise RuntimeError("C31 restored a netd-to-Zygote restart callback.")
    if b"critical window=${zygote.critical_window.minute:-off} target=zygote-fatal" not in \
            (C31_TREE / PRIMARY_RC).read_bytes():
        raise RuntimeError("C31 primary Zygote critical definition changed unexpectedly.")

    base_contexts = c23.C1 / "configs_retained/system/file_contexts"
    fs_config_source = c23.C1 / "configs_retained/system/fs_config"
    require_file(base_contexts)
    require_file(fs_config_source)
    context_additions = (
        "/system/system/bin/c25_bootdiag u:object_r:shell_exec:s0",
        "/system/system/etc/init/c25_bootdiag\\.rc u:object_r:system_file:s0",
        "/system/system/bin/c30_diag u:object_r:c30_diag_exec:s0",
        "/system/system/etc/init/c30_diag\\.rc u:object_r:system_file:s0",
    )
    contexts = base_contexts.read_text(encoding="utf-8").rstrip("\n") + "\n" + "\n".join(context_additions) + "\n"
    contexts_path = stage / "system_file_contexts_c31"
    contexts_path.write_text(contexts, encoding="utf-8", newline="\n")
    source_lines = fs_config_source.read_text(encoding="utf-8").splitlines()
    rebased = []
    for line in source_lines:
        fields = line.split(maxsplit=1)
        rebased.append(line if not fields or fields[0] == "/" else
                       "system/" + fields[0].lstrip("/") + (" " + fields[1] if len(fields) > 1 else ""))
    known = {line.split()[0].lstrip("/") for line in rebased
             if line.strip() and not line.lstrip().startswith("#")}
    added = []
    for entry in sorted(C31_TREE.rglob("*"), key=lambda item: item.relative_to(C31_TREE).as_posix()):
        relative = "system/" + entry.relative_to(C31_TREE).as_posix()
        if relative in known:
            continue
        st = entry.lstat()
        added.append(f"{relative} {st.st_uid} {st.st_gid} {stat.S_IMODE(st.st_mode):04o}")
        known.add(relative)
    fs_config = stage / "system_fs_config_c31"
    fs_config.write_text("\n".join(rebased + added) + "\n", encoding="utf-8", newline="\n")

    raw = stage / "system_c31_diag.raw.erofs"
    image = stage / "system_c31_diag.img"
    run([c23.MKFS, "-zlz4hc", "-T", "0", "-U", c23.SYSTEM_UUID,
         "--mount-point=/system", f"--fs-config-file={fs_config}",
         f"--file-contexts={contexts_path}", raw, C31_TREE], stage / "mkfs_system_c31_diag.log")
    run([c23.FSCK, "-d0", raw], stage / "fsck_system_c31_diag.log")
    shutil.copy2(raw, image)
    run(["python3", c23.AVBTOOL, "add_hashtree_footer", "--image", image,
         "--partition_size", str(c23.SYSTEM_SIZE), "--partition_name", "system",
         "--hash_algorithm", "sha256", "--salt", c23.SYSTEM_SALT,
         "--algorithm", "NONE", "--do_not_generate_fec"], stage / "avb_system_c31_diag.log")
    require_file(image, c23.SYSTEM_SIZE)

    readbacks: dict[str, object] = {}
    checks = {
        "/system/etc/init/hw/init.rc": (
            IMPORT_C25, IMPORT_C30,
            "setprop init.svc_debug.no_fatal.zygote true",
            "THYME_C31DIAG event=critical_gate",
            "on zygote-start", "THYME_C31DIAG event=zygote_start",
            "on property:init.svc.zygote=*", "on property:init.svc.zygote_secondary=*",
            "on property:init.svc.netd=*", "on property:sys.boot_completed=*",
            "THYME_C31DIAG property=sys.powerctl"),
        "/system/etc/init/netd.rc": ("service netd /system/bin/netd",),
        "/system/etc/init/hw/init.zygote64.rc": (
            "service zygote /system/bin/app_process64", "critical window=${zygote.critical_window.minute:-off} target=zygote-fatal"),
        "/system/etc/init/hw/init.zygote64_32.rc": (
            "service zygote_secondary /system/bin/app_process32", "onrestart restart zygote"),
        "/system/etc/selinux/plat_property_contexts": ("init.svc_debug_pid.", "init.svc.zygote "),
        "/system/etc/selinux/plat_sepolicy.cil": ("(type c30_diag)", "(type c30_diag_exec)"),
        "/system/etc/init/c30_diag.rc": ("C30_INIT_HELPER_RUNNING.txt", "start c30_diag"),
    }
    for erofs_path, tokens in checks.items():
        content = run_bytes([c23.DUMP, "--cat", f"--path={erofs_path}", raw])
        text = content.decode("utf-8", errors="replace")
        missing = [token for token in tokens if token not in text]
        if missing:
            raise RuntimeError(f"C31 final EROFS readback missing {erofs_path}: {missing}")
        readbacks[erofs_path] = {"bytes": len(content),
                                 "sha256": hashlib.sha256(content).hexdigest().upper(),
                                 "required_tokens": list(tokens)}
        if erofs_path == "/system/etc/init/netd.rc" and any(
                callback.encode() in content for callback in NETD_CALLBACKS):
            raise RuntimeError("C31 final EROFS reintroduced netd-to-Zygote callbacks.")
    if sha256(C31_TREE / PLAT_CIL) != sha256(C30_TREE / PLAT_CIL) or \
            sha256(C31_TREE / PROPERTY_CONTEXTS) != sha256(C30_TREE / PROPERTY_CONTEXTS):
        raise RuntimeError("C31 modified SELinux policy or property contexts.")
    verify_link = image.parent / "system.img"
    if verify_link.exists() or verify_link.is_symlink():
        raise FileExistsError(verify_link)
    verify_link.symlink_to(image)
    run(["python3", c23.AVBTOOL, "verify_image", "--image", image], stage / "avb_verify_system_c31_diag.log")
    verify_link.unlink()
    return {"system_image_bytes": image.stat().st_size,
            "system_image_sha256": sha256(image),
            "final_erofs_readback": readbacks,
            "platform_policy_sha256_unchanged": sha256(C31_TREE / PLAT_CIL),
            "property_contexts_sha256_unchanged": sha256(C31_TREE / PROPERTY_CONTEXTS),
            "init_rc_patch": {"before_sha256": sha256(C30_TREE / SYSTEM_INIT),
                              "after_sha256": sha256(C31_TREE / SYSTEM_INIT)},
            "new_files": [], "changed_files": [SYSTEM_INIT]}


def main() -> None:
    if "microsoft" not in Path("/proc/sys/kernel/osrelease").read_text().lower():
        raise RuntimeError("Run this builder in the Ubuntu WSL distribution.")
    if C31_STAGE.exists() or C31_WORK.exists():
        raise FileExistsError("C31-DIAG run1 output already exists; refusing overwrite.")
    storage = {}
    for drive, mount in (("C", "/mnt/c"), ("D", "/mnt/d"), ("E", "/mnt/e")):
        usage = shutil.disk_usage(mount)
        free_gib = round(usage.free / (1024 ** 3), 2)
        storage[f"{drive}_free_gib"] = free_gib
        print(f"[SPACE] {drive}: free={free_gib:.2f} GiB", flush=True)
        if usage.free < 50 * 1024 ** 3:
            raise RuntimeError(f"{drive}: below 50 GiB; stopping before build.")

    c30_manifest = load_c30_manifest()
    c30_init_path = C30_TREE / SYSTEM_INIT
    require_file(c30_init_path)
    expected_init = c30_manifest["system_build"]["final_erofs_readback"]["/system/etc/init/hw/init.rc"]["sha256"]
    if sha256(c30_init_path) != str(expected_init).upper():
        raise RuntimeError("C30 system_tree init.rc does not match its final EROFS readback manifest.")
    active_init = C30_TREE / "system/bin/init"
    require_file(active_init)
    active_init_bytes = active_init.read_bytes()
    if b"init.svc_debug.no_fatal." not in active_init_bytes or b"init.svc_debug_pid." not in active_init_bytes:
        raise RuntimeError("The C30 system's active second-stage init lacks the required diagnostic code paths.")
    patch_bytes = PATCH_FILE.read_bytes()
    print(f"[INIT] active second-stage init SHA256={sha256(active_init)}; no_fatal and debug PID strings present", flush=True)

    C31_STAGE.mkdir(parents=True, exist_ok=False)
    C31_IMAGES.mkdir(parents=True, exist_ok=False)
    C31_WORK.mkdir(parents=True, exist_ok=False)
    stage = C31_WORK / "staging"
    stage.mkdir(parents=True, exist_ok=False)
    c23 = load_module("candidate23_builder_for_c31diag", ROOT / "tools/build_candidate23_sf_prime_skip.py")
    c24 = load_module("candidate24_builder_for_c31diag", ROOT / "tools/build_candidate24_framework_display_diag.py")
    c28 = load_module("candidate28_builder_for_c31diag", ROOT / "tools/build_candidate28_recovery_diag.py")
    for tool in (c23.MKFS, c23.FSCK, c23.DUMP, c23.LPMAKE, c23.SIMG2IMG, c23.LPDUMP, c23.AVBTOOL):
        require_file(tool)
    for tool in (c23.MKFS, c23.FSCK, c23.DUMP, c23.LPMAKE, c23.SIMG2IMG, c23.LPDUMP):
        if not os.access(tool, os.X_OK):
            raise PermissionError(f"Build tool is not executable: {tool}")

    shutil.copytree(C30_TREE, C31_TREE, symlinks=True, copy_function=c28.hardlink_or_copy)
    init_change = apply_patch()
    delta = tree_delta(C30_TREE, C31_TREE)
    if delta != {"removed": [], "added": [], "modified": [SYSTEM_INIT]}:
        raise RuntimeError(f"C31-DIAG tree delta is outside the one-file allowlist: {delta}")
    if sha256(C30_TREE / SYSTEM_INIT) != str(expected_init).upper():
        raise RuntimeError("C30 source tree changed while cloning C31-DIAG.")
    init_permissions = validate_init_permissions(stage)
    system_info = build_system(c23, stage, c30_manifest)
    system_info["existing_init_permissions"] = init_permissions

    c24.C23_IMAGES = C30_IMAGES
    vbmeta_info = c24.rebuild_vbmeta_system_c24(c23, stage / "system_c31_diag.img",
                                                 C31_IMAGES / "vbmeta_system.img", stage)
    c23.C23_IMAGES = C31_IMAGES
    super_image, logical_hashes = c23.build_super(stage / "system_c31_diag.img", stage)
    if logical_hashes != c30_manifest.get("logical_input_hashes", {}):
        raise RuntimeError("C31-DIAG changed one or more non-system logical partition inputs.")
    for name in INHERITED_SMALL:
        source, destination = C30_IMAGES / name, C31_IMAGES / name
        shutil.copy2(source, destination)
        expected = c30_manifest["images"][name]
        if destination.stat().st_size != int(expected["bytes"]) or sha256(destination) != str(expected["sha256"]).upper():
            raise RuntimeError(f"C31-DIAG changed an inherited image: {name}")

    entries = {}
    for name in IMAGE_NAMES:
        path = C31_IMAGES / name
        require_file(path)
        entries[name] = {"bytes": path.stat().st_size, "sha256": sha256(path)}
    manifest = {
        "candidate": CANDIDATE,
        "base": BASE_CANDIDATE,
        "classification": "diagnostic-only; not a startup fix",
        "changes": [
            "Adds one early-init setprop for init.svc_debug.no_fatal.zygote=true; this suppresses only init's critical fatal escalation for primary zygote. Service restarts/onrestart continue unchanged.",
            "Appends one post-start zygote-start snapshot and init built-in /dev/kmsg property-trigger markers for primary/secondary zygote, netd, sys.boot_completed, and sys.powerctl. Kmsg timestamps provide monotonic uptime; service state and init debug PID correlate C30 pstore main PIDs with init-managed service names.",
            "Retains all C30 diagnostics, netd callbacks removal, Zygote service definitions, secondary callback, SELinux, property contexts, ART/runtime, graphics stack, kernel, fstab, encryption, and inherited boot images.",
        ],
        "evidence_basis": [
            "C30 pmsg contains five main SIGABRT PIDs; the final abort estimate is about 43 ms before PID1's sysrq panic, but none is mapped to an init service PID.",
            "C30 primary zygote remains critical with a 10-minute window; C30 active second-stage init binary contains the init.svc_debug.no_fatal and init.svc_debug_pid code-path strings.",
            "C30 pmsg contains no service-name/PID reap line sufficient to correlate main PIDs; init built-in writes to kmsg are retained by the existing pstore-first Standalone capture path.",
        ],
        "runtime_questions": [
            "Does setting no_fatal prevent the C30-style PID1 panic while primary Zygote continues to restart?",
            "Which of the C30 main SIGABRT PIDs belong to primary zygote, secondary zygote, or another process?",
            "Do native init reap logs and THYME_C31DIAG kmsg state/PID markers align in Candidate pstore?",
        ],
        "source_delta": {**delta, "unexpected_changes": []},
        "init_change": init_change,
        "active_second_stage_init": {"path": "system/bin/init", "bytes": active_init.stat().st_size,
                                     "sha256": sha256(active_init),
                                     "no_fatal_string_present": True, "debug_pid_string_present": True},
        "system_build": system_info,
        "vbmeta_system_update": vbmeta_info,
        "logical_input_hashes": logical_hashes,
        "flash_scope_prepared": ["super", "vbmeta_system_a"],
        "inherited_images_checked": {name: c30_manifest["images"][name] for name in INHERITED_SMALL},
        "images": entries,
        "host_storage_gate": storage,
        "device_operations": "none during build; flash script is separate and never reboots",
    }
    (C31_IMAGES / "BUILD_MANIFEST.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                                                     encoding="utf-8", newline="\n")
    C31_REPORT_DIR.mkdir(parents=True, exist_ok=False)
    report = [
        "# C31-DIAG 构建与静态门禁报告", "",
        "## 目的", "",
        "本 Candidate 只验证 C30 的 primary Zygote critical escalation 与 PID1 sysrq panic 是否同一因果链。它不是生产修复，不改变 Zygote、netd、SELinux 或系统服务的启动策略。", "",
        "## 实际改动", "",
        f"- C30→C31-DIAG 唯一树内差异：`{SYSTEM_INIT}`。C30 的 C25/C30 imports 保留；新增 early-init `init.svc_debug.no_fatal.zygote=true`、zygote-start 初始状态/PID 快照和 THYME_C31DIAG kmsg 状态标记。",
        "- active second-stage `/system/bin/init` 的 C30 SHA-256、大小和 no_fatal/debug-PID 字符串记录于 BUILD_MANIFEST.json。仅静态二进制字符串检查，不等同设备运行时生效验证。",
        "- 没有改 SELinux policy/property contexts、netd rc、primary/secondary Zygote rc、kernel、vendor、framework、ART、userdata 或 metadata。", "",
        "## 验证", "",
        "- 一文件 allowlist tree diff 通过；C25/C30 diagnostic helper、netd callbacks absence、primary critical 定义、secondary callback 和 SELinux 文件 SHA 复核通过。",
        "- system EROFS 重建、fsck、关键 init RC EROFS readback、AVB system image verify、vbmeta_system descriptor regeneration、LP repack/lpdump 和镜像 manifest SHA 验证通过。",
        "- C30 非 system logical input hashes 与 C31 重建输入一致；继承 boot/vendor_boot/dtbo/vbmeta 均与 C30 Manifest 相同。", "",
        "## 运行时尚未验证", "",
        "- C31-DIAG 尚未在设备启动。运行时必须确认 THYME_C31DIAG gate marker、zygote service/PID state 和 pstore 时间戳。",
        "- no_fatal 属性设计上只跳过 critical fatal 分支，zygote 仍可重启且 onrestart 不变；C31 实机用于验证是否不再触发原 PID1 panic并获取各次 PID/信号。",
        "- 设备刷写状态与槽位以最终实时 Fastboot transcript 为准；本构建不发送设备命令。", "",
    ]
    (C31_REPORT_DIR / "C31_DIAG_BUILD_AND_STATIC_GATE.md").write_text("\n".join(report), encoding="utf-8", newline="\n")
    print(json.dumps({"candidate": CANDIDATE, "delta": delta, "system": system_info,
                      "vbmeta_system": vbmeta_info, "images": entries,
                      "logical_input_hashes": logical_hashes, "report": str(C31_REPORT_DIR)},
                     ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
