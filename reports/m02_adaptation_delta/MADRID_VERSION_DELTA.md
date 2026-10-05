# Madrid Official OS4.0.15 → OS4.0.19 version delta

Updated: 2026-10-05 20:05 HKT
Definition: `VERSION_DELTA = Madrid Official 4.0.19 − Madrid Official 4.0.15`.

Both sources are `madrid`, XEOCNXM, Android 17 / SDK 37. The 4.0.15 OTA payload was hash-verified against its embedded `FILE_HASH`; 4.0.19 is the existing M00 official payload extraction. The two releases use the same internal build naming scheme. Exact manifests: `work/m02_delta_exact/official_415_vs_official_419/`.

## Partition and tree changes

| Partition | 4.0.15 payload image bytes | 4.0.19 payload image bytes | Exact tree delta | Notes |
| --- | ---: | ---: | --- | --- |
| `system` | 977,055,744 | 977,055,744 | 0 added / 0 removed / 219 modified | Same EROFS filesystem block count; only one APEX path changed. |
| `system_ext` | 817,618,944 | 817,614,848 | 0 / 0 / 60 modified | 56 `lib/lib64`, 3 `etc`, 1 `bin`; same partition content family. |
| `product` | 5,667,659,776 | 5,667,659,776 | 0 / 0 / 1 modified | Only `etc/build.prop`; no product APK changed. |
| `mi_ext` | 173,858,816 | 173,858,816 | 0 / 0 / 1 modified | Only `etc/build.prop`. |
| `vendor` | 1,512,136,704 | 1,512,136,704 | Image SHA differs | Madrid vendor is not selected for M02; retain Known-Good thyme vendor. No 4.15→4.19 vendor tree diff was needed for the selected rebase. |
| `odm` | 5,976,264,704 | 5,976,252,416 | Image SHA differs | Do not import either Madrid ODM into thyme. |
| `system_dlkm` | 8,949,760 | 8,949,760 | Image SHA differs | Official modules carry 6.18.21 vermagic and are omitted from the 4.19.325 thyme stack. |
| `vendor_dlkm` | 78,315,520 | 78,315,520 | Image SHA differs | Official modules carry 6.18.21 vermagic and are omitted. |
| `boot`, `vendor_boot`, `dtbo`, `vbmeta`, `vbmeta_system` | hashes differ by release | hashes differ by release | Device-side transplant is excluded | Keep the A-validated Known-Good thyme boot/AVB bundle. |

## User-space change profile

- **APEX:** 36 system APEX/CAPEX files exist in both builds. Only `system/apex/com.android.virt.apex` changes; the other 35 are byte-identical.
- **Native/framework libraries:** system has 219 modified paths; 142 are grouped as system-level paths, 48 media, 17 display, 7 thermal/power, 4 network, 1 APEX. system_ext has 56 `lib/lib64` files, one binary (`bin/misight`) and three `etc` files changed.
- **system_server:** no `services.jar` path changes between official 4.0.15 and 4.0.19. The Known-Good-vs-Official 4.0.15 `services.jar` adaptation remains a distinct path and is preserved.
- **Product APKs:** no product APK changes in this exact 4.15→4.19 tree delta. `product/etc/build.prop` is the only product path that changes.
- **VINTF / policy / init:** no VINTF manifest, SELinux mapping/policy, or init rc path changed in the exact four rebased partitions. System's version delta does update `libselinux.so.tango` and `libvintf.so.tango`; these are libraries, not SELinux policy/VINTF manifests.
- **Release property rebase:** product build.prop release keys change to OS4.0.19 (build description/date/UTC/host/UUID/incremental and product fingerprint/date/UUID/incremental). Preserve Known-Good thyme values such as density 440, scheduler/affinity/minfree tuning, crypto state, and other device settings. In `mi_ext/etc/build.prop`, take the four 4.0.19 incremental/SMR version keys while retaining `ro.product.mod_device=thyme`.

## Candidate application rule

Use the Known-Good tree as the adaptation-bearing base, then overlay the exact Official 4.0.19 modified-file set from `system` and `system_ext`. Those two path sets have zero intersection with the Known-Good adaptation paths. Preserve Known-Good `product`, `vendor`, `odm`, and `mi_ext`; manually merge only the Official 4.0.19 release identity keys into `product` and `mi_ext` build.prop. This carries the actual version delta without replacing thyme hardware content.

`vendor` and `odm` image hashes change between official releases, but those Madrid hardware images are intentionally not part of the thyme rebase. The M02 file-level version delta is therefore scoped to selected platform partitions plus image-level identity records for excluded partitions.
