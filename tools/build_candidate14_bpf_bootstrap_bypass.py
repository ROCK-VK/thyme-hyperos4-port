#!/usr/bin/env python3
"""Build a minimal C14 boot-progress variant from the verified C13 baseline.

Only two init trigger blocks are changed:
* system/etc/init/netbpfload.rc no longer executes bpfloader/netd1shot; it sets
  bpf.progs_loaded=1 and starts netd so init can continue on the 4.19 kernel.
* system_ext/etc/init/hyper_bpfloader.rc no longer runs the second BPF loader.

The C13 SELinux policy, filesystem configuration, and all other LP images are
preserved. This is a host-side build only; it never invokes adb or fastboot.
"""

from __future__ import annotations

import hashlib
import json
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path("[LOCAL_PROJECT_ROOT]")
C13_DIR = ROOT / "work/stage_c_thyme_os4_candidate_13_treble_ion_fix/images"
C14_DIR = ROOT / "work/stage_d_thyme_os4_candidate_14_bpf_bootstrap_bypass_run5"
IMAGES_DIR = C14_DIR / "images"

WSL_ROOT = "/path/to/thyme-os4-local"
WSL_STAGE = "/path/to/thyme-os4-build/c14_bpf_bootstrap_20260926_run5"
WSL_C14_IMAGES = f"{WSL_ROOT}/work/stage_d_thyme_os4_candidate_14_bpf_bootstrap_bypass_run5/images"
C7_SYSTEM = "/path/to/thyme-os4-build/c7_stage/system_sar_avb.img"
C13_EXT_TREE = "/path/to/thyme-os4-build/c13_build_stage/system_ext_tree"
C1_BASE = "/path/to/thyme-os4-build/thyme_xiaomi15_os4_first_boot_candidate_1"
FSCK = f"{WSL_ROOT}/tools/erofs-utils/wsl/fsck.erofs"
DUMP = f"{WSL_ROOT}/tools/erofs-utils/wsl/dump.erofs"
MKFS = f"{WSL_ROOT}/tools/erofs-utils/wsl/mkfs.erofs"
LPMAKE = f"{WSL_ROOT}/tools/android-tools-static/linux/android-tools-static/lpmake"
SIMG2IMG = f"{WSL_ROOT}/tools/android-tools-static/linux/android-tools-static/simg2img"
LPDUMP = f"{WSL_ROOT}/tools/android-tools-static/linux/android-tools-static/lpdump"
AVBTOOL = f"{WSL_ROOT}/tools/bootimg/avbtool.py"

DEVICE_SIZE = 9_126_805_504
ALIGNMENT = 1_048_576
SYSTEM_SIZE = 1_092_616_192
SYSTEM_EXT_SIZE = 942_669_824
SALT = "c5ffc2c51fef1864ad27e6903e582f52611121819811b66eb40f6ea9b60350c5"
SYSTEM_UUID = "[REDACTED_DEVICE_ID]-8f73-4e28-aefe-8ee48d2d8b41"
SYSTEM_EXT_UUID = "[REDACTED_DEVICE_ID]-9266-550f-9093-74a7abd8693f"


def q(value: str) -> str:
    return shlex.quote(value)


def safe_print(value: str) -> None:
    try:
        print(value, end="" if value.endswith("\n") else "\n")
    except UnicodeEncodeError:
        encoding = sys.stdout.encoding or "utf-8"
        repaired = value.encode(encoding, errors="backslashreplace").decode(encoding, errors="replace")
        print(repaired, end="" if repaired.endswith("\n") else "\n")


def run_wsl(command: str) -> str:
    safe_print(f"[WSL] {command}")
    result = subprocess.run(
        ["wsl", "-d", "Ubuntu", "-e", "bash", "-lc", command],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    if result.stdout:
        safe_print(result.stdout)
    if result.stderr:
        safe_print(result.stderr)
    if result.returncode:
        raise RuntimeError(f"WSL command failed ({result.returncode}): {command}")
    return result.stdout


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def main() -> None:
    if C14_DIR.exists():
        raise FileExistsError(f"Refusing to overwrite existing Candidate 14 directory: {C14_DIR}")
    for name in ("boot.img", "vendor_boot.img", "dtbo.img", "vbmeta.img", "vbmeta_system.img", "super.img", "system_ext_c13.img"):
        if not (C13_DIR / name).is_file():
            raise FileNotFoundError(C13_DIR / name)

    C14_DIR.mkdir(parents=True, exist_ok=False)
    IMAGES_DIR.mkdir()
    unchanged = ("boot.img", "vendor_boot.img", "dtbo.img", "vbmeta.img")
    for name in unchanged:
        shutil.copy2(C13_DIR / name, IMAGES_DIR / name)
        if sha256(C13_DIR / name) != sha256(IMAGES_DIR / name):
            raise RuntimeError(f"Unchanged C13 image copy mismatch: {name}")

    stage = q(WSL_STAGE)
    system_tree = q(f"{WSL_STAGE}/system_tree")
    ext_tree = q(f"{WSL_STAGE}/system_ext_tree")
    c7_system = q(C7_SYSTEM)
    c13_ext_tree = q(C13_EXT_TREE)
    c14_images = q(WSL_C14_IMAGES)

    setup = f"""
set -euo pipefail
test ! -e {stage}
mkdir -p {stage}
{q(FSCK)} --extract={system_tree} {c7_system}
cp -a {c13_ext_tree} {ext_tree}
python3 - <<'PY'
from pathlib import Path
import stat

stage = Path({WSL_STAGE!r})
tree = stage / 'system_tree'
source = Path({C1_BASE!r}) / 'configs_retained/system/fs_config'
target = stage / 'system_fs_config_c14'
lines = source.read_text(encoding='utf-8').splitlines()
rebased = []
for line in lines:
    fields = line.split(maxsplit=1)
    if not fields:
        rebased.append(line)
        continue
    path = fields[0]
    if path == '/':
        rebased.append(line)
    else:
        rebased.append('system/' + path.lstrip('/') + (' ' + fields[1] if len(fields) > 1 else ''))
known = {{line.split()[0].lstrip('/') for line in rebased if line.strip() and not line.lstrip().startswith('#')}}
added = []
for entry in sorted(tree.rglob('*'), key=lambda p: p.relative_to(tree).as_posix()):
    path = 'system/' + entry.relative_to(tree).as_posix()
    if path in known:
        continue
    st = entry.lstat()
    added.append(f'{{path}} {{st.st_uid}} {{st.st_gid}} {{stat.S_IMODE(st.st_mode):04o}}')
    known.add(path)
target.write_text(chr(10).join(rebased + added) + chr(10), encoding='utf-8')
print('Supplemental SAR root fs_config entries:')
print(*added, sep=chr(10))
PY
"""
    run_wsl(setup)

    patch_cmd = f"""
set -euo pipefail
python3 - <<'PY'
from pathlib import Path

stage = Path({WSL_STAGE!r})
system = stage / 'system_tree/system/etc/init/netbpfload.rc'
hyper = stage / 'system_ext_tree/etc/init/hyper_bpfloader.rc'

text = system.read_text(encoding='utf-8')
start_marker = 'on load-bpf-programs\\n'
end_marker = '\\n# Note: This will actually execute'
assert text.count(start_marker) == 1, 'Expected one netbpfload event action'
start = text.index(start_marker)
end = text.index(end_marker, start)
replacement = '''on load-bpf-programs
    # Candidate 14: bypass the Android 25Q2 BPF loader requirement on the
    # thyme 4.19 kernel so init can proceed to later boot stages.
    setprop bpf.progs_loaded 1
    start netd
'''
text = text[:start] + replacement + text[end:]
assert 'exec_start bpfloader' not in text
assert 'wait_for_prop bpf.progs_loaded 1' not in text
assert 'exec_start netd1shot' not in text
assert text.count('setprop bpf.progs_loaded 1') == 1
system.write_text(text, encoding='utf-8', newline='\\n')

text = hyper.read_text(encoding='utf-8')
start_marker = 'on load-bpf-programs\\n'
end_marker = '\\n# Start bpf monitor'
assert text.count(start_marker) == 1, 'Expected one HyperOS BPF event action'
start = text.index(start_marker)
end = text.index(end_marker, start)
text = text[:start] + '# Candidate 14: skip hyper_bpfloader on the 4.19 bring-up kernel.\\n' + text[end:]
assert 'exec_start hyper_bpfloader' not in text
hyper.write_text(text, encoding='utf-8', newline='\\n')
print('patched system netbpfload.rc and system_ext hyper_bpfloader.rc')
PY
"""
    run_wsl(patch_cmd)

    raw_system = q(f"{WSL_STAGE}/system_c14.raw.erofs")
    avb_system = q(f"{WSL_STAGE}/system_c14.img")
    raw_ext = q(f"{WSL_STAGE}/system_ext_c14.raw.erofs")
    avb_ext = q(f"{WSL_STAGE}/system_ext_c14.img")
    configs = f"{C1_BASE}/configs_retained"
    system_fs_config = q(f"{WSL_STAGE}/system_fs_config_c14")
    build_erofs = f"""
set -euo pipefail
{q(MKFS)} -zlz4hc -T 0 -U {SYSTEM_UUID} --mount-point=/system \\
  --fs-config-file={system_fs_config} \\
  --file-contexts={q(configs + '/system/file_contexts')} {raw_system} {system_tree}
{q(FSCK)} -d0 {raw_system}
{q(MKFS)} -zlz4hc -T 0 -U {SYSTEM_EXT_UUID} --mount-point=/system_ext \\
  --fs-config-file={q(configs + '/system_ext/fs_config')} \\
  --file-contexts={q(configs + '/system_ext/file_contexts')} {raw_ext} {ext_tree}
{q(FSCK)} -d0 {raw_ext}
"""
    run_wsl(build_erofs)

    static_checks = f"""
set -euo pipefail
{q(DUMP)} --cat --path=/system/etc/init/netbpfload.rc {raw_system} > {q(WSL_STAGE + '/netbpfload.c14.rc')}
{q(DUMP)} --cat --path=/etc/init/hyper_bpfloader.rc {raw_ext} > {q(WSL_STAGE + '/hyper_bpfloader.c14.rc')}
grep -F 'setprop bpf.progs_loaded 1' {q(WSL_STAGE + '/netbpfload.c14.rc')}
grep -F 'start netd' {q(WSL_STAGE + '/netbpfload.c14.rc')}
! grep -E 'exec_start bpfloader|wait_for_prop bpf.progs_loaded 1|exec_start netd1shot' {q(WSL_STAGE + '/netbpfload.c14.rc')}
! grep -E '^on load-bpf-programs|exec_start hyper_bpfloader' {q(WSL_STAGE + '/hyper_bpfloader.c14.rc')}
{q(DUMP)} --cat --path=/etc/selinux/system_ext_sepolicy.cil {raw_ext} | grep -F 'allow hal_keymaster ion_device'
{q(DUMP)} --cat --path=/etc/selinux/system_ext_sepolicy.cil {raw_ext} | grep -F 'allow hal_gatekeeper ion_device'
"""
    run_wsl(static_checks)

    add_footer = f"""
set -euo pipefail
cp {raw_system} {avb_system}
python3 {q(AVBTOOL)} add_hashtree_footer --image {avb_system} --partition_size {SYSTEM_SIZE} \\
  --partition_name system --hash_algorithm sha256 --salt {SALT} --algorithm NONE --do_not_generate_fec
cp {raw_ext} {avb_ext}
python3 {q(AVBTOOL)} add_hashtree_footer --image {avb_ext} --partition_size {SYSTEM_EXT_SIZE} \\
  --partition_name system_ext --hash_algorithm sha256 --salt {SALT} --algorithm NONE --do_not_generate_fec
test "$(stat -c %s {avb_system})" = {SYSTEM_SIZE}
test "$(stat -c %s {avb_ext})" = {SYSTEM_EXT_SIZE}
"""
    run_wsl(add_footer)

    vbmeta_code = f"""
set -euo pipefail
PYTHONPATH={q(WSL_ROOT + '/tools/bootimg')} python3 - <<'PY'
from pathlib import Path
from avbtool import Avb, ImageHandler, AvbHashtreeDescriptor

avb = Avb()
base = Path({WSL_ROOT + '/work/stage_c_thyme_os4_candidate_13_treble_ion_fix/images/vbmeta_system.img'!r})
system = Path({WSL_STAGE + '/system_c14.img'!r})
system_ext = Path({WSL_STAGE + '/system_ext_c14.img'!r})
out = Path({WSL_C14_IMAGES + '/vbmeta_system.img'!r})
_, _, old_descs, _ = avb._parse_image(ImageHandler(str(base)))
_, _, system_descs, _ = avb._parse_image(ImageHandler(str(system)))
_, _, ext_descs, _ = avb._parse_image(ImageHandler(str(system_ext)))
new_system = next(x for x in system_descs if isinstance(x, AvbHashtreeDescriptor) and x.partition_name == 'system')
new_ext = next(x for x in ext_descs if isinstance(x, AvbHashtreeDescriptor) and x.partition_name == 'system_ext')
replaced = set()
new_descs = []
for desc in old_descs:
    if isinstance(desc, AvbHashtreeDescriptor) and desc.partition_name == 'system':
        new_descs.append(new_system); replaced.add('system')
    elif isinstance(desc, AvbHashtreeDescriptor) and desc.partition_name == 'system_ext':
        new_descs.append(new_ext); replaced.add('system_ext')
    else:
        new_descs.append(desc)
assert replaced == {{'system', 'system_ext'}}, replaced
blob = avb._generate_vbmeta_blob(
    algorithm_name='NONE', key_path=None, public_key_metadata_path=None,
    descriptors=new_descs, chain_partitions_use_ab=None,
    chain_partitions_do_not_use_ab=None, rollback_index=0, flags=2,
    rollback_index_location=2, props=None, props_from_file=None,
    kernel_cmdlines=None, setup_rootfs_from_kernel=None, ht_desc_to_setup=None,
    include_descriptors_from_image=None, signing_helper=None,
    signing_helper_with_files=None, release_string=None,
    append_to_release_string=None, required_libavb_version_minor=0)
assert len(blob) <= 131072
blob += b'\\0' * (131072 - len(blob))
out.write_bytes(blob)
_, _, verify_descs, _ = avb._parse_image(ImageHandler(str(out)))
names = {{x.partition_name for x in verify_descs if isinstance(x, AvbHashtreeDescriptor)}}
assert {{'product', 'system', 'system_ext'}} <= names, names
print('C14 vbmeta_system descriptors:')
for x in verify_descs:
    if isinstance(x, AvbHashtreeDescriptor):
        print(x.partition_name, x.image_size, x.root_digest.hex())
PY
"""
    run_wsl(vbmeta_code)

    super_sparse = q(f"{WSL_STAGE}/super_c14_sparse.img")
    super_raw = q(f"{WSL_STAGE}/super_c14_raw.img")
    base = C1_BASE
    lpmake_cmd = f"""
set -euo pipefail
{q(LPMAKE)} --metadata-size 65536 --metadata-slots 3 --device-size {DEVICE_SIZE} \\
  --block-size 4096 --alignment {ALIGNMENT} --virtual-ab --sparse --super-name super \\
  --group qti_dynamic_partitions_a:{DEVICE_SIZE} --group qti_dynamic_partitions_b:{DEVICE_SIZE} \\
  --partition mi_ext_a:readonly:202375168:qti_dynamic_partitions_a --partition mi_ext_b:none:0:qti_dynamic_partitions_b \\
  --partition odm_a:readonly:36700160:qti_dynamic_partitions_a --partition odm_b:none:0:qti_dynamic_partitions_b \\
  --partition product_a:readonly:4387241984:qti_dynamic_partitions_a --partition product_b:none:0:qti_dynamic_partitions_b \\
  --partition system_a:readonly:1092616192:qti_dynamic_partitions_a --partition system_b:none:0:qti_dynamic_partitions_b \\
  --partition system_ext_a:readonly:942669824:qti_dynamic_partitions_a --partition system_ext_b:none:0:qti_dynamic_partitions_b \\
  --partition vendor_a:readonly:1510998016:qti_dynamic_partitions_a --partition vendor_b:none:0:qti_dynamic_partitions_b \\
  --image mi_ext_a={q(base + '/super/avb_images/mi_ext.img')} \\
  --image odm_a={q(base + '/provider_images/odm.img')} \\
  --image product_a={q(base + '/super/avb_images/product.img')} \\
  --image system_a={avb_system} --image system_ext_a={avb_ext} \\
  --image vendor_a={q(base + '/provider_images/vendor.img')} --output {super_sparse}
{q(SIMG2IMG)} {super_sparse} {super_raw}
{q(LPDUMP)} {super_raw} > {q(WSL_STAGE + '/lpdump_c14.txt')}
grep -q 'system_a' {q(WSL_STAGE + '/lpdump_c14.txt')}
grep -q 'system_ext_a' {q(WSL_STAGE + '/lpdump_c14.txt')}
grep -q 'product_a' {q(WSL_STAGE + '/lpdump_c14.txt')}
cp {super_sparse} {c14_images}/super.img
"""
    run_wsl(lpmake_cmd)

    manifest = {
        "candidate": "Candidate 14 BPF bootstrap bypass",
        "base": "Candidate 13",
        "changes": [
            "system/etc/init/netbpfload.rc: skip bpfloader and netd1shot; set bpf.progs_loaded=1; start netd",
            "system_ext/etc/init/hyper_bpfloader.rc: skip hyper_bpfloader trigger",
        ],
        "unchanged_from_c13": list(unchanged),
        "flash_scope_prepared": ["vbmeta_system_a", "super"],
        "images": {},
    }
    for path in sorted(IMAGES_DIR.iterdir()):
        if path.is_file():
            manifest["images"][path.name] = {"bytes": path.stat().st_size, "sha256": sha256(path)}
    (IMAGES_DIR / "BUILD_MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
