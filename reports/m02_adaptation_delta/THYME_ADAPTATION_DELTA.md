# THYME adaptation delta: Madrid Official 4.0.15 → Known-Good port

Updated: 2026-10-05 20:05 HKT
Definition: `ADAPTATION_DELTA = Known-Good thyme port 4.0.15 − Official madrid 4.0.15`.

The comparison uses the exact `OS4.0.15.0.XEOCNXM` OTA supplied by the user. The OTA payload hash matches its embedded hash. Its original ZIP container was not present, so the listed ZIP MD5/size remain unchecked. Exact image and tree evidence is private under `work/reference_madrid_os4_0_15_official/` and `work/m02_tree_manifest/`.

## Content delta by partition

Counts are added / removed / modified content-or-type paths. Metadata-only changes are reported separately; they are not called content changes.

| Partition | Added | Removed | Modified content/type | High-value delta | Rebase treatment |
| --- | ---: | ---: | ---: | --- | --- |
| `system` | 2 | 0 | 2 | Adds `etc/selinux/mapping/30.0.cil` and `.compat.cil`; changes `etc/init/hw/init.rc` and `framework/services.jar`. | Preserve the four Known-Good changes; no Official 4.0.19 changed path intersects them. Runtime-test init/framework behavior. |
| `system_ext` | 3 | 6 | 4 | Adds `com.android.vndk.v30.apex` (114,769,920 B) and two SELinux v30 mappings; removes the MiSightService tree; changes PowerKeeper, VINTF manifest, framework-ext-res and miui-services. | Preserve the VNDK30/mapping/VINTF/device compatibility changes. Keep the four modified baseline files pending runtime validation; no changed Official 4.0.19 path collides. |
| `product` | 27 | 159 | 17 | Adds `thyme.xml`, thyme display config, runtime permission, overlays/apps; removes Madrid device feature/display IDs and many preinstalled apps/data-app/media files; modifies overlays, apps, boot animation and build.prop. | Use Known-Good product tree; merge only OS4.0.19 release identity into build.prop. |
| `vendor` | 2,524 | 3,394 | 987 | Broad hardware stack replacement: HAL libraries/services, init rc, VINTF, device configs, display/power/thermal/audio/camera/network, firmware references and kernel modules. Another 429 same-path records are metadata-only. | Keep the whole Known-Good thyme ext4 image; no Madrid vendor graft. |
| `odm` | 4 | 2,859 | 10 | Madrid's multi-GB ODM is almost wholly absent from the 2.35 MB thyme ODM; identity and hardware config differ. Eight other same-path records are metadata-only. | Keep the Known-Good thyme image. |
| `mi_ext` | 0 content additions | 1 file removed | 1 file modified | The sole content modification is `etc/build.prop`; the removed file is Madrid `vendor/etc/cust_features/device_features.xml`. `lost+found` is an ext4 artifact. Another 179 of 180 reported path modifications are metadata-only. | Keep Known-Good filesystem/tree and thyme device identity; merge 4.0.19 version keys into build.prop. |

The `system_ext` removal count comprises six entries in the MiSightService tree. Product's removed set is dominated by preinstalled apps/data-app/media; its modified set includes the Madrid→thyme `etc/build.prop`, device overlays and device assets. Exact added/removed/modified CSV/JSON manifests are retained privately under `work/m02_delta_exact/official_415_vs_known_good/`.

## Hardware-layer identity evidence

- Known-Good runtime reached Android framework/UI and stayed online for 900 seconds; kernel was `4.19.325-cxk-lxsclnb-g33d88af64048` (A).
- Its vendor properties identify `thyme`, Mi 10S, board `thyme`, platform `kona`; the source comment identifies `device/xiaomi/thyme`. Its vendor contains 4.19 modules, thyme HALs, init rules and VINTF declarations (B).
- Known-Good ODM identifies model `M2102J2SC` / Mi 10S and occupies 2,351,104 bytes, versus Official Madrid ODM's roughly 5.86 GB filesystem (B).
- Known-Good `vendor`, `odm`, `mi_ext` are ext4; Official Madrid versions are EROFS. For `vendor` and `odm`, path/content manifests differ by thousands of entries (C).
- `mi_ext` is not purely thyme-origin: nearly all its file content matches Madrid 4.0.15; the port changes its device property, rebuilds it as ext4 and removes one Madrid vendor-feature file (B/C). It is therefore classified **HYBRID**, not wholly THYME_BASED.

## Delta interpretation

The proven adaptation is a whole hardware compatibility stack, not one or two system patches. The active M02 baseline must retain the exact tested boot bundle and the Known-Good thyme `vendor`, `odm`, `mi_ext`, plus the product/system compatibility changes. Firmware is excluded: M01-R3 booted without flashing any Known-Good firmware.

The EROFS FUSE manifests cannot expose most embedded SELinux xattrs (`errno 61`). File hashes, paths, sizes and readable metadata are valid; absent xattr values are unknown. Do not “repair” or drop labels by interpreting unavailable values as empty.
