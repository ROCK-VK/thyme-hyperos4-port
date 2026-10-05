# Known-Good Madrid 4.0.15 → Thyme boot stack

Frozen: 2026-10-05. This is the baseline already proven on the project Xiaomi 10S; M02 must preserve it unless later device evidence shows a boot-stack change is necessary.

## Immutable image assets

Source: community Known-Good package `BB解密-261002_移植Mi18pm-_HyperOS_4.0.15-for_thyme_A17\images`. Hashes were rechecked locally by `tools\restore_known_good_madrid_4_0_15.ps1` dry-run.

| Component | File | Bytes | SHA256 | Restore target |
| --- | --- | ---: | --- | --- |
| boot | `boot_noroot.img` | 134,217,728 | `B059E885DAAA11F0032E05FF5B16C7EE6A13D84B8CDBD51033AC2B4999C3FA0F` | `boot_a` |
| vendor_boot | `vendor_boot.img` | 100,663,296 | `ED5391F9AD2BE11A0636657968972D005600658C45FF631E5462CE9779840B07` | `vendor_boot_a` |
| dtbo | `dtbo.img` | 33,554,432 | `A0F550A32C15B95A6BA0BBE141976BAD905D23FC74367E3E3FF0F41BC90C6D3A` | `dtbo_a` |
| super | `super.img` | 9,126,805,504 | `D05DC8DFDD7DCD54A319D0051BDD1BB9942F3E162C52B2272DFC585E0B314496` | `super` |
| vbmeta | `vbmeta.img` | 4,096 | `D2E1979739EC67076A90B0FC625DAE84A1AA2ED72D05D2B55D52539E3462B442` | `vbmeta_a` |
| vbmeta_system | `vbmeta_system.img` | 4,096 | `D2E1979739EC67076A90B0FC625DAE84A1AA2ED72D05D2B55D52539E3462B442` | `vbmeta_system_a` |

## Boot internals

| Item | Frozen observation | Evidence |
| --- | --- | --- |
| Runtime kernel | `4.19.325-cxk-lxsclnb-g33d88af64048` | A-level M01-R3 runtime: `uname -a`, device remained online, `sys.boot_completed=1` |
| Kernel image | 47,185,936 bytes; SHA256 `B9D1E524B3AED85C7D3F19DBD900A0E291EC9310A3B36DC47ADDAA29D20C621C` | Local extracted kernel from the already-unpacked Known-Good boot image |
| Kernel built-in command line | `cgroup_disable=pressure ramoops_memreserve=4M` | Existing extracted Known-Good kernel config (`CONFIG_CMDLINE`); effective `/proc/cmdline` was denied to the production shell and remains unconfirmed |
| Boot ramdisk | 50,637,560-byte gzip payload; expanded CPIO 99,590,400 bytes. Existing M00 analysis identifies it as TWRP-derived recovery ramdisk with first-stage super mounting responsibility. | Existing unpack and `THYME_SUCCESS_REFERENCE_ARCHITECTURE.md` |
| Ramdisk file manifest | `known_good_boot_stack/ramdisk-files.txt` (110,955 bytes); per-file hash manifest `known_good_boot_stack/ramdisk-files.sha256sum` (334,181 bytes), SHA256 `4C60B087B388CB9F273546E286F33C6054026C7C1C9656D220F64F7C9A063D46` | Copied from the already-existing unpack; not regenerated |
| vendor_boot ramdisk | 2,180 bytes (near-empty) | Existing `succ_vb` extraction |
| vendor_boot DTB | 1,613,832 bytes | Existing `succ_vb` extraction |
| vendor_boot bootconfig | No separate `bootconfig` component in the existing v3 extraction | Existing `succ_vb` tree contains `vendor_ramdisk` and `dtb`; do not confuse Official 4.0.19 bootconfig with this image |
| dtbo source | SHA256-equal to official thyme OS1.0.4.0 `dtbo.img` | M00 static comparison; current M01-R3 boot confirms the stack works together |

The success package uses an atypical split: the large TWRP-derived `boot` ramdisk mounts dynamic partitions, while `vendor_boot` has almost no ramdisk content. Keep `boot`, `vendor_boot`, and `dtbo` as a tested bundle. Do not transplant official Madrid boot/vbmeta images into a candidate by default.

## Device-level validation and constraints

- M01-R3 reached Android framework/UI, ADB `device`, and `sys.boot_completed=1`; the 900-second observation window completed with ADB still online.
- The running custom kernel banner matched the Known-Good image family.
- No Known-Good firmware was flashed; the device's pre-existing firmware stack was sufficient for this boot.
- Success `vbmeta` and `vbmeta_system` are both 4 KiB and share a SHA256 in this package.
- R3 erased `userdata` and `metadata` before boot; it did not rewrite this six-image stack.
- Raw ROMs and image binaries stay private. The public report contains only image metadata, hashes, and text manifests.

Evidence level: image details **B** (local hash/structure); successful boot, kernel, and runtime **A** (real device).
