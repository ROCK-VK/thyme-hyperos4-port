#!/usr/bin/env python3
"""Build C24 from the verified C23 system tree with bounded boot/UI/display sampling."""

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
C23_TREE = Path("/root/10s_os4_build/c23_sf_prime_skip_20260927_run4/system_tree")
C24_WORK = Path("/root/10s_os4_build/c24_framework_display_diag_20260928_run2")
C24_TREE = C24_WORK / "system_tree"
C23_IMAGES = ROOT / "work/stage_m_thyme_os4_candidate_23_sf_prime_skip_run4/images"
C24_DIR = ROOT / "work/stage_n_thyme_os4_candidate_24_framework_display_diag_run2"
C24_IMAGES = C24_DIR / "images"
TEMPLATE_DIR = ROOT / "tools/candidate24_bootdiag"
IMAGE_NAMES = ("boot.img", "vendor_boot.img", "dtbo.img", "vbmeta.img",
               "vbmeta_system.img", "super.img")
CANDIDATE = "Candidate 24 Framework/UI/display readiness diagnostic"
BASE = "Candidate 23 SurfaceFlinger shader-cache prime bypass"


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
        raise RuntimeError(f"Unexpected file size for {path}: {path.stat().st_size} != {size}")


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
        print(output[-12000:], flush=True)
        raise subprocess.CalledProcessError(result.returncode, command, output)
    return output


def load_c23_builder():
    path = ROOT / "tools/build_candidate23_sf_prime_skip.py"
    spec = importlib.util.spec_from_file_location("candidate23_builder", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import existing C23 builder: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def verify_c23_baseline(builder) -> dict[str, object]:
    manifest_path = C23_IMAGES / "BUILD_MANIFEST.json"
    require_file(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("candidate") != BASE:
        raise RuntimeError("C23 manifest does not describe the expected candidate.")
    if set(manifest.get("images", {})) != set(IMAGE_NAMES):
        raise RuntimeError("C23 manifest is not a complete six-image manifest.")
    # Recheck the four inherited boot/AVB images plus C23 vbmeta_system. Do not
    # rehash the old 7.7 GB C23 super; its exact bytes were verified at build/flash.
    checked = {}
    for name in ("boot.img", "vendor_boot.img", "dtbo.img", "vbmeta.img", "vbmeta_system.img"):
        path = C23_IMAGES / name
        entry = manifest["images"][name]
        require_file(path, int(entry["bytes"]))
        digest = sha256(path)
        if digest != str(entry["sha256"]).upper():
            raise RuntimeError(f"C23 source image differs from its manifest: {name}")
        checked[name] = {"bytes": path.stat().st_size, "sha256": digest}
    super_entry = manifest["images"]["super.img"]
    require_file(C23_IMAGES / "super.img", int(super_entry["bytes"]))

    prop = (C23_TREE / "system/build.prop").read_text(encoding="utf-8")
    expected_properties = (
        "service.sf.prime_shader_cache=0",
        "debug.renderengine.vulkan=true",
        "debug.renderengine.backend=skiavkthreaded",
        "debug.hwui.renderer=skiavk",
        "ro.surface_flinger.default_composition_pixel_format=2",
    )
    for item in expected_properties:
        if prop.splitlines().count(item) != 1:
            raise RuntimeError(f"C23 property baseline is missing or duplicated: {item}")
    if not (C23_TREE / "system/etc/init/hw/init.rc").is_file():
        raise FileNotFoundError("C23 system init.rc not found in its build tree.")
    return {"manifest": manifest, "checked_images": checked,
            "retained_properties": list(expected_properties)}


def install_diagnostic_tree() -> tuple[str, str]:
    if C24_WORK.exists() or C24_TREE.exists():
        raise FileExistsError(f"Refusing to overwrite existing C24 WSL output: {C24_WORK}")
    if C24_DIR.exists() or C24_IMAGES.exists():
        raise FileExistsError(f"Refusing to overwrite existing C24 image stage: {C24_DIR}")
    rc_template = TEMPLATE_DIR / "c24_bootdiag.rc"
    sh_template = TEMPLATE_DIR / "c24_bootdiag.sh"
    require_file(rc_template)
    require_file(sh_template)

    # Hard-link unchanged files to save hundreds of GiB; new files are unique,
    # and init.rc is unlinked in the new tree before its one-line import edit.
    C24_WORK.mkdir(parents=True, exist_ok=False)
    shutil.copytree(C23_TREE, C24_TREE, symlinks=True, copy_function=os.link)
    rc_path = C24_TREE / "system/etc/init/c24_bootdiag.rc"
    sh_path = C24_TREE / "system/bin/c24_bootdiag.sh"
    init_rc = C24_TREE / "system/etc/init/hw/init.rc"
    if rc_path.exists() or sh_path.exists():
        raise FileExistsError("C24 diagnostic file name already exists in the copied C23 tree.")

    init_bytes = init_rc.read_bytes()
    import_line = b"import /system/etc/init/c24_bootdiag.rc"
    if import_line in init_bytes:
        raise RuntimeError("C24 import unexpectedly already exists in C23 init.rc.")
    original_hash = hashlib.sha256(init_bytes).hexdigest().upper()
    rc_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(rc_template, rc_path)
    sh_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(sh_template, sh_path)
    os.chmod(rc_path, 0o644)
    os.chmod(sh_path, 0o644)

    # Break the hard link before changing this file; preserve C23 byte-for-byte.
    init_rc.unlink()
    text = init_bytes.decode("utf-8")
    lines = text.splitlines()
    insert_at = next((i for i, line in enumerate(lines)
                      if line.startswith("on ") or line.startswith("service ")), len(lines))
    lines.insert(insert_at, import_line.decode("ascii"))
    init_rc.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    os.chmod(init_rc, 0o644)
    if hashlib.sha256((C23_TREE / "system/etc/init/hw/init.rc").read_bytes()).hexdigest().upper() != original_hash:
        raise RuntimeError("C23 source init.rc changed; aborting before image construction.")
    return original_hash, hashlib.sha256(init_rc.read_bytes()).hexdigest().upper()


def build_system(builder, stage: Path) -> tuple[Path, dict[str, object]]:
    import_file = C24_TREE / "system/etc/init/hw/init.rc"
    rc_file = C24_TREE / "system/etc/init/c24_bootdiag.rc"
    sh_file = C24_TREE / "system/bin/c24_bootdiag.sh"
    for path in (import_file, rc_file, sh_file):
        require_file(path)
    if import_file.read_text(encoding="utf-8").count("import /system/etc/init/c24_bootdiag.rc") != 1:
        raise RuntimeError("C24 init import is absent or duplicated.")

    file_contexts = builder.C1 / "configs_retained/system/file_contexts"
    fs_config_source = builder.C1 / "configs_retained/system/fs_config"
    require_file(file_contexts)
    require_file(fs_config_source)
    file_contexts_c24 = stage / "system_file_contexts_c24"
    contexts = file_contexts.read_text(encoding="utf-8")
    context_additions = (
        "/system/system/etc/init/c24_bootdiag\\.rc u:object_r:system_file:s0",
        "/system/system/bin/c24_bootdiag\\.sh u:object_r:system_file:s0",
    )
    contexts += "\n" + "\n".join(context_additions) + "\n"
    file_contexts_c24.write_text(contexts, encoding="utf-8", newline="\n")

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
    for entry in sorted(C24_TREE.rglob("*"), key=lambda p: p.relative_to(C24_TREE).as_posix()):
        relative = "system/" + entry.relative_to(C24_TREE).as_posix()
        if relative in known:
            continue
        st = entry.lstat()
        added.append(f"{relative} {st.st_uid} {st.st_gid} {stat.S_IMODE(st.st_mode):04o}")
        known.add(relative)
    fs_config = stage / "system_fs_config_c24"
    fs_config.write_text("\n".join(rebased + added) + "\n", encoding="utf-8", newline="\n")

    raw = stage / "system_c24.raw.erofs"
    image = stage / "system_c24.img"
    builder.run([builder.MKFS, "-zlz4hc", "-T", "0", "-U", builder.SYSTEM_UUID,
                 "--mount-point=/system", f"--fs-config-file={fs_config}",
                 f"--file-contexts={file_contexts_c24}", raw, C24_TREE],
                log=stage / "mkfs_system_c24.log")
    builder.run([builder.FSCK, "-d0", raw], log=stage / "fsck_system_c24.log")
    shutil.copy2(raw, image)
    builder.run(["python3", builder.AVBTOOL, "add_hashtree_footer", "--image", image,
                 "--partition_size", str(builder.SYSTEM_SIZE), "--partition_name", "system",
                 "--hash_algorithm", "sha256", "--salt", builder.SYSTEM_SALT,
                 "--algorithm", "NONE", "--do_not_generate_fec"],
                log=stage / "avb_system_c24.log")
    require_file(image, builder.SYSTEM_SIZE)

    checks = {}
    for image_path, erofs_path, token in (
        (raw, "/system/etc/init/hw/init.rc", "import /system/etc/init/c24_bootdiag.rc"),
        (raw, "/system/etc/init/c24_bootdiag.rc", "start c24_bootdiag"),
        (raw, "/system/bin/c24_bootdiag.sh", "C24BootDiag"),
        (raw, "/system/build.prop", "service.sf.prime_shader_cache=0"),
    ):
        output_path = stage / ("dump_" + erofs_path.strip("/").replace("/", "_") + ".txt")
        builder.run([builder.DUMP, "--cat", f"--path={erofs_path}", image_path], log=output_path)
        content = output_path.read_text(encoding="utf-8", errors="replace")
        if token not in content:
            raise RuntimeError(f"C24 final EROFS is missing expected content: {erofs_path}: {token}")
        checks[erofs_path] = {"contains": token, "bytes": len(content.encode("utf-8"))}

    verify_input = image.parent / "system.img"
    if verify_input.exists() or verify_input.is_symlink():
        raise FileExistsError(f"Refusing to overwrite AVB verification sibling: {verify_input}")
    verify_input.symlink_to(image)
    builder.run(["python3", builder.AVBTOOL, "verify_image", "--image", image],
                log=stage / "avb_verify_system_c24.log")
    verify_input.unlink()

    return image, {"file_contexts": context_additions,
                  "new_fs_config_paths": [
                      "system/system/etc/init/c24_bootdiag.rc",
                      "system/system/bin/c24_bootdiag.sh"],
                  "final_erofs_readback": checks,
                  "system_image_sha256": sha256(image),
                  "system_image_bytes": image.stat().st_size}


def rebuild_vbmeta_system_c24(builder, system_image: Path, out: Path,
                              stage: Path) -> dict[str, object]:
    """Replace only the system descriptor, allowing its EROFS data length to grow."""
    sys.path.insert(0, str(ROOT / "tools/bootimg"))
    from avbtool import Avb, AvbHashtreeDescriptor, ImageHandler

    base = C23_IMAGES / "vbmeta_system.img"
    require_file(base, 131072)
    avb = Avb()
    _, base_header, base_descs, _ = avb._parse_image(ImageHandler(str(base)))
    _, _, system_descs, _ = avb._parse_image(ImageHandler(str(system_image)))
    new_system = next((d for d in system_descs
                       if isinstance(d, AvbHashtreeDescriptor) and d.partition_name == "system"), None)
    old_system = next((d for d in base_descs
                       if isinstance(d, AvbHashtreeDescriptor) and d.partition_name == "system"), None)
    if new_system is None or old_system is None:
        raise RuntimeError("C23 or C24 is missing the expected system hashtree descriptor.")

    invariant_fields = ("dm_verity_version", "data_block_size", "hash_block_size",
                        "fec_num_roots", "fec_offset", "fec_size", "hash_algorithm",
                        "flags", "partition_name", "salt")
    changed = [name for name in invariant_fields if getattr(new_system, name) != getattr(old_system, name)]
    if changed:
        raise RuntimeError(f"C24 changed unexpected system AVB fields: {changed}")
    if new_system.image_size <= 0 or new_system.image_size > builder.SYSTEM_SIZE:
        raise RuntimeError("C24 system AVB data size is outside the system_a partition.")
    if new_system.tree_offset != new_system.image_size:
        raise RuntimeError("C24 system hashtree offset does not immediately follow its data region.")
    if new_system.tree_offset + new_system.tree_size > builder.SYSTEM_SIZE:
        raise RuntimeError("C24 system hashtree would exceed the system_a partition.")

    new_descs = [new_system if isinstance(d, AvbHashtreeDescriptor) and d.partition_name == "system" else d
                 for d in base_descs]
    blob = avb._generate_vbmeta_blob(
        algorithm_name="NONE", key_path=None, public_key_metadata_path=None,
        descriptors=new_descs, chain_partitions_use_ab=None,
        chain_partitions_do_not_use_ab=None, rollback_index=base_header.rollback_index,
        flags=base_header.flags, rollback_index_location=base_header.rollback_index_location,
        props=None, props_from_file=None, kernel_cmdlines=None,
        setup_rootfs_from_kernel=None, ht_desc_to_setup=None,
        include_descriptors_from_image=None, signing_helper=None,
        signing_helper_with_files=None, release_string=base_header.release_string,
        append_to_release_string=None,
        required_libavb_version_minor=base_header.required_libavb_version_minor)
    if len(blob) > 131072:
        raise RuntimeError("C24 vbmeta_system blob exceeds the existing partition image size.")
    out.write_bytes(blob + b"\0" * (131072 - len(blob)))

    _, new_header, check_descs, _ = avb._parse_image(ImageHandler(str(out)))
    old_by_name = {d.partition_name: d for d in base_descs if isinstance(d, AvbHashtreeDescriptor)}
    new_by_name = {d.partition_name: d for d in check_descs if isinstance(d, AvbHashtreeDescriptor)}
    if set(new_by_name) != set(old_by_name):
        raise RuntimeError("C24 vbmeta_system descriptor set changed unexpectedly.")
    if builder.descriptor_json(new_by_name["system"]) != builder.descriptor_json(new_system):
        raise RuntimeError("C24 system descriptor did not survive vbmeta_system generation.")
    for name in old_by_name:
        if name != "system" and builder.descriptor_json(old_by_name[name]) != builder.descriptor_json(new_by_name[name]):
            raise RuntimeError(f"C24 unexpectedly changed the {name} hashtree descriptor.")
    if (new_header.flags, new_header.rollback_index, new_header.rollback_index_location,
            new_header.release_string) != (base_header.flags, base_header.rollback_index,
            base_header.rollback_index_location, base_header.release_string):
        raise RuntimeError("C24 vbmeta_system header fields changed unexpectedly.")
    builder.run(["python3", builder.AVBTOOL, "info_image", "--image", out],
                log=stage / "vbmeta_system_c24_info.txt")
    return {
        "base_sha256": sha256(base),
        "system_image_size_before": old_system.image_size,
        "system_image_size_after": new_system.image_size,
        "system_tree_size": new_system.tree_size,
        "system_root_digest": new_system.root_digest.hex(),
        "flags": new_header.flags,
        "rollback_index": new_header.rollback_index,
        "rollback_index_location": new_header.rollback_index_location,
        "unchanged_other_descriptors": sorted(name for name in old_by_name if name != "system"),
    }


def main() -> None:
    if "microsoft" not in Path("/proc/sys/kernel/osrelease").read_text().lower():
        raise RuntimeError("Run this builder inside the Ubuntu WSL distribution.")
    builder = load_c23_builder()
    for tool in (builder.MKFS, builder.FSCK, builder.DUMP, builder.LPMAKE,
                 builder.SIMG2IMG, builder.LPDUMP, builder.AVBTOOL):
        require_file(tool)
    for executable in (builder.MKFS, builder.FSCK, builder.DUMP, builder.LPMAKE,
                       builder.SIMG2IMG, builder.LPDUMP):
        if not os.access(executable, os.X_OK):
            raise PermissionError(f"Build tool is not executable: {executable}")

    baseline = verify_c23_baseline(builder)
    init_source_sha, init_c24_sha = install_diagnostic_tree()
    C24_DIR.mkdir(parents=True, exist_ok=False)
    C24_IMAGES.mkdir(parents=True, exist_ok=False)
    stage = C24_WORK / "staging"
    stage.mkdir(parents=True, exist_ok=False)

    print("[C24] Building system with diagnostic-only init service; C23 graphics properties retained.", flush=True)
    system_image, system_info = build_system(builder, stage)

    # Reuse the proven C23 AVB/LP routines with C23 as the base descriptor set.
    builder.C22_IMAGES = C23_IMAGES
    builder.C23_IMAGES = C24_IMAGES
    vbmeta_info = rebuild_vbmeta_system_c24(builder,
        system_image, C24_IMAGES / "vbmeta_system.img", stage)
    super_image, lp_inputs = builder.build_super(system_image, stage)
    expected_lp_inputs = baseline["manifest"].get("logical_input_hashes", {})
    if lp_inputs != expected_lp_inputs:
        raise RuntimeError("A non-system logical partition input differs from the C23 manifest.")
    for name in ("boot.img", "vendor_boot.img", "dtbo.img", "vbmeta.img"):
        shutil.copy2(C23_IMAGES / name, C24_IMAGES / name)
        expected = baseline["checked_images"][name]["sha256"]
        if sha256(C24_IMAGES / name) != expected:
            raise RuntimeError(f"Inherited C23 image changed while copying: {name}")

    entries = {}
    for name in IMAGE_NAMES:
        path = C24_IMAGES / name
        require_file(path)
        entries[name] = {"bytes": path.stat().st_size, "sha256": sha256(path)}

    manifest = {
        "candidate": CANDIDATE,
        "base": BASE,
        "changes": [
            "Added /system/bin/c24_bootdiag.sh and /system/etc/init/c24_bootdiag.rc; the system init.rc explicitly imports the diagnostic rc.",
            "The post-fs-data oneshot samples boot properties/process PIDs every 10 seconds and bounded WindowManager, ActivityManager, SurfaceFlinger, display, layer-list and BootAnimation-latency dumps about once per minute for 15 minutes. Output goes to Android logd/pmsg; it writes no persistent diagnostic file.",
        ],
        "evidence_basis": [
            "C23 ran for about 11m52s with a static Xiaomi logo and pmsg coverage to about 11m38s, but did not capture system_server phases, WMS enable-screen, SystemUI/HOME, bootanim.exit, sys.boot_completed or HWC/present state.",
            "BootAnimationShownTiming in C23 does not prove a frame reached the physical panel; C24 samples framework state and SurfaceFlinger/display state so those failure classes can be distinguished.",
            "Targeted K40 OS4 Android 17 comparison found no directly reusable framework/display boot fix; C23 core framework jars match the OS4 donor/K40, while K40-specific overlays are device-targeted and were not copied.",
        ],
        "limits": [
            "C24 changes diagnostic init scheduling and adds periodic binder dumps, a small workload that could slightly perturb timing; it does not change SELinux enforcing, GPU routing, display configuration, fstab, encryption, kernel or vendor hardware stack.",
            "Software present/latency records can show SurfaceFlinger/HWC submission attempts, but only the user's observation establishes what appeared on the physical panel.",
            "All runtime diagnostic output still depends on logd/pmsg retention and will be verified from the next boot; this build is not runtime-validated.",
        ],
        "retained_from_c23": [
            "C23 shader-cache bypass, K21 SkiaVk RenderEngine profile, C22 isolated K40 Vulkan UMD stack, prior BPF/ION/property-context/storage fixes, SELinux enforcing and thyme kernel/vendor/device hardware stack.",
            "No changes to userdata, metadata, misc/BCB, boot-control state or hardware identity/calibration partitions.",
        ],
        "checks": [
            "C23 small inherited image set checked against its manifest; the existing 7.7 GB C23 super was not rehashed.",
            "New system EROFS fsck passed; final EROFS readback asserted imported init rc, service/action, sampling script and retained C23 property.",
            "avbtool verify_image validated the new system footer and hashtree; the system descriptor data size is allowed to reflect the additional EROFS blocks while remaining within system_a.",
            "New vbmeta_system contains the updated system hashtree descriptor only; C23 product/system_ext descriptors and AVB header metadata retained.",
            "LP repacked with the same C23 logical partition sources and geometry; lpdump extent checks passed.",
            "Android shell script syntax checked with Ubuntu sh -n; new diagnostics use system_file xattrs and existing system_file/ shell_exec tool contexts only; no SELinux policy added.",
        ],
        "flash_scope_prepared": ["super", "vbmeta_system_a"],
        "c23_baseline": {"checked_images": baseline["checked_images"],
                         "retained_properties": baseline["retained_properties"],
                         "system_init_rc_sha256_before": init_source_sha,
                         "system_init_rc_sha256_c24": init_c24_sha},
        "system_build": system_info,
        "vbmeta_system_update": vbmeta_info,
        "logical_input_hashes": lp_inputs,
        "images": entries,
    }
    (C24_IMAGES / "BUILD_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    report = [
        "# Candidate 24 Framework/UI/display diagnostic build", "",
        f"- Candidate: {CANDIDATE}", f"- Base: {BASE}",
        "- System-only diagnostic additions; C23 system properties and all other logical partition sources retained.",
        "- The diagnostic service logs state to logd/pmsg every 10 seconds and bounded framework/display dumps roughly once per minute for 15 minutes after post-fs-data.",
        "- No runtime claim is made until the next C24 boot evidence is collected.",
        "- Prepared flash scope: `super`, `vbmeta_system_a`; builder never communicates with a device.",
        "", "| Image | Bytes | SHA-256 |", "|---|---:|---|",
    ]
    report += [f"| `{name}` | {entries[name]['bytes']} | `{entries[name]['sha256']}` |"
               for name in IMAGE_NAMES]
    (C24_DIR / "BUILD_REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8", newline="\n")
    print(f"[C24] Build complete: {C24_IMAGES}", flush=True)
    for name in IMAGE_NAMES:
        print(f"  {name}: {entries[name]['bytes']} bytes SHA256={entries[name]['sha256']}", flush=True)


if __name__ == "__main__":
    main()
