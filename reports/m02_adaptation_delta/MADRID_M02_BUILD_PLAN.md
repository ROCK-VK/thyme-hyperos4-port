# MADRID-M02 build plan

Updated: 2026-10-05 21:52 HKT
Goal: Madrid Official OS4.0.19 platform user space + proven thyme adaptation/runtime stack.

## Composition

1. **Keep exact Known-Good boot bundle:** `boot_noroot`, `vendor_boot`, `dtbo`, `vbmeta`, `vbmeta_system`; hashes are in `KNOWN_GOOD_BOOT_STACK.md`. Preserve the 4.19.325-cxk kernel and its thyme DTB/ramdisk behavior.
2. **`system`:** start with Known-Good system tree; overlay the 219 changed files from Official 4.0.19. Preserve the two SELinux mapping additions plus Known-Good `init.rc` and `services.jar`. The file-path intersection is zero.
3. **`system_ext`:** start with Known-Good system_ext; overlay the 60 changed files from Official 4.0.19. Preserve VNDK30, its SELinux mapping files, Known-Good VINTF manifest and the Known-Good modified framework files. The path intersection is zero.
4. **`product`:** start with the whole Known-Good thyme product tree (the known-good EROFS extent is about 1.451 GB smaller than Official 4.0.19 product). Merge Official 4.0.19 release identity keys into `etc/build.prop`; retain thyme density, scheduler, affinity and memory tuning.
5. **`vendor`, `odm`:** copy Known-Good thyme image bytes without modification.
6. **`mi_ext`:** copy/rebuild the Known-Good thyme/hybrid tree and merge only Official 4.0.19 release keys; keep `ro.product.mod_device=thyme`.
7. **Omit:** Official Madrid `system_dlkm`, `vendor_dlkm`, `mi_product`, Madrid vendor/ODM, all firmware. The modules target 6.18.21; the proven stack runs 4.19.325 and its fstab does not mount DLKM.
8. **`super`:** build a 9,126,805,504-byte A-slot-only dynamic partition image containing `mi_ext_a`, `odm_a`, `product_a`, `system_a`, `system_ext_a`, `vendor_a`. Preserve known-good boot partition layout; no B-slot write.

## Property merge allowlist

- `product/etc/build.prop`: take 4.0.19 `ro.build.description`, build date/UTC, host, UUID, incremental, and product fingerprint/date/UUID/incremental values. Keep all Known-Good thyme-specific settings, including `ro.sf.lcd_density=440`, `persist.miui.density_v2=440`, `ro.miui.affinity.*`, scheduler/minfree settings, device identity and boot-environment values. Do not replace the file wholesale.
- `mi_ext/etc/build.prop`: update only `ro.build.version.incremental`, `ro.build.version.smr_baseversion`, `ro.mi.os.version.incremental`, and `ro.product.build.version.incremental`; preserve `ro.product.mod_device=thyme`.
- Record before/after values and file hashes in candidate metadata.

## Measured candidate r3 size

| Partition | Proposed allocation basis |
| --- | ---: |
| `system_a` | Rebuilt EROFS: 959,004,672 B |
| `system_ext_a` | Rebuilt EROFS incl. VNDK30: 849,969,152 B |
| `product_a` | Rebuilt EROFS after property merge: 4,109,991,936 B |
| `vendor_a` | Known-Good ext4 image: 2,044,887,040 B |
| `odm_a` | Known-Good ext4 image: 2,351,104 B |
| `mi_ext_a` | Known-Good ext4 image: 174,723,072 B |
| **LP-reported populated A extents** | **8,140,926,976 B** |
| **Physical super** | **9,126,805,504 B**; sparse image: 8,063,690,032 B |
| **Raw physical capacity minus extents** | **985,878,528 B**, before separately accounting LP reservations/alignment |

These are measured candidate values, not a projection. `lpmake` produced a sparse super that expands to exactly the 9,126,805,504-byte thyme physical target. AOSP `lpdump` and the independent LP parser agree on all partition sizes, both LP metadata checksums validate, and B-slot extents are empty. The candidate validator reports 985,878,528 B raw capacity minus the six A-slot extents; this residual is not claimed as wholly allocatable after metadata reservations. See `SUPER_SIZE_BUDGET.md`.

## Candidate build status

`MADRID-M02` candidate r3 exists at `work/madrid_m02_candidate_r3/`. Its complete image inventory, SHA256 list, LP reports, AVB/header reports, property merge reports and round-trip comparisons are in `metadata/`. `metadata/STATIC_GATE_REPORT.json` records `passed=true`, 12 images, all three EROFS round-trips at zero differences, and no gate errors. The candidate has not been flashed or boot-tested. Device staging is a separate step and must stop in Bootloader Fastboot before the one-time first-boot checkpoint.

## Build and static acceptance gates

- Build all selected EROFS filesystems with source file contexts/fs_config; preserve uid/gid, mode, symlink targets and capabilities. No filesystem labels may be inferred from FUSE `errno 61` omissions.
- Compare rebuilt file trees against the intended merged manifests; require no unexpected added/removed/modified file, symlink, owner, mode or readable label.
- Run EROFS fsck/stat checks on each rebuilt image; record block counts, file-data bytes and image hashes.
- Verify both build.prop merges against the explicit allowlist.
- Generate LP metadata; parse it with `lpdump` and independent parser, validate A-slot names/extents/filesystem magic, 1 MiB alignment and group limits; require total image <= 9,126,805,504 B with documented margin.
- Verify exact frozen boot-stack hashes, known-good vbmeta flags/descriptors, super image size/hash, and full candidate inventory.
- Preserve original Known-Good assets. `tools/restore_known_good_madrid_4_0_15.ps1` remains the recovery path; its default is dry-run and it does not reboot.

## Device staging after build

- Device write plan: active slot A only — `boot_a`, `vendor_boot_a`, `dtbo_a`, `super`, `vbmeta_a`, `vbmeta_system_a` — plus clean `userdata` and `metadata` for the first OS4.0.19 base. Do not write firmware, B slot, FRP, persist, modemst, EFS/NV, calibration or identity partitions; never relock.
- Require local image SHA/size, product `thyme`, bootloader Fastboot, unlocked state, active slot A and target partition sizes to pass before any write. Clean data only after the candidate images/static gates have all passed.
- Completed for candidate r3: six image flashes, `erase userdata`, `erase metadata`, and `set_active a` all returned exit 0. Post-check is `thyme`, slot A, unlocked, Bootloader Fastboot, A not unbootable, retry budget 7, device online. See `MADRID_M02_STAGING_REPORT.md`.
- **Do not reboot in the build/staging workflow.** The phone is stopped at the only human checkpoint: wait for “开始启动 MADRID-M02”.
- First boot: monitor USB/ADB/Fastboot and the user's screen. Stop after the first clear failure for RAM diagnostics; on progress or ADB, keep Android running and collect bounded runtime evidence.
