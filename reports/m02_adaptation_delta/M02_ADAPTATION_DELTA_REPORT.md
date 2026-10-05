# M02 adaptation delta report

Updated: 2026-10-05 21:52 HKT

## Result

The user-provided exact Official Madrid `OS4.0.15.0.XEOCNXM` recovery OTA is present as an extracted directory. Its `payload.bin` size and SHA256 match the OTA's embedded size/hash; `pre-device=madrid`, Android 17 / SDK 37, and the internal build ID is consistent with the already-audited 4.0.19 package naming scheme. The full original ZIP is absent, so ZIP-level MD5/size are not claimed as verified. The payload was extracted once into 66 partition images and inventoried.

The Known-Good package's true thyme adaptation is now separated from the Madrid 4.0.15 base at file-path/hash level for `system`, `system_ext`, `product`, `vendor`, `odm`, and `mi_ext`. Official 4.0.15→4.0.19 file deltas are available for `system`, `system_ext`, `product`, and `mi_ext`, the partitions selected for the platform rebase. The only exact overlap is the `product` and `mi_ext` `etc/build.prop` files; both receive key-level manual merges.

## Candidate source strategy

The candidate was built offline as `work/madrid_m02_candidate_r3/`. It overlays the exact Official 4.0.19 modified-file sets for `system` (219 paths) and `system_ext` (60 paths), retains the Known-Good product/vendor/odm/mi_ext adaptation, and reuses the tested boot/vendor_boot/dtbo/vbmeta/vbmeta_system stack. Madrid firmware, Madrid vendor/odm, the 6.18.21 DLKM and the unmounted empty `mi_product` stub are omitted. The candidate passes its static gates; device staging and runtime remain pending.

Evidence supporting this route:

- A-level Known-Good Android framework/UI boot with kernel `4.19.325-cxk-lxsclnb-g33d88af64048`, ADB online, `sys.boot_completed=1`, active Tethering APEX/netd/INetd/BPF runtime, and no Madrid firmware flash.
- B/C-level exact OTA metadata/hash, image hashes, file-tree comparisons and build.prop key deltas.
- Official 4.0.19 version changes in platform trees do not collide with Known-Good adaptation paths in `system`/`system_ext`; no `system_server` JAR, product APK, VINTF manifest, SELinux policy or init rc path changes in Official 4.0.15→4.0.19.
- DLKM sample vermagic is 6.18.21; successful boot stack is 4.19.325 and lacks DLKM mounts.

## Constraints and unknowns

- EROFS FUSE could not expose most SELinux xattrs (`errno 61`). Missing values remain unknown; the build must preserve source `fs_config` / file-context metadata.
- Official Madrid 4.0.19 `vendor` and `odm` hashes differ from 4.0.15, but their trees are excluded from the thyme candidate; the 4.15→4.19 tree delta for those excluded images was not expanded.
- M02 runtime compatibility of the 4.0.19 platform libraries with Known-Good 4.19.325 kernel and A13-derived thyme vendor is not yet tested. The file deltas show where the version changed; they cannot replace the next controlled runtime boot.
- Candidate r3 EROFS sizes, LP metadata checksums and A-slot extents are now measured and pass static validation; see `M02_CANDIDATE_BUILD_REPORT.md` and `SUPER_SIZE_BUDGET.md`. Candidate runtime compatibility with Official 4.0.19 is still unknown.

## Device status

MADRID-M02 candidate r3 passed its offline static gates and was staged successfully to A/shared partitions. Both data clean commands returned `OKAY`; the phone remains in Bootloader Fastboot on slot A with retry budget 7. No formal candidate reboot/boot has occurred. Detailed result: `MADRID_M02_STAGING_REPORT.md`.

Next: stop at the unique first-boot checkpoint and wait for `开始启动 MADRID-M02`. Runtime compatibility remains unverified until that explicit start instruction.
