# M03 Port Provenance and Method Report

Updated: 2026-10-06 HKT
Status: static provenance audit complete. MADRID-M02 r3 remains the running device build. No reboot, flash, root, remount, installation or device-file change was performed for this audit.

## Executive conclusion

The community Known-Good package already carries a complete Madrid OS4.0.15-to-thyme adaptation stack that has booted to Android framework on the project Xiaomi 10S. This project did not redo Android 17 hardware bring-up from scratch: it verified that baseline, separated the exact Madrid 4.0.15-to-4.0.19 donor delta, applied 219 system paths and 60 system_ext paths plus two controlled build.prop merges, rebuilt the selected EROFS/super layout, and confirmed MADRID-M02 r3 reaches sys.boot_completed=1.

The component matrix is also available as [PORT_PROVENANCE_MATRIX.md](PORT_PROVENANCE_MATRIX.md).

## Evidence and attribution rules

- A: direct runtime evidence from the Xiaomi 10S.
- B: local image/hash/boot structure evidence.
- C: exact file/tree comparison.
- D: inference or unresolved origin.
- “Original Porter” in this report means the adaptation and artifacts present in the shipped community package. It does not identify which individual authored, compiled or generated them.
- Static kernel configuration establishes available capabilities; it does not establish why the ROM boots. Runtime success establishes the selected bundle works together; it does not isolate one component as the cause.
- EROFS FUSE manifests could not read most SELinux xattrs. Missing xattr values are unknown, not empty labels.

## Corrected architecture diagram

<pre>
Official thyme OS1.0.4 reference
  4.19.157 baseline; exact dtbo match; some packaged firmware matches
                    │
                    └── Thyme hardware lineage evidence
                        vendor / odm / device HALs / configs / 4.19 modules
                                      │
                                      ▼
Official Madrid 4.0.15 ───────► Community Known-Good port 4.0.15 → thyme
  system / system_ext /           custom 4.19.325-cxk boot bundle
  product userspace base           TWRP-derived boot ramdisk; thyme DTB/dtbo
                                   adapted system_ext/product; six-partition A-only super
                                      │
                                      │ keep the tested boot and hardware stack
                                      ▼
Official Madrid 4.0.19 ───────► Our M02 rebase and image engineering
  exact version delta              219 system + 60 system_ext paths
                                   product + mi_ext release property merges
                                   EROFS rebuild + new LP/super metadata
                                   inherit, validate, do not regenerate vbmeta
                                      │
                                      ▼
                            MADRID-M02 r3 — OS4.0.19 → thyme
                                      │
                                      ▼
                   Real device: sys.boot_completed=1;
                   Known-Good kernel; Tethering/netd/BPF runtime present
</pre>

The graph shows provenance, not a proven step-by-step boot trace. The large recovery-derived boot ramdisk and near-empty vendor_boot suggest a nonstandard first-stage mount arrangement, but the live handoff was not captured. The A-level result proves the selected bundle boots as a whole.

## Four reference baselines

| Baseline | Verified identity and use |
| --- | --- |
| Thyme stock reference | Official thyme OS1.0.4.0.TGACNXM / Android 13 image set. Exact dtbo match and selected firmware matches were found. It is not proven to be the original porter's exact vendor source. |
| Madrid Official 4.0.15 | User-provided exact madrid OS4.0.15.0.XEOCNXM / Android 17 OTA. Payload identity/hash and extraction were verified in M02; the ZIP container itself was not retained for independent ZIP-level validation. |
| Community Known-Good 4.0.15 port | Madrid-derived Android 17 userspace plus thyme hardware/boot adaptation; M01-R3 reached Android framework boot on-device after userdata and metadata erase. |
| MADRID-M02 r3 | Exact 4.0.19 rebase of selected Known-Good trees and boot stack; M02 runtime reached sys.boot_completed=1 on the same device. |

## Table 1 — Component Provenance

| Component | Thyme Stock | Madrid Official | Original Porter | Our M02 |
| --- | --- | --- | --- | --- |
| boot / kernel | Official thyme reference kernel is 4.19.157, not the runtime kernel. | Android 17 Madrid kernel is 6.18.21 and is not used. | Package uses a 4.19.325-cxk kernel in a hybrid boot image. BPF_LSM, CGROUP_BPF, EROFS and Android vendor hooks are enabled in the inspected config. Exact source and compiler/author are unknown; classify as LIKELY_CUSTOM_BUILT, not CONFIRMED_COMPILED. | Reuses exact Known-Good boot_noroot image. M01-R3 and M02 runtime both report the same 4.19.325-cxk banner (A). |
| boot ramdisk | Stock image is a reference only. | Madrid boot v4 has no boot ramdisk; its vendor_boot carries the larger ramdisk set. | 50.6 MB gzip / 99.6 MB expanded ramdisk carries TWRP/recovery/sekaiacg/Magisk artifacts, recovery fstab/init and first_stage_ramdisk files. Its exact live mount/handoff sequence remains an inference. | Reused byte-for-byte; no M02 ramdisk edit. |
| vendor_boot / DTB | Known-Good contains a thyme DTB, but full vendor_boot differs from stock references. | Madrid vendor_boot v4 layout is not used. | v3 hybrid image with a 2,180-byte vendor ramdisk plus thyme DTB. Only the complete selected bundle is device-validated. | Exact Known-Good image retained. |
| dtbo | Exact hash match to official thyme OS1.0.4 dtbo (B). | Madrid dtbo differs and is not used. | Directly reuses the thyme dtbo. | Exact Known-Good dtbo retained. |
| vbmeta / vbmeta_system | Thyme OS1.0.4 images: SHA256_RSA2048, flags 0, signed descriptor data; embedded rollback indexes are 0 and 1,709,251,200 respectively. | Madrid 4.0.15/4.0.19 images use SHA256_RSA4096, flags 0 and signed descriptors. 4.0.19 embedded indexes are 0 and 1,788,220,800. | Both images are 4 KiB, Algorithm NONE, flags 2, and have no descriptors; both hashes are identical. AOSP defines flags bit 1 as VERIFICATION_DISABLED and bit 0 as HASHTREE_DISABLED. | Same two Known-Good images inherited and validated; M02 did not regenerate AVB images. |
| system | Not the Android 17 system/framework source. | Main Madrid/missi platform userspace base. | Versus exact 4.0.15: 2 policy-mapping additions and 2 modified files (init.rc, services.jar). | Rebased 219 official 4.0.19 changed paths; rebuilt EROFS. |
| system_ext | Not the Android 17 framework source. | Madrid platform base. | 3 additions, 6 removed path entries, 4 content changes. Includes VNDK30 and SELinux v30 mappings, changes around PowerKeeper/VINTF/framework resources/miui-services, and removes MiSightService entries. | Rebased 60 official 4.0.19 changed paths; rebuilt EROFS. |
| product | Thyme device configuration is a reference; exact stock file provenance is not established for the full tree. | Madrid product base and bundled apps/assets. | Hybrid product: adds thyme XML/display configuration/overlays/permissions/apps; removes 159 path entries and modifies 17. Regular-file comparison shows 92 removed files. The removed set includes large data-app APKs and media assets. | Keeps Known-Good product tree and merges 11 allowlisted 4.0.19 release keys while preserving thyme density/device settings; rebuilt EROFS. |
| vendor | Thyme/SM8250 hardware lineage is clear, but the full image was not proven byte-identical to OS1.0.4 vendor. | Madrid vendor is not used. | Thyme hardware layer: HALs, init rules, VINTF, device configs, policy and 4.19 modules. | Exact Known-Good vendor image retained. |
| odm | Thyme / Mi 10S identity and configuration; exact OS1.0.4 byte lineage not fully proven. | Multi-gigabyte Madrid odm is not used. | Compact thyme-based odm with Mi 10S identity/configuration. | Exact Known-Good odm image retained. |
| mi_ext | Carries thyme device identity, but is not purely thyme-origin. | Most regular-file content matches Madrid 4.0.15. | Hybrid: Madrid-derived contents, ext4 rebuild, thyme mod_device and one removed Madrid feature entry. 179 of 180 path metadata changes are not content changes. | Keeps the Known-Good tree; updates four version keys and preserves ro.product.mod_device=thyme. |
| system_dlkm / vendor_dlkm | The retained thyme vendor modules target the 4.19 stack. | Madrid modules report 6.18.21 vermagic. | Madrid DLKM absent from Known-Good. | Omitted because the selected kernel is 4.19.325 and the Known-Good layout has no DLKM mount. This is kernel compatibility, not only space trimming. |
| super / LP | Physical thyme super is 9,126,805,504 bytes. | Madrid partition footprint cannot be copied as-is into thyme super. | Six populated A-slot partitions; B extents empty. system/system_ext/product are EROFS; vendor/odm/mi_ext are ext4. | Generated sparse super is 8,063,690,032 bytes and expands to 9,126,805,504 bytes. Six A extents total 8,140,926,976 bytes. LP metadata validated by lpdump and an independent parser. |
| firmware | Exact OS1.0.4 matches include abl, dtbo and imagefv; other packaged firmware matches a later thyme OurSky OS3.0.318 bundle. | No Madrid firmware used. | Package includes a mixed thyme firmware bundle and its stock script would flash it. | No success firmware was flashed in M01-R3 or M02; the phone’s pre-existing firmware was sufficient for both proven boots. |
| optional root/recovery | Not part of the hardware provenance. | Not used. | Installer offers boot_noroot, boot_magisk, boot_alpha, boot_ksu and boot_apatch variants; Magisk and ReSukiSU APKs are add-ons. The selected boot image determines whether a rooted variant is used. | boot_noroot reused; M02 did not add root. Installing a manager APK alone does not convert the no-root boot image into a rooted boot. |
| SELinux | Exact cause/source not established. | Official policies were not wholly transplanted. | Ramdisk contains policy/context files; most EROFS SELinux xattrs were unreadable in the manifests. | Runtime reports Permissive, but ordinary-shell cmdline/bootconfig access was denied and no static source was attributed. Do not claim complete policy adaptation or that the porter intentionally disabled enforcement. |

The matching stock dtbo is direct provenance evidence. For vendor/odm, the current evidence establishes thyme lineage through identities, source comments, hardware contents and the exact comparison against Madrid; it does not establish every file's source in a specific stock HyperOS 1 build. The package's firmware is also mixed across thyme releases, and its presence in the package is not evidence it had to be flashed.

## Hardware subsystem coverage and evidence limits

The source report identifies the Known-Good vendor delta as a broad thyme hardware stack. This audit can establish package lineage and component classes, but it did not run feature tests for each HAL. The table separates static presence from real-device proof.

| Subsystem | Package/tree evidence | Runtime evidence and limit |
| --- | --- | --- |
| Display | Thyme display configuration and overlays were added in product; vendor carries thyme display/HAL configuration. | M02 reached an interactive Android framework UI on the device. This confirms a working display path to UI, not every panel mode, brightness curve or refresh feature. |
| Audio | The vendor delta includes thyme audio HAL/configuration classes. | No call, speaker, microphone or audio playback test was part of M03. |
| Camera | Camera-related vendor HAL/configuration is in the thyme hardware layer. | Camera capture/video was not tested in M01/M02 provenance work. |
| Wi-Fi / Bluetooth | Thyme vendor modules and firmware references are present; the packaged Bluetooth/radio firmware is from the thyme-side bundle, not Madrid. | No Wi-Fi association, Bluetooth pairing or data path was independently tested here. No package firmware was flashed for the successful boots. |
| Power / thermal | Vendor device configuration covers power/thermal classes; system_ext includes the Known-Good PowerKeeper change. | No sustained load, thermal throttling or battery behavior test. |
| Sensors / fingerprint / NFC | These belong to the thyme vendor/ODM hardware layer, rather than Madrid's SoC/device layer. Exact per-HAL source attribution was not established in this audit. | No sensor, fingerprint unlock or NFC feature test is claimed. |
| IR | The running system reports vendor.ir-hal-1-0 restarting. | Restart cause and user-visible impact remain unknown; this task did not fix or further diagnose it. |
| Keymaster / gatekeeper / vold | The package includes thyme-side TEE/keymaster firmware references and thyme vendor/ODM/init integration; clean-data boot confirms the basic system can start with this existing device stack. | No key operation, biometric authentication, encrypted-data migration or vold feature test is claimed. |
| Init / VINTF / SELinux | Thyme vendor carries init, VINTF and policy/configuration files; Known-Good system/system_ext add policy mappings. | The M02 runtime is Permissive, but its source is unproven. Most EROFS SELinux xattrs were unreadable; this is not evidence of complete enforcing-policy compatibility. |

## Table 2 — Original Porter Contribution

| Work present in the shipped port | Evidence | Type | Importance |
| --- | --- | --- | --- |
| Package carries a custom 4.19.325-cxk kernel used with this Android 17 userspace stack | Kernel banner and config are present; successful M01-R3 and M02 runtime use it. No kernel source tree, build log or attributable commit was found. | LIKELY_CUSTOM_BUILT; author/compiler unverified | BOOT_CRITICAL |
| Assemble a very large TWRP-derived boot ramdisk and a near-empty vendor_boot arrangement | 50.6 MB gzip ramdisk, recovery markers/init/fstab/first_stage files; vendor ramdisk is 2,180 B. Exact live mount sequence is inferred. | MODIFIED_REUSED | BOOT_CRITICAL |
| Provide thyme hardware compatibility images | thyme identity and contents in vendor/odm; HAL/init/VINTF/config/module set; exact stock OS1 file-by-file source not fully proved. | MODIFIED_REUSED | HARDWARE_CRITICAL |
| Reuse thyme dtbo and package mixed thyme firmware | dtbo hash equals official OS1.0.4; firmware hashes identify OS1.0.4 plus later OurSky OS3.0.318 sources. M01-R3 booted without flashing those firmware images. | REUSED | HARDWARE_CRITICAL for dtbo; OPTIONAL for packaged firmware |
| Adapt Madrid system_ext/product/mi_ext and compatibility mappings | Exact 4.0.15 tree delta shows mappings/VNDK30, thyme configs/overlays, content changes and removals. Motive for individual removed apps is not documented. | MODIFIED_REUSED | COMPATIBILITY |
| Fit the port into thyme dynamic partitions | Six A-only partitions, mixed EROFS/ext4, custom LP layout; Madrid DLKM absent. Exact image-generation script/tool provenance is not established. | GENERATED (layout/image structure confirmed; author/tool not proven) | SPACE_LAYOUT |
| Supply simplified no-chain vbmeta images and optional root boot variants | 4 KiB Algorithm NONE / flags 2 / no descriptors; BAT exposes five boot choices. | GENERATED (vbmeta structure); REUSED/MODIFIED variants | BOOT_CRITICAL for vbmeta policy; OPTIONAL for root |

No component meets CONFIRMED_COMPILED on the available evidence. The custom kernel is strong evidence of a custom binary, not proof the community port author compiled it.

## Table 3 — Our Contribution from M00 through M02

| Work | Evidence / result | Type | Importance |
| --- | --- | --- | --- |
| Correct the donor identity and establish exact release references | M00 verified the community port is Madrid OS4.0.15, not the previously assumed donor; exact 4.0.15 and 4.0.19 identities/hashes were inventoried. The user supplied the faster 4.0.15 download. | Static audit / provenance | COMPATIBILITY |
| Establish a real Known-Good baseline | M01-R1/R2 failures were preserved without inventing a root cause. M01-R3 cleared userdata and metadata and reached Android framework on the same device; 4.19.325-cxk ran, no success firmware was flashed, and Tethering/netd/BPF runtime was present. | Controlled experiment / runtime evidence | BOOT_CRITICAL |
| Separate adaptation delta from donor version delta | Exact 4.0.15 comparison; 4.0.15→4.0.19 changed paths isolated and conflict report created. | Differential analysis | COMPATIBILITY |
| Rebase the 4.0.19 release changes | Applied 219 system and 60 system_ext changed paths; merged 11 product release keys and 4 mi_ext version keys while preserving thyme configuration and identity. | Modified/rebased content | COMPATIBILITY |
| Rebuild M02 filesystems and super layout | Rebuilt system/system_ext/product EROFS and generated a six-partition A-only sparse super sized to the thyme physical target. Kept vendor/odm/boot stack from Known-Good; mi_ext content received only the controlled property merge. | GENERATED | SPACE_LAYOUT |
| Validate rather than claim an AVB rebuild | Reused Known-Good vbmeta and vbmeta_system hashes; checked AVB headers. Generated LP metadata and checked it with both lpdump and an independent parser. EROFS fsck and full round-trip gates passed. | Validation / generated LP metadata | BOOT_CRITICAL / SPACE_LAYOUT |
| Build reproducible tooling and recovery path | Added exact OTA inventory, tree/delta tools, property merge/overlay, EROFS/super build and validation, controlled flash tooling, and dry-run Known-Good restore script. | Engineering automation | COMPATIBILITY |
| Confirm M02 on hardware | One authorized boot reached ADB and sys.boot_completed=1 with OS4.0.19 fingerprint and the Known-Good kernel. Tethering APEX/netd/INetd/BPF were present. | Runtime validation | BOOT_CRITICAL |

## What Madrid Official contributes versus what remains Xiaomi Thyme

Madrid Official remains the source of most platform userspace: system, system_ext and much of product and mi_ext. M02 applies the exact 4.0.19 version delta without changing the tested boot/kernel or replacing thyme vendor/odm. The active hardware side remains thyme-specific: dtbo, the tested 4.19.325 boot bundle and the vendor/odm compatibility layer. The device's existing firmware remains unchanged.

The product partition shrink is measurable: Official 4.0.15 product image is 5,667,659,776 bytes; Known-Good is 4,110,647,296 bytes; M02 r3 is 4,109,991,936 bytes. The removed manifest includes large preinstalled APKs such as MiMediaEditor, MiShop, Health, MIUIMusicT, SmartHome and MIUIVideo, plus media such as bootanimation-back.zip. This proves what was removed and the resulting space reduction; it does not prove each item was removed because it was madrid-specific or hardware-incompatible.

## Approximate content share — not engineering effort

Denominator: regular-file sizes across the six selected M02 dynamic filesystem trees (system, system_ext, product, vendor, odm, mi_ext), approximately 10.572 GB and 13,047 regular files. This excludes image-container padding/compression, directories/symlinks/metadata, boot images, vbmeta/dtbo, firmware and removed files. Categories are assigned by final path/content provenance so counts do not double-count; byte weight counts the full final size of a changed file, not only the bytes that differ.

| Mutually exclusive content bucket | Approx. bytes | Byte share | Files | File share |
| --- | ---: | ---: | ---: | ---: |
| Madrid 4.0.15 content unchanged by port/M02 | 7.688 GB | 72.7% | 9,184 | 70.4% |
| Thyme hardware layer in vendor + odm (lineage, not per-file OS1 proof) | 2.026 GB | 19.2% | 3,538 | 27.1% |
| Known-Good port-added/modified content outside the two rebased build.prop paths | 605.8 MB | 5.7% | 44 | 0.34% |
| M02 4.0.19 changed/merged paths | 253.0 MB | 2.4% | 281 | 2.15% |
| Total | 10.572 GB | 100% | 13,047 | 100% |

If “Madrid Official content” means all Official-derived content including the files updated to 4.0.19, combine the first and fourth rows: about 75.1% of bytes and 72.5% of files. The 5.7% Known-Good change bucket is a changed-file weight, not proof those bytes were authored from scratch by the porter; some files may have been reused from thyme. File counts and byte counts describe package composition, not labor.

### Engineering criticality

- Original package: the boot/kernel, dynamic partition mount path, thyme vendor/odm and dtbo are the dominant boot/hardware-critical adaptation. Product pruning and the A-only super layout solve space/layout constraints. Optional root variants and packaged firmware are not required for the tested boot.
- Our M02: the work is substantial release rebase, image reconstruction, validation and reproducibility engineering. It is not a new kernel, HAL, or from-scratch Android 17 hardware bring-up.
- No defensible person-hour or “engineering effort percent” can be computed from file sizes/counts. A small boot-critical change may outweigh gigabytes of unchanged resources.

## Known limits and unverified items

- M01-R3 erased userdata and metadata together; it strongly correlates with Known-Good success but does not isolate which partition was decisive.
- M02 runtime was a single first boot to sys.boot_completed=1. Real tethering data transfer was not tested; vendor.ir-hal-1-0 restarting remains unexplained.
- M02 reports SELinux Permissive, but its source was not attributed. Do not describe this as full enforcing-policy adaptation or a confirmed porter shortcut.
- The exact original kernel source/compiler, exact stock OS1 vendor/odm file ancestry, and individual porter authorship remain unproven.
- The TWRP-derived ramdisk structure suggests the first-stage mount approach; a direct boot-time trace was not captured.
- The actual device rollback-fuse/RPMB state was not read. AVB image header indexes are not that state.

## 一句话结论

社区 Known-Good 包已经携带并在这台 thyme 上验证了一套可启动的 Madrid OS4.0.15 Android 17 适配栈；本项目没有重做硬件 bring-up，而是保留该适配栈，把 Official Madrid 4.0.19 的精确版本差分重基、重建并验证为 MADRID-M02，且已实机达到 sys.boot_completed=1。

### 原作者最关键的 5 项工作

1. 将 4.19.325-cxk kernel 纳入实际运行的 boot 组合（kernel 编译者与个人作者归属未确认）。
2. 将 TWRP-derived 的大型 recovery ramdisk 配入 boot，并采用近空 vendor_boot / thyme DTB 组织方式。
3. 构造 thyme vendor/odm 硬件兼容层：HAL、init、VINTF、设备配置、policy 和 4.19 modules。
4. 复用 thyme dtbo，并处理 Madrid system/system_ext/product/mi_ext 与 thyme 的兼容差异。
5. 将内容重排为适合 9.126 GB thyme super 的六分区 A-only 布局，并提供简化 vbmeta 与可选 root boot variants。

### 我们最关键的 5 项工作

1. M00 确认真正 donor 是 Madrid OS4.0.15，并取得精确官方 4.0.15 / 4.0.19 参考。
2. M01 受控验证 Known-Good；失败轮次保留现场，R3 clean data/metadata 后取得首次成功 Android framework boot 证据。
3. 精确分离 Official 4.0.15 adaptation delta 与 4.0.19 version delta，形成 provenance、冲突与容量报告。
4. 将 219 个 system、60 个 system_ext 官方变更和两处分区 build.prop 合并应用到已验证基线；重建 EROFS 与 A-only super/LP metadata。
5. 建立 hash、EROFS round-trip/fsck、LP 双解析器、property gates、受控 flash 与 Known-Good restore 自动化，并完成 M02 首次真机 boot-complete 验证。

### 当前仍来自 Xiaomi 官方的主体

Madrid 官方 system/system_ext/product/mi_ext 文件内容仍是平台主体，M02 的 4.0.19 发布文件来自官方 Madrid。Thyme 官方可直接确认的复用包括 OS1.0.4 dtbo 与部分固件参考；M02 实际没有刷这些固件。当前工作区不能证明 Known-Good vendor/odm 的每个文件都直接来自某个精确 OS1 build。所有权/授权状态未由本次技术 provenance 审计判断。

## 证据索引

- M00: [donor identity](../m00_madrid_intake_20261005/SUCCESS_PORT_DONOR_IDENTITY.md), [boot and super architecture](../m00_madrid_intake_20261005/THYME_SUCCESS_REFERENCE_ARCHITECTURE.md), [three-way structure map](../m00_madrid_intake_20261005/THREE_WAY_STRUCTURE_MAP.md).
- M01: [R3 Known-Good runtime report](../m01_known_good_runtime/M01_R3_REPORT.md).
- M02: [adaptation delta](../m02_adaptation_delta/THYME_ADAPTATION_DELTA.md), [version delta](../m02_adaptation_delta/MADRID_VERSION_DELTA.md), [partition matrix](../m02_adaptation_delta/PARTITION_PROVENANCE_MATRIX.md), [boot stack](../m02_adaptation_delta/KNOWN_GOOD_BOOT_STACK.md), [candidate build](../m02_adaptation_delta/M02_CANDIDATE_BUILD_REPORT.md), [runtime report](../m02_runtime/M02_FIRST_BOOT_RUNTIME_REPORT.md).
- Tool evidence: M02 build/overlay/manifest/validator and [Known-Good restore script](../../tools/restore_known_good_madrid_4_0_15.ps1).
- AVB flags: [AOSP libavb vbmeta header](https://android.googlesource.com/platform/external/avb/+/master/libavb/avb_vbmeta_image.h).
