#!/usr/bin/env python3
"""Build C25 from the verified C24 tree with a bounded, persistent boot sampler."""

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
C24_WORK = Path("/path/to/thyme-os4-build/c24_framework_display_diag_20260928_run2")
C24_TREE = C24_WORK / "system_tree"
C25_WORK = Path("/path/to/thyme-os4-build/c25_first_screen_diag_20260928_run5")
C25_TREE = C25_WORK / "system_tree"
C24_DIR = ROOT / "work/stage_n_thyme_os4_candidate_24_framework_display_diag_run2"
C24_IMAGES = C24_DIR / "images"
C25_DIR = ROOT / "work/stage_o_thyme_os4_candidate_25_first_screen_diag_20260928_run5"
C25_IMAGES = C25_DIR / "images"
TEMPLATE_DIR = ROOT / "tools/candidate25_bootdiag"
IMAGE_NAMES = ("boot.img", "vendor_boot.img", "dtbo.img", "vbmeta.img",
               "vbmeta_system.img", "super.img")
SMALL_INHERITED = ("boot.img", "vendor_boot.img", "dtbo.img", "vbmeta.img")
CANDIDATE = "Candidate 25 persistent first-screen/framework diagnostic"
BASE = "Candidate 24 Framework/UI/display readiness diagnostic"
IMPORT_C24 = "import /system/etc/init/c24_bootdiag.rc"
IMPORT_C25 = "import /system/etc/init/c25_bootdiag.rc"
INIT_TRIGGER = "C25_INIT_TRIGGER.txt"


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


def verify_c24_base() -> tuple[dict[str, object], dict[str, dict[str, object]]]:
    manifest_path = C24_IMAGES / "BUILD_MANIFEST.json"
    require_file(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("candidate") != BASE:
        raise RuntimeError("C24 manifest does not identify the expected diagnostic baseline.")
    if set(manifest.get("images", {})) != set(IMAGE_NAMES):
        raise RuntimeError("C24 manifest is not a complete six-image manifest.")
    if manifest.get("flash_scope_prepared") != ["super", "vbmeta_system_a"]:
        raise RuntimeError("C24 manifest has an unexpected flash scope.")
    checked: dict[str, dict[str, object]] = {}
    # Verify only the small inherited images; the unchanged C24 super is size-checked,
    # not rehashed. Its logical source hashes remain tied to the C24 build manifest.
    for name in SMALL_INHERITED + ("vbmeta_system.img",):
        path = C24_IMAGES / name
        entry = manifest["images"][name]
        require_file(path, int(entry["bytes"]))
        actual = sha256(path)
        if actual != str(entry["sha256"]).upper():
            raise RuntimeError(f"C24 inherited image differs from manifest: {name}")
        checked[name] = {"bytes": path.stat().st_size, "sha256": actual}
    require_file(C24_IMAGES / "super.img", int(manifest["images"]["super.img"]["bytes"]))
    return manifest, checked


def insert_policy_fragment(policy_path: Path, fragment_path: Path) -> dict[str, str]:
    text = policy_path.read_text(encoding="utf-8")
    policy_before_sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest().upper()
    fragment = fragment_path.read_text(encoding="utf-8").strip()
    if "c25_diag_data_file" in text or "C25 bounded boot diagnostic" in text:
        raise RuntimeError("C25 policy content already exists in the source tree.")
    marker = "(typeattributeset file_type ("
    if text.count(marker) != 1:
        raise RuntimeError("Expected exactly one compiled file_type attribute set.")
    block_start = text.index(marker)
    line_end = text.find("\n", block_start)
    if line_end < 0:
        line_end = len(text)
    line = text[block_start:line_end]
    close = line.rfind("))")
    if close < 0:
        raise RuntimeError("Could not locate the file_type attribute-set terminator.")
    # Declare the new type before its first attribute reference, then add it to file_type.
    declaration = "(type c25_diag_data_file)\n"
    line = line[:close] + " c25_diag_data_file" + line[close:]
    text = text[:block_start] + declaration + line + text[line_end:]
    text = text.rstrip("\n") + "\n\n; C25 bounded boot diagnostic policy\n" + fragment + "\n"
    policy_path.unlink()
    policy_path.write_text(text, encoding="utf-8", newline="\n")
    return {"policy_before_sha256": policy_before_sha256}


def install_c25_tree() -> dict[str, object]:
    if C25_TREE.exists():
        raise FileExistsError(f"Refusing to overwrite existing C25 system tree: {C25_TREE}")
    for source in (TEMPLATE_DIR / "c25_bootdiag.rc", TEMPLATE_DIR / "c25_bootdiag.cpp",
                   TEMPLATE_DIR / "c25_policy_fragment.cil"):
        require_file(source)

    if not C25_WORK.is_dir():
        raise FileNotFoundError(f"C25 staging root was not initialized: {C25_WORK}")
    shutil.copytree(C24_TREE, C25_TREE, symlinks=True, copy_function=os.link)

    # C25 supersedes C24's unverified logd-only sampler. Break the shared init link
    # before editing so the immutable C24 tree remains unchanged.
    init_rc = C25_TREE / "system/etc/init/hw/init.rc"
    lines = init_rc.read_text(encoding="utf-8").splitlines()
    if lines.count(IMPORT_C24) != 1:
        raise RuntimeError("C24 init import is missing or duplicated in the base tree.")
    lines.remove(IMPORT_C24)
    if IMPORT_C25 in lines:
        raise RuntimeError("C25 init import unexpectedly already exists.")
    insert_at = next((i for i, line in enumerate(lines)
                      if line.startswith("on ") or line.startswith("service ")), len(lines))
    lines.insert(insert_at, IMPORT_C25)
    init_rc.unlink()
    init_rc.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    os.chmod(init_rc, 0o644)

    old_rc = C25_TREE / "system/etc/init/c24_bootdiag.rc"
    old_script = C25_TREE / "system/bin/c24_bootdiag.sh"
    for old in (old_rc, old_script):
        if not old.is_file():
            raise FileNotFoundError(f"Expected C24 diagnostic file missing: {old}")
        old.unlink()

    rc_dst = C25_TREE / "system/etc/init/c25_bootdiag.rc"
    rc_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(TEMPLATE_DIR / "c25_bootdiag.rc", rc_dst)
    os.chmod(rc_dst, 0o644)

    policy_path = C25_TREE / "system/etc/selinux/plat_sepolicy.cil"
    policy_hash_before = sha256(policy_path)
    policy_result = insert_policy_fragment(policy_path, TEMPLATE_DIR / "c25_policy_fragment.cil")
    policy_hash_after = sha256(policy_path)

    contexts_path = C25_TREE / "system/etc/selinux/plat_file_contexts"
    contexts = contexts_path.read_text(encoding="utf-8")
    if "/metadata/thyme_os4_diag" in contexts or "/system/bin/c25_bootdiag" in contexts:
        raise RuntimeError("C25 runtime file-context entries already exist in C24 tree.")
    additions = (
        "/system/bin/c25_bootdiag u:object_r:shell_exec:s0",
        "/system/etc/init/c25_bootdiag\\.rc u:object_r:system_file:s0",
        "/metadata/thyme_os4_diag(/.*)? u:object_r:c25_diag_data_file:s0",
    )
    contexts_path.unlink()
    contexts_path.write_text(contexts.rstrip("\n") + "\n" + "\n".join(additions) + "\n",
                             encoding="utf-8", newline="\n")
    os.chmod(contexts_path, 0o644)

    # Regenerate the platform CIL+mapping digest. The verified current mapping is 202604.cil.
    mapping = C25_TREE / "system/etc/selinux/mapping/202604.cil"
    require_file(mapping)
    digest = hashlib.sha256(policy_path.read_bytes() + mapping.read_bytes()).hexdigest()
    checksum = C25_TREE / "system/etc/selinux/plat_sepolicy_and_mapping.sha256"
    checksum.unlink()
    checksum.write_text(digest + "\n", encoding="ascii", newline="\n")

    # The user-build vendor image has no precompiled policy or precompiled hash,
    # so first-stage policy loading must use the CIL dynamic compilation path.
    vendor = Path("/path/to/thyme-os4-build/c22_k40_vulkan_umd_20260927_run5/vendor_c22.img")
    require_file(vendor, 1_510_998_016)
    debugfs = shutil.which("debugfs")
    if not debugfs:
        raise FileNotFoundError("debugfs is required for the bounded vendor SELinux inventory.")
    inventory = subprocess.run([debugfs, "-R", "ls /etc/selinux", str(vendor)],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, errors="replace")
    (C25_WORK / "vendor_selinux_inventory.txt").write_text(
        inventory.stdout or "", encoding="utf-8", newline="\n")
    if inventory.returncode != 0:
        raise subprocess.CalledProcessError(inventory.returncode, inventory.args, inventory.stdout)
    if "precompiled_sepolicy" in (inventory.stdout or ""):
        raise RuntimeError("Vendor SELinux inventory unexpectedly includes precompiled policy; inspect before build.")

    return {
        "c24_init_import_removed": IMPORT_C24,
        "c25_init_import_added": IMPORT_C25,
        "c24_shell_sampler_removed": [str(old_rc), str(old_script)],
        "policy_before_sha256": policy_hash_before,
        "policy_after_sha256": policy_hash_after,
        "policy_insertion": policy_result,
        "plat_sepolicy_and_mapping_sha256": digest,
        "mapping_file": "system/etc/selinux/mapping/202604.cil",
        "file_context_additions": list(additions),
        "dynamic_policy_evidence": "C22 vendor_c22.img /etc/selinux has no precompiled_sepolicy or precompiled hash; final C25 plat CIL is dynamically compiled by init.",
    }


def compile_helper(stage: Path) -> tuple[Path, dict[str, object]]:
    ndk = Path("/path/to/thyme-os4-build/toolchains/android-ndk-r29/toolchains/llvm/prebuilt/linux-x86_64")
    clang = ndk / "bin/clang++"
    sysroot = ndk / "sysroot"
    source = TEMPLATE_DIR / "c25_bootdiag.cpp"
    binary = stage / "c25_bootdiag"
    require_file(clang)
    require_file(sysroot / "usr/include/android/log.h")
    require_file(sysroot / "usr/include/sys/system_properties.h")
    command = [str(clang), "--target=aarch64-linux-android35", f"--sysroot={sysroot}",
               "-O2", "-fPIE", "-pie", "-static-libstdc++", "-D_FORTIFY_SOURCE=2", "-Wall", "-Wextra",
               "-Werror", "-Wno-unused-parameter", "-o", str(binary), str(source), "-llog"]
    run(command, stage / "compile_c25_bootdiag.log")
    os.chmod(binary, 0o755)
    readelf = shutil.which("llvm-readelf") or shutil.which("readelf")
    if not readelf:
        raise FileNotFoundError("readelf is required to validate the C25 helper ELF.")
    elf = run([readelf, "-h", str(binary)], stage / "c25_bootdiag_elf_header.txt")
    dynamic = run([readelf, "-d", str(binary)], stage / "c25_bootdiag_dynamic_deps.txt")
    if ("AArch64" not in elf or "PIE" not in dynamic or "liblog.so" not in dynamic
            or "libc++_shared.so" in dynamic):
        raise RuntimeError("C25 helper ELF architecture or dynamic dependency check failed.")
    return binary, {"bytes": binary.stat().st_size, "sha256": sha256(binary),
                    "architecture": "AArch64", "needed": ["liblog.so"],
                    "cxx_runtime": "statically linked libc++",
                    "source_sha256": sha256(source)}


def build_policy_check(stage: Path) -> dict[str, object]:
    policy = C25_TREE / "system/etc/selinux/plat_sepolicy.cil"
    test_copy = stage / "plat_sepolicy_c25_compile_input.cil"
    text = policy.read_text(encoding="utf-8")
    # Ubuntu libsepol predates one Android 17 policycap. Remove only that declaration
    # from a temporary syntax-check copy; the shipped CIL retains the original cap.
    cap = "(policycap functionfs_seclabel)"
    if text.count(cap) != 1:
        raise RuntimeError("Expected exactly one Android 17 functionfs_seclabel policycap.")
    test_copy.write_text(text.replace(cap + "\n", "", 1), encoding="utf-8", newline="\n")
    output = stage / "plat_policy_c25_syntax_check.bin"
    secilc = shutil.which("secilc")
    if not secilc:
        raise FileNotFoundError("secilc is not available for platform CIL validation.")
    # Do not pass -N: this keeps the host compiler's neverallow checks enabled.
    result = subprocess.run([secilc, "-m", "-M", "true", "-G", "-c", "35",
                             "-o", str(output), str(test_copy)],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, errors="replace")
    (stage / "secilc_c25_platform_policy_check.log").write_text(
        result.stdout or "", encoding="utf-8", newline="\n")
    if result.returncode:
        raise subprocess.CalledProcessError(result.returncode, result.args, result.stdout)
    require_file(output)
    return {"secilc": secilc, "passed": True, "neverallow_checks_enabled": True,
            "compatibility_note": "The Ubuntu host libsepol lacks only the Android 17 functionfs_seclabel policycap; the temporary check input omits that declaration. Final image retains it, and vendor lacks precompiled policy so device init dynamically compiles the unmodified Android 17 CIL."}


def install_helper(binary: Path) -> None:
    dest = C25_TREE / "system/bin/c25_bootdiag"
    if dest.exists() or dest.is_symlink():
        raise FileExistsError(dest)
    shutil.copy2(binary, dest)
    os.chmod(dest, 0o755)


def build_system(builder, stage: Path) -> tuple[Path, dict[str, object]]:
    init_rc = C25_TREE / "system/etc/init/hw/init.rc"
    service_rc = C25_TREE / "system/etc/init/c25_bootdiag.rc"
    helper = C25_TREE / "system/bin/c25_bootdiag"
    for path in (init_rc, service_rc, helper):
        require_file(path)
    init_text = init_rc.read_text(encoding="utf-8")
    if init_text.count(IMPORT_C25) != 1 or IMPORT_C24 in init_text:
        raise RuntimeError("C25 init import state is invalid.")

    # Build-time fs_config and image xattrs are derived from the same retained C1 source maps.
    file_contexts = builder.C1 / "configs_retained/system/file_contexts"
    fs_config_source = builder.C1 / "configs_retained/system/fs_config"
    require_file(file_contexts)
    require_file(fs_config_source)
    file_contexts_c25 = stage / "system_file_contexts_c25"
    contexts = file_contexts.read_text(encoding="utf-8")
    context_additions = (
        "/system/system/bin/c25_bootdiag u:object_r:shell_exec:s0",
        "/system/system/etc/init/c25_bootdiag\\.rc u:object_r:system_file:s0",
    )
    contexts += "\n" + "\n".join(context_additions) + "\n"
    file_contexts_c25.write_text(contexts, encoding="utf-8", newline="\n")

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
    for entry in sorted(C25_TREE.rglob("*"), key=lambda p: p.relative_to(C25_TREE).as_posix()):
        relative = "system/" + entry.relative_to(C25_TREE).as_posix()
        if relative in known:
            continue
        st = entry.lstat()
        added.append(f"{relative} {st.st_uid} {st.st_gid} {stat.S_IMODE(st.st_mode):04o}")
        known.add(relative)
    fs_config = stage / "system_fs_config_c25"
    fs_config.write_text("\n".join(rebased + added) + "\n", encoding="utf-8", newline="\n")

    raw = stage / "system_c25.raw.erofs"
    image = stage / "system_c25.img"
    builder.run([builder.MKFS, "-zlz4hc", "-T", "0", "-U", builder.SYSTEM_UUID,
                 "--mount-point=/system", f"--fs-config-file={fs_config}",
                 f"--file-contexts={file_contexts_c25}", raw, C25_TREE],
                log=stage / "mkfs_system_c25.log")
    builder.run([builder.FSCK, "-d0", raw], log=stage / "fsck_system_c25.log")
    shutil.copy2(raw, image)
    builder.run(["python3", builder.AVBTOOL, "add_hashtree_footer", "--image", image,
                 "--partition_size", str(builder.SYSTEM_SIZE), "--partition_name", "system",
                 "--hash_algorithm", "sha256", "--salt", builder.SYSTEM_SALT,
                 "--algorithm", "NONE", "--do_not_generate_fec"],
                log=stage / "avb_system_c25.log")
    require_file(image, builder.SYSTEM_SIZE)

    checks: dict[str, object] = {}
    expectations = (
        ("/system/etc/init/hw/init.rc", IMPORT_C25),
        ("/system/etc/init/c25_bootdiag.rc", "C25_INIT_TRIGGER.txt"),
        ("/system/etc/init/c25_bootdiag.rc", "seclabel u:r:shell:s0"),
        ("/system/etc/init/c25_bootdiag.rc", "start c25_bootdiag"),
        ("/system/bin/c25_bootdiag", "C25BootDiag"),
        ("/system/etc/selinux/plat_sepolicy.cil", "c25_diag_data_file"),
        ("/system/etc/selinux/plat_file_contexts", "/metadata/thyme_os4_diag"),
        ("/system/etc/selinux/plat_sepolicy_and_mapping.sha256",
         (C25_TREE / "system/etc/selinux/plat_sepolicy_and_mapping.sha256").read_text(encoding="ascii").strip()),
        ("/system/build.prop", "service.sf.prime_shader_cache=0"),
    )
    for erofs_path, token in expectations:
        output_path = stage / ("dump_" + erofs_path.strip("/").replace("/", "_") + "_c25.txt")
        builder.run([builder.DUMP, "--cat", f"--path={erofs_path}", raw], log=output_path)
        content = output_path.read_text(encoding="utf-8", errors="replace")
        if token not in content:
            raise RuntimeError(f"C25 final EROFS is missing expected content: {erofs_path}: {token}")
        checks[erofs_path] = {"contains": token, "bytes": len(content.encode("utf-8"))}
    for forbidden in (IMPORT_C24, "c24_bootdiag.sh", "C24BootDiag"):
        if forbidden in init_text and forbidden == IMPORT_C24:
            raise RuntimeError("C24 logd-only service remains imported in C25.")

    verify_input = image.parent / "system.img"
    if verify_input.exists() or verify_input.is_symlink():
        raise FileExistsError(f"Refusing to overwrite AVB verification sibling: {verify_input}")
    verify_input.symlink_to(image)
    builder.run(["python3", builder.AVBTOOL, "verify_image", "--image", image],
                log=stage / "avb_verify_system_c25.log")
    verify_input.unlink()

    return image, {
        "file_contexts_for_image": list(context_additions),
        "new_fs_config_paths": ["system/system/bin/c25_bootdiag",
                                 "system/system/etc/init/c25_bootdiag.rc"],
        "final_erofs_readback": checks,
        "system_image_bytes": image.stat().st_size,
        "system_image_sha256": sha256(image),
    }


def main() -> None:
    if "microsoft" not in Path("/proc/sys/kernel/osrelease").read_text().lower():
        raise RuntimeError("Run this builder inside WSL Ubuntu.")
    baseline, inherited = verify_c24_base()
    c23 = load_module("candidate23_builder_for_c25", ROOT / "tools/build_candidate23_sf_prime_skip.py")
    c24 = load_module("candidate24_builder_for_c25", ROOT / "tools/build_candidate24_framework_display_diag.py")
    for tool in (c23.MKFS, c23.FSCK, c23.DUMP, c23.LPMAKE,
                 c23.SIMG2IMG, c23.LPDUMP, c23.AVBTOOL):
        require_file(tool)
    for executable in (c23.MKFS, c23.FSCK, c23.DUMP, c23.LPMAKE, c23.SIMG2IMG, c23.LPDUMP):
        if not os.access(executable, os.X_OK):
            raise PermissionError(f"Build tool is not executable: {executable}")

    C25_DIR.mkdir(parents=True, exist_ok=False)
    C25_IMAGES.mkdir(parents=True, exist_ok=False)
    C25_WORK.mkdir(parents=True, exist_ok=False)
    stage = C25_WORK / "staging"
    stage.mkdir(parents=True, exist_ok=False)

    policy_info = install_c25_tree()
    helper, helper_info = compile_helper(stage)
    install_helper(helper)
    policy_check = build_policy_check(stage)

    print("[C25] Building bounded dual-channel framework/display diagnostic on C24.", flush=True)
    system_image, system_info = build_system(c23, stage)
    c24.C23_IMAGES = C24_IMAGES
    vbmeta_info = c24.rebuild_vbmeta_system_c24(
        c23, system_image, C25_IMAGES / "vbmeta_system.img", stage)
    c23.C23_IMAGES = C25_IMAGES
    super_image, logical_hashes = c23.build_super(system_image, stage)
    if logical_hashes != baseline.get("logical_input_hashes", {}):
        raise RuntimeError("A non-system logical partition input differs from the C24 manifest.")
    for name in SMALL_INHERITED:
        shutil.copy2(C24_IMAGES / name, C25_IMAGES / name)
        if sha256(C25_IMAGES / name) != inherited[name]["sha256"]:
            raise RuntimeError(f"Inherited C24 image changed while copying: {name}")

    entries = {}
    for name in IMAGE_NAMES:
        path = C25_IMAGES / name
        require_file(path)
        entries[name] = {"bytes": path.stat().st_size, "sha256": sha256(path)}

    manifest = {
        "candidate": CANDIDATE,
        "base": BASE,
        "changes": [
            "Removed C24's unverified logd-only shell sampler and replaced it with a bounded AArch64 native helper, explicitly launched in the existing shell SELinux domain.",
            "post-fs-data creates only /metadata/thyme_os4_diag, relabels it, records C25_INIT_TRIGGER.txt, and starts the helper. The helper creates a unique C25 log before queries; each line is fdatasync'd and also sent to logd.",
            "The helper samples boot properties/process IDs every 15 seconds and bounded WMS/AM/SurfaceFlinger/display/layers/HOME dumps about once per minute for 15 minutes. Every query records timeout, exit/signal, spawn error, denial count, truncation and matching lines; persistent per-file cap is 512 KiB and directory cap is 8 MiB.",
            "Added a dedicated SELinux file type limited to the C25 metadata directory and explicit shell access to the three sampled boot-property types and binder calls to system_server/SurfaceFlinger. No default_android_service access was added.",
            "The platform CIL+202604 mapping digest was regenerated. The actual C22 vendor input has no precompiled policy/hash; init uses the dynamic CIL compile path.",
        ],
        "evidence_basis": [
            "C24 ran for about 16m43s and pmsg/console contained zero C24BootDiag markers. The C24 script emitted only logd records; the service had no explicit seclabel and no persistent file, so absence cannot distinguish service-start failure from log/pstore retention.",
            "The C24 shell service used /system/bin/sh without an explicit SELinux service context. C25's explicit existing shell context makes its process domain deterministic; a native bounded helper avoids a long-lived shell interpreter.",
            "C23/C24 system_server, WMS, SystemUI/HOME, bootanim exit, boot complete and physical display state remain unknown; C25's primary result is a durable, bounded sample file readable by Standalone.",
            "The targeted K40 Android 17 package has no IMiHwcExtension service-context/provider chain matching the C23/C24 AVC. No broad allow or speculative HWC change is included.",
        ],
        "limits": [
            "The helper runs as the existing shell SELinux domain with an explicit init service seclabel; it writes only the separately labeled C25 directory under metadata and queries already exposed Android services.",
            "Sampling uses bounded 4-second commands and can perturb timing slightly; no graphics, HWC, kernel, boot, fstab, encryption, userdata, or hardware settings are changed.",
            "The persistent C25 log is written under metadata, not userdata and not encryption-key/metadata records. No filesystem formatting or encryption metadata operation occurs.",
            "Static host policy compilation omits one unsupported policycap only in its temporary compiler input; the final system image retains the original Android 17 policycap and device init dynamically compiles the shipped CIL.",
        ],
        "retained_from_c24": [
            "C23 shader-cache bypass, C21 SkiaVk profile, C22 isolated K40 Vulkan UMD stack, C13/C16/C17 policy fixes, C14 BPF bypass, fstab and encrypted /data path, enforcing SELinux, and thyme kernel/vendor/device stack.",
            "C24 ANGLE/RGBX and all C23 first-screen/display behavior retained; no C24 logd-only diagnostic service remains imported.",
        ],
        "checks": [
            "C24 small inherited images checked against its manifest; unchanged C24 super was size-checked but not rehashed.",
            "Native helper compiled for AArch64 Android API 35 as PIE; libc++ is statically linked so only system-provided liblog is an added dynamic dependency.",
            "Platform CIL compiled without -N (neverallow checks enabled) using a temporary check copy that omits only unsupported functionfs_seclabel policycap; final shipped CIL retains that policycap.",
            "New system EROFS fsck passed; final EROFS readback asserted init trigger/service, helper, policy rules, runtime file contexts, updated policy/mapping digest and retained C24 boot property.",
            "avbtool verified the new system footer/hashtree; vbmeta_system contains only the updated system descriptor, preserving all other descriptor and header fields.",
            "LP repacked with the same C24 non-system logical partition inputs and geometry; lpdump extent checks passed.",
        ],
        "policy": policy_info,
        "policy_compile_check": policy_check,
        "native_helper": helper_info,
        "system_build": system_info,
        "vbmeta_system_update": vbmeta_info,
        "logical_input_hashes": logical_hashes,
        "flash_scope_prepared": ["super", "vbmeta_system_a"],
        "c24_baseline": {"checked_images": inherited,
                         "logical_input_hashes": baseline.get("logical_input_hashes", {})},
        "images": entries,
    }
    (C25_IMAGES / "BUILD_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    report = [
        "# Candidate 25 persistent first-screen/framework diagnostic build", "",
        f"- Candidate: {CANDIDATE}", f"- Base: {BASE}",
        "- C25 replaces C24's unverified logd-only sampler with a bounded native helper and a durable metadata diagnostic file.",
        "- The first file record is START; property/PID samples occur every 15 seconds and bounded framework/display queries about once per minute for 15 minutes.",
        "- Diagnostic writes are confined to `/metadata/thyme_os4_diag`; the helper does not modify userdata, encryption metadata records, BCB or hardware partitions.",
        "- Prepared flash scope: `super`, `vbmeta_system_a`; this builder never communicates with a device.",
        "", "| Image | Bytes | SHA-256 |", "|---|---:|---|",
    ]
    report += [f"| `{name}` | {entries[name]['bytes']} | `{entries[name]['sha256']}` |"
               for name in IMAGE_NAMES]
    (C25_DIR / "BUILD_REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8", newline="\n")
    print(f"[C25] Build complete: {C25_IMAGES}", flush=True)
    for name in IMAGE_NAMES:
        print(f"  {name}: {entries[name]['bytes']} bytes SHA256={entries[name]['sha256']}", flush=True)


if __name__ == "__main__":
    main()
