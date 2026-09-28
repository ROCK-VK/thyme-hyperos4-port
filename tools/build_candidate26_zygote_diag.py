#!/usr/bin/env python3
"""Build C26 on C25 with bounded, persistent Zygote/logcat first-exit capture."""

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
C25_WORK = Path("/path/to/thyme-os4-build/c25_first_screen_diag_20260928_run5")
C25_TREE = C25_WORK / "system_tree"
C26_WORK = Path("/path/to/thyme-os4-build/c26_zygote_diag_20260929_run2")
C26_TREE = C26_WORK / "system_tree"
C25_DIR = ROOT / "work/stage_o_thyme_os4_candidate_25_first_screen_diag_20260928_run5"
C25_IMAGES = C25_DIR / "images"
C26_DIR = ROOT / "work/stage_c26_zygote_diag_20260929_run2"
C26_IMAGES = C26_DIR / "images"
TEMPLATE_DIR = ROOT / "tools/candidate26_zygote_diag"
IMAGE_NAMES = ("boot.img", "vendor_boot.img", "dtbo.img", "vbmeta.img",
               "vbmeta_system.img", "super.img")
SMALL_INHERITED = ("boot.img", "vendor_boot.img", "dtbo.img", "vbmeta.img")
CANDIDATE = "Candidate 26 Zygote first-exit diagnostic"
BASE = "Candidate 25 persistent first-screen/framework diagnostic"
IMPORT_C25 = "import /system/etc/init/c25_bootdiag.rc"
IMPORT_C26 = "import /system/etc/init/c26_zygote_diag.rc"


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


def verify_c25_base() -> tuple[dict[str, object], dict[str, dict[str, object]]]:
    manifest_path = C25_IMAGES / "BUILD_MANIFEST.json"
    require_file(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("candidate") != BASE:
        raise RuntimeError("C25 manifest does not identify the expected diagnostic baseline.")
    if set(manifest.get("images", {})) != set(IMAGE_NAMES):
        raise RuntimeError("C25 manifest does not contain the six expected images.")
    if manifest.get("flash_scope_prepared") != ["super", "vbmeta_system_a"]:
        raise RuntimeError("C25 manifest has an unexpected flash scope.")
    checked: dict[str, dict[str, object]] = {}
    for name in SMALL_INHERITED + ("vbmeta_system.img",):
        path = C25_IMAGES / name
        expected = manifest["images"][name]
        require_file(path, int(expected["bytes"]))
        actual = sha256(path)
        if actual != str(expected["sha256"]).upper():
            raise RuntimeError(f"C25 inherited image differs from its manifest: {name}")
        checked[name] = {"bytes": path.stat().st_size, "sha256": actual}
    require_file(C25_IMAGES / "super.img", int(manifest["images"]["super.img"]["bytes"]))
    return manifest, checked


def clone_c25_tree() -> None:
    require_file(C25_TREE / "system/etc/init/hw/init.rc")
    for path in (C26_TREE,):
        if path.exists() or path.is_symlink():
            raise FileExistsError(f"Refusing to overwrite existing C26 tree: {path}")
    def link_or_copy(source: str, destination: str) -> str:
        try:
            os.link(source, destination, follow_symlinks=False)
        except OSError as exc:
            if exc.errno not in (errno.EXDEV, errno.EPERM, errno.EACCES, errno.EOPNOTSUPP):
                raise
            shutil.copy2(source, destination, follow_symlinks=False)
        return destination

    shutil.copytree(C25_TREE, C26_TREE, symlinks=True, copy_function=link_or_copy)


def replace_file(path: Path, content: bytes, mode: int) -> None:
    if path.exists() or path.is_symlink():
        path.unlink()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    os.chmod(path, mode)


def install_c26_tree() -> dict[str, object]:
    init_rc = C26_TREE / "system/etc/init/hw/init.rc"
    init_text = init_rc.read_text(encoding="utf-8")
    if init_text.count(IMPORT_C25) != 1 or IMPORT_C26 in init_text:
        raise RuntimeError("C25/C26 init import state is not the expected baseline.")
    replace_file(init_rc, (init_text.rstrip("\n") + "\n" + IMPORT_C26 + "\n").encode(),
                 stat.S_IMODE(init_rc.stat().st_mode))

    rc_path = C26_TREE / "system/etc/init/c26_zygote_diag.rc"
    helper_path = C26_TREE / "system/bin/c26_zygote_diag"
    if rc_path.exists() or helper_path.exists():
        raise FileExistsError("C26 diagnostic files already exist in the cloned tree.")
    shutil.copyfile(TEMPLATE_DIR / "c26_zygote_diag.rc", rc_path)
    os.chmod(rc_path, 0o644)

    contexts_path = C26_TREE / "system/etc/selinux/plat_file_contexts"
    contexts = contexts_path.read_text(encoding="utf-8")
    additions = (
        "/system/bin/c26_zygote_diag u:object_r:shell_exec:s0",
        "/system/etc/init/c26_zygote_diag\\.rc u:object_r:system_file:s0",
    )
    if any(entry.split()[0] in contexts for entry in additions):
        raise RuntimeError("C26 runtime file contexts already exist in the C25 tree.")
    replace_file(contexts_path, (contexts.rstrip("\n") + "\n" + "\n".join(additions) + "\n").encode(),
                 stat.S_IMODE(contexts_path.stat().st_mode))

    policy = C26_TREE / "system/etc/selinux/plat_sepolicy.cil"
    mapping_hash = C26_TREE / "system/etc/selinux/plat_sepolicy_and_mapping.sha256"
    return {
        "init_import_added": IMPORT_C26,
        "init_import_retained": IMPORT_C25,
        "runtime_file_context_additions": list(additions),
        "plat_sepolicy_sha256": sha256(policy),
        "plat_sepolicy_and_mapping_sha256_file": mapping_hash.read_text(encoding="ascii").strip(),
        "cil_changed": False,
    }


def compile_helper(stage: Path) -> tuple[Path, dict[str, object]]:
    ndk = Path("/path/to/thyme-os4-build/toolchains/android-ndk-r29/toolchains/llvm/prebuilt/linux-x86_64")
    clang = ndk / "bin/clang++"
    sysroot = ndk / "sysroot"
    source = TEMPLATE_DIR / "c26_zygote_diag.cpp"
    binary = stage / "c26_zygote_diag"
    require_file(clang)
    require_file(sysroot / "usr/include/sys/system_properties.h")
    header = (sysroot / "usr/include/sys/system_properties.h").read_text(encoding="utf-8")
    if "__system_property_wait(" not in header or "__system_property_area_serial" not in header:
        raise RuntimeError("The configured Android NDK does not expose the property wait API.")
    command = [str(clang), "--target=aarch64-linux-android35", f"--sysroot={sysroot}",
               "-O2", "-fPIE", "-pie", "-static-libstdc++", "-D_FORTIFY_SOURCE=2",
               "-Wall", "-Wextra", "-Werror", "-o", str(binary), str(source), "-llog"]
    run(command, stage / "compile_c26_zygote_diag.log")
    os.chmod(binary, 0o755)
    readelf = shutil.which("llvm-readelf") or shutil.which("readelf")
    if not readelf:
        raise FileNotFoundError("readelf is required to validate the C26 helper ELF.")
    elf = run([readelf, "-h", binary], stage / "c26_zygote_diag_elf_header.txt")
    dynamic = run([readelf, "-d", binary], stage / "c26_zygote_diag_dynamic_deps.txt")
    if "AArch64" not in elf or "PIE" not in dynamic or "liblog.so" not in dynamic or "libc++_shared.so" in dynamic:
        raise RuntimeError("C26 helper ELF architecture or dynamic dependency check failed.")
    return binary, {"bytes": binary.stat().st_size, "sha256": sha256(binary),
                    "architecture": "AArch64", "needed": ["liblog.so"],
                    "cxx_runtime": "statically linked libc++",
                    "source_sha256": sha256(source)}


def install_helper(binary: Path) -> None:
    dest = C26_TREE / "system/bin/c26_zygote_diag"
    if dest.exists() or dest.is_symlink():
        raise FileExistsError(dest)
    shutil.copy2(binary, dest)
    os.chmod(dest, 0o755)


def build_system(builder, stage: Path) -> tuple[Path, dict[str, object]]:
    init_rc = C26_TREE / "system/etc/init/hw/init.rc"
    service_rc = C26_TREE / "system/etc/init/c26_zygote_diag.rc"
    helper = C26_TREE / "system/bin/c26_zygote_diag"
    for path in (init_rc, service_rc, helper):
        require_file(path)
    init_text = init_rc.read_text(encoding="utf-8")
    if init_text.count(IMPORT_C25) != 1 or init_text.count(IMPORT_C26) != 1:
        raise RuntimeError("C25/C26 init imports are not present exactly once.")

    file_contexts = builder.C1 / "configs_retained/system/file_contexts"
    fs_config_source = builder.C1 / "configs_retained/system/fs_config"
    require_file(file_contexts)
    require_file(fs_config_source)
    file_contexts_c26 = stage / "system_file_contexts_c26"
    contexts = file_contexts.read_text(encoding="utf-8")
    context_additions = (
        "/system/system/bin/c25_bootdiag u:object_r:shell_exec:s0",
        "/system/system/etc/init/c25_bootdiag\\.rc u:object_r:system_file:s0",
        "/system/system/bin/c26_zygote_diag u:object_r:shell_exec:s0",
        "/system/system/etc/init/c26_zygote_diag\\.rc u:object_r:system_file:s0",
    )
    contexts += "\n" + "\n".join(context_additions) + "\n"
    file_contexts_c26.write_text(contexts, encoding="utf-8", newline="\n")

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
    for entry in sorted(C26_TREE.rglob("*"), key=lambda p: p.relative_to(C26_TREE).as_posix()):
        relative = "system/" + entry.relative_to(C26_TREE).as_posix()
        if relative in known:
            continue
        st = entry.lstat()
        added.append(f"{relative} {st.st_uid} {st.st_gid} {stat.S_IMODE(st.st_mode):04o}")
        known.add(relative)
    fs_config = stage / "system_fs_config_c26"
    fs_config.write_text("\n".join(rebased + added) + "\n", encoding="utf-8", newline="\n")

    raw = stage / "system_c26.raw.erofs"
    image = stage / "system_c26.img"
    builder.run([builder.MKFS, "-zlz4hc", "-T", "0", "-U", builder.SYSTEM_UUID,
                 "--mount-point=/system", f"--fs-config-file={fs_config}",
                 f"--file-contexts={file_contexts_c26}", raw, C26_TREE],
                log=stage / "mkfs_system_c26.log")
    builder.run([builder.FSCK, "-d0", raw], log=stage / "fsck_system_c26.log")
    shutil.copy2(raw, image)
    builder.run(["python3", builder.AVBTOOL, "add_hashtree_footer", "--image", image,
                 "--partition_size", str(builder.SYSTEM_SIZE), "--partition_name", "system",
                 "--hash_algorithm", "sha256", "--salt", builder.SYSTEM_SALT,
                 "--algorithm", "NONE", "--do_not_generate_fec"], log=stage / "avb_system_c26.log")
    require_file(image, builder.SYSTEM_SIZE)

    checks: dict[str, object] = {}
    expectations = (
        ("/system/etc/init/hw/init.rc", IMPORT_C26),
        ("/system/etc/init/c26_zygote_diag.rc", "/system/bin/c26_zygote_diag --logcat"),
        ("/system/etc/init/c26_zygote_diag.rc", "start c26_logcat"),
        ("/system/etc/init/c26_zygote_diag.rc", "start c26_zygote_watch"),
        ("/system/etc/init/c26_zygote_diag.rc", "seclabel u:r:shell:s0"),
        ("/system/bin/c26_zygote_diag", "C26ZygoteDiag"),
        ("/system/bin/c26_zygote_diag", "C26_LOGCAT_START"),
        ("/system/bin/c26_zygote_diag", "init.svc_debug_pid.zygote"),
        ("/system/etc/selinux/plat_file_contexts", "/metadata/thyme_os4_diag"),
    )
    for erofs_path, token in expectations:
        output_path = stage / ("dump_" + erofs_path.strip("/").replace("/", "_") + "_c26.bin")
        builder.run([builder.DUMP, "--cat", f"--path={erofs_path}", raw], log=output_path)
        content = output_path.read_bytes()
        if token.encode() not in content:
            raise RuntimeError(f"C26 final EROFS is missing expected content: {erofs_path}: {token}")
        checks[erofs_path] = {"contains": token, "bytes": len(content)}

    if IMPORT_C25.encode() not in (C26_TREE / "system/etc/init/hw/init.rc").read_bytes():
        raise RuntimeError("C26 failed to retain the C25 init import.")
    build_prop = (C26_TREE / "system/build.prop").read_bytes()
    for required in (b"service.sf.prime_shader_cache=0", b"persist.graphics.egl=angle"):
        if required not in build_prop:
            raise RuntimeError(f"C26 failed to retain expected inherited property: {required.decode()}")
    policy_hash = sha256(C26_TREE / "system/etc/selinux/plat_sepolicy.cil")
    expected_policy_hash = sha256(C25_TREE / "system/etc/selinux/plat_sepolicy.cil")
    if policy_hash != expected_policy_hash:
        raise RuntimeError("C26 changed C25 platform policy; no policy change is intended.")

    verify_input = image.parent / "system.img"
    if verify_input.exists() or verify_input.is_symlink():
        raise FileExistsError(f"Refusing to overwrite AVB verification sibling: {verify_input}")
    verify_input.symlink_to(image)
    builder.run(["python3", builder.AVBTOOL, "verify_image", "--image", image],
                log=stage / "avb_verify_system_c26.log")
    verify_input.unlink()

    return image, {"file_context_additions": list(context_additions),
                   "new_fs_config_paths": ["system/system/bin/c26_zygote_diag",
                                            "system/system/etc/init/c26_zygote_diag.rc"],
                   "final_erofs_readback": checks,
                   "system_image_bytes": image.stat().st_size,
                   "system_image_sha256": sha256(image),
                   "plat_sepolicy_sha256": policy_hash,
                   "plat_cil_unchanged_from_c25": True}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resume", action="store_true",
                        help="Resume only the known C26 run2 tree after an interrupted final EROFS validation.")
    args = parser.parse_args()
    if "microsoft" not in Path("/proc/sys/kernel/osrelease").read_text().lower():
        raise RuntimeError("Run this builder inside WSL Ubuntu.")
    c25_manifest, inherited = verify_c25_base()
    c23 = load_module("candidate23_builder_for_c26", ROOT / "tools/build_candidate23_sf_prime_skip.py")
    c24 = load_module("candidate24_builder_for_c26", ROOT / "tools/build_candidate24_framework_display_diag.py")
    c25 = load_module("candidate25_builder_for_c26", ROOT / "tools/build_candidate25_first_screen_diag.py")
    for tool in (c23.MKFS, c23.FSCK, c23.DUMP, c23.LPMAKE,
                 c23.SIMG2IMG, c23.LPDUMP, c23.AVBTOOL):
        require_file(tool)
    for executable in (c23.MKFS, c23.FSCK, c23.DUMP, c23.LPMAKE, c23.SIMG2IMG, c23.LPDUMP):
        if not os.access(executable, os.X_OK):
            raise PermissionError(f"Build tool is not executable: {executable}")
    require_file(C25_WORK / "system_tree/system/etc/init/c25_bootdiag.rc")
    if args.resume:
        if not C26_DIR.is_dir() or not C26_IMAGES.is_dir() or not C26_WORK.is_dir() or not C26_TREE.is_dir():
            raise FileNotFoundError("Cannot resume C26: expected run2 partial tree/work/image directories are missing.")
        if (C26_IMAGES / "BUILD_MANIFEST.json").exists() or any(C26_IMAGES.iterdir()):
            raise FileExistsError("Cannot resume C26 because final image files already exist; refusing to overwrite.")
        init_text = (C26_TREE / "system/etc/init/hw/init.rc").read_text(encoding="utf-8")
        rc_path = C26_TREE / "system/etc/init/c26_zygote_diag.rc"
        helper_path = C26_TREE / "system/bin/c26_zygote_diag"
        contexts_text = (C26_TREE / "system/etc/selinux/plat_file_contexts").read_text(encoding="utf-8")
        if init_text.count(IMPORT_C25) != 1 or init_text.count(IMPORT_C26) != 1 or not rc_path.is_file() or not helper_path.is_file():
            raise RuntimeError("C26 partial tree does not have the expected imported diagnostic assets.")
        for required in ("/system/bin/c26_zygote_diag u:object_r:shell_exec:s0",
                         "/system/etc/init/c26_zygote_diag\\.rc u:object_r:system_file:s0"):
            if required not in contexts_text:
                raise RuntimeError(f"C26 partial tree is missing runtime file context: {required}")
        if sha256(C26_TREE / "system/etc/selinux/plat_sepolicy.cil") != sha256(C25_TREE / "system/etc/selinux/plat_sepolicy.cil"):
            raise RuntimeError("C26 partial tree platform policy differs from C25.")
        resume_index = 1
        while (C26_WORK / f"staging_retry_{resume_index}").exists():
            resume_index += 1
        stage = C26_WORK / f"staging_retry_{resume_index}"
        stage.mkdir(parents=True, exist_ok=False)
        policy_info = {"init_import_added": IMPORT_C26, "init_import_retained": IMPORT_C25,
                       "runtime_file_contexts_verified": True,
                       "plat_sepolicy_sha256": sha256(C26_TREE / "system/etc/selinux/plat_sepolicy.cil"),
                       "plat_sepolicy_and_mapping_sha256_file": (C26_TREE / "system/etc/selinux/plat_sepolicy_and_mapping.sha256").read_text(encoding="ascii").strip(),
                       "cil_changed": False, "resumed_partial_run": True}
    else:
        if C26_DIR.exists() or C26_WORK.exists():
            raise FileExistsError("C26 run2 output already exists; use --resume only for the known partial EROFS check.")
        C26_DIR.mkdir(parents=True, exist_ok=False)
        C26_IMAGES.mkdir(parents=True, exist_ok=False)
        C26_WORK.mkdir(parents=True, exist_ok=False)
        stage = C26_WORK / "staging"
        stage.mkdir(parents=True, exist_ok=False)
        clone_c25_tree()
        policy_info = install_c26_tree()

    helper, helper_info = compile_helper(stage)
    if args.resume:
        (C26_TREE / "system/bin/c26_zygote_diag").unlink()
    install_helper(helper)

    print("[C26] Building a bounded Zygote first-exit capture on C25.", flush=True)
    system_image, system_info = build_system(c23, stage)
    c24.C23_IMAGES = C25_IMAGES
    vbmeta_info = c24.rebuild_vbmeta_system_c24(c23, system_image,
                                                C26_IMAGES / "vbmeta_system.img", stage)
    c23.C23_IMAGES = C26_IMAGES
    super_image, logical_hashes = c23.build_super(system_image, stage)
    if logical_hashes != c25_manifest.get("logical_input_hashes", {}):
        raise RuntimeError("A non-system logical partition input differs from the C25 manifest.")
    for name in SMALL_INHERITED:
        shutil.copy2(C25_IMAGES / name, C26_IMAGES / name)
        if sha256(C26_IMAGES / name) != inherited[name]["sha256"]:
            raise RuntimeError(f"Inherited C25 image changed while copying: {name}")

    entries = {}
    for name in IMAGE_NAMES:
        path = C26_IMAGES / name
        require_file(path)
        entries[name] = {"bytes": path.stat().st_size, "sha256": sha256(path)}
    manifest = {
        "candidate": CANDIDATE,
        "base": BASE,
        "changes": [
            "Retains C25's persistent 15-second framework/display sampler and adds an explicitly shell-labeled init service that streams all logd buffers to a unique metadata file with 1 MiB rotation and three rotated files.",
            "Adds a bounded native watcher using Bionic property wait with a 2-second timeout to record changes in zygote, zygote_secondary, c26_logcat, c25_bootdiag, netd and init debug-PID properties for up to 15 minutes.",
            "On each observed zygote restarting/stopped transition, records current zygote process cmdline/status when visible and captures up to eight bounded logcat tails from crash/system/main.",
            "Uses the existing shell_exec and c25_diag_data_file labeling/policy for new helper outputs. Platform CIL, fstab, properties, GPU/HWC, ART, kernel and hardware partitions are unchanged.",
        ],
        "evidence_basis": [
            "C25 persisted 55 consecutive samples with init.svc.zygote and zygote_secondary restarting and no system_server PID, but contained no Android logcat/crash buffer export and therefore did not preserve the first Zygote exit reason.",
            "Targeted C25/K40/donor byte comparisons show identical zygote rc files, app_process32/64, libandroid_runtime, bootclasspath/systemserverclasspath protobufs, ART APEX and runtime APEX; no K40 Zygote/ART replacement is supported by the present evidence.",
        ],
        "diagnostic_limits": [
            "The continuous logcat output is capped at four files of up to 1 MiB each; event and event-tail files are capped at 512 KiB and 1 MiB. The watcher records up to eight tails and exits after 15 minutes.",
            "The watcher uses the existing shell SELinux domain and policy. If init cannot start a service or shell cannot read logd/proc, C25 sampling and init/pstore logs remain separate evidence; C26 does not silently label that as a successful capture.",
            "This version collects no /data/tombstones content; Standalone follow-up may read only if it can do so safely without changing the mounted data state.",
        ],
        "k40_runtime_comparison": {
            "report": "work/reports/20260929_C26_ZYGOTE_FIRST_EXIT/runtime_comparison.txt",
            "result": "Zygote rc, app_process32/64, libandroid_runtime, classpath PBs, ART capex and runtime apex are byte-identical across cached K40 OS4.0.0.8 Android 17 package, Xiaomi 15 donor and C25. K40 and donor selected product dalvik.vm values also match. No direct K40 Zygote/ART adaptation found.",
        },
        "runtime_helper": helper_info,
        "policy": policy_info,
        "system_build": system_info,
        "vbmeta_system_update": vbmeta_info,
        "logical_input_hashes": logical_hashes,
        "flash_scope_prepared": ["super", "vbmeta_system_a"],
        "images": entries,
        "c25_baseline": {"checked_images": inherited,
                         "logical_input_hashes": c25_manifest.get("logical_input_hashes", {})},
        "host_storage_gate": {
            "C_free_gib": 76.76,
            "D_free_gib": 119.52,
            "E_free_gib": 176.11,
            "note": "C is below 80 GiB; prior bounded review found no safe project-reclaimable large files. All large staging/build outputs are directed to E and WSL on D. Docker assets are excluded and untouched.",
        },
    }
    manifest_path = C26_IMAGES / "BUILD_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    report = C26_DIR / "C26_ZYGOTE_DIAGNOSTIC_BUILD_REPORT.md"
    report.write_text(
        "# Candidate 26 Zygote 首因诊断构建\n\n"
        "C26 保留 C25 的持久状态采样，并加入连续限额 logcat 与 Zygote 生命周期采集。"
        "当前没有证据支持替换 K40 的 Zygote/ART 文件：本次定点比较中的启动 rc、"
        "app_process、ART/runtime APEX 和 classpath 均与供体逐字节一致。"
        "因此 C26 不改系统启动行为，只提升获取退出首因的能力。\n\n"
        "新增采集包括：所有 logd buffer 的 1 MiB × 4 文件滚动、Bionic property-wait 状态变化、"
        "zygote 进程 cmdline/status、首次至多 8 次重启时的 crash/system/main logcat tail。"
        "新增文件继续使用 C25 的 shell domain 和 metadata 诊断目录访问策略，没有扩展 CIL 权限。\n\n"
        "刷写范围：`super`、`vbmeta_system_a`。C25 的 boot、vendor_boot、dtbo、vbmeta_a 与数据状态保持。"
        "构建清单记录六项镜像大小/SHA-256；本报告不包含 ROM 或分区镜像。\n",
        encoding="utf-8", newline="\n")
    print(f"[C26] Build complete: {C26_IMAGES}", flush=True)
    print(f"[C26] Manifest: {manifest_path}", flush=True)


if __name__ == "__main__":
    main()
