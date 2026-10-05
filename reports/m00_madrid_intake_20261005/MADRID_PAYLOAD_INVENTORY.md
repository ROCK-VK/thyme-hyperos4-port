# MADRID PAYLOAD INVENTORY — official Xiaomi 18 Pro Max (`madrid`) OS4.0.19.0.XEOCNXM OTA

**Report ID:** `m00_madrid_intake_20261005` · **Generated:** 2026-10-05 · **Mode:** STRICTLY READ-ONLY.
No device was touched; no `adb`/`fastboot`/flash/erase/reboot was issued. Nothing under `10S系统`,
`18promax系统`, `reports\c*` or `work\stage_c*` was modified.
Labelling: **`[B]`** = static file evidence, reproducible from the named artefact; **`[D]`** = inference.
Missing evidence is written **`UNDETERMINED`**; nothing is guessed.

## 0. Evidence base
| Item | Value |
| --- | --- |
| Donor OTA | `18promax系统\madrid-ota_full-OS4.0.19.0.XEOCNXM-user-17.0-140f98a3e5\` |
| `payload.bin` size / SHA-256 | 12,430,754,836 B / `e1c22495c310f694f7146848d12d695b36cc872c5942d3e6ed01ec1bd14f70b6` `[B]` |
| base64 of that digest | `4cIklcMQ9pT3FGhI0S1pWzbMhyxZQtPm7QHsG9FPcLY=` — **identical to `FILE_HASH` in `payload_properties.txt`** `[B]` |
| Dumped images | `work\reference_madrid_os4_0_19\images\` — **66 files, 16,044,277,760 B = 14.9424 GiB** `[B]` |
| Hash method | SHA-256 streamed in 8 MiB chunks, all 66 files read in full; `certutil -hashfile vbmeta.img SHA256` independently reproduced the Python digest `[B]` |

Artefacts produced by this intake, under `work\madrid_m00_intake\`: `IMAGE_INVENTORY.csv`/`.json`
(bulk per-file data), `pb_decode.txt`, `payload_manifest.txt`, `payload_super_layout.txt`,
`payload_field15.txt`, `file_magic.txt`, `deep_probe.json`, `erofs_ident_full.txt`,
`ramdisks\ramdisk_probe.txt`, `dtb_probe.txt`, `vbmeta_info.txt`, `vbmeta_system_info.txt`.

## 1. OTA metadata decode
### 1.1 `META-INF/com/android/metadata` + `metadata.pb` `[B]`
| Key | Value |
| --- | --- |
| `ota-type` | **AB** — full OTA, not incremental (`metadata.pb` fields for pre-device/pre-build are absent) |
| `pre-device` | **`madrid`** |
| `post-build` | `Xiaomi/madrid/madrid:17/CP2A.260605.016/17OS4.0.261004.020338398.QCPECN.S:user/release-keys` |
| `post-build-incremental` | `17OS4.0.261004.020338398.QCPECN.S` |
| `post-sdk-level` | `37` (Android 17) |
| `post-security-patch-level` | **`2026-09-01`** |
| `post-timestamp` | `1791056252` → **2026-10-03T19:37:32Z** |
| `ota-required-cache` | `0` |

`metadata.pb` raw field map `[B]`: f1 = `1`; f4 = repeated {f1 name, f2 value}
(`ota-property-files`, `ota-streaming-property-files`); f5 = {f1 `'madrid'`}; f6 = post-build block
{f1 device `madrid`, f2 fingerprint, f3 incremental, f4 varint `0x6ac1597c` = 1791056252, f5 `'37'`,
f6 `'2026-09-01'`, f7 = repeated per-partition identity}; f18 = `'2026-09-01'`.
`metadata.pb` f6.f7 component split `[B]`: `init_boot`/`system`/`system_ext` → device `missi`,
ts 1791050921; `odm`/`system_dlkm`/`vendor_dlkm` → `madrid`, ts 1790792235; `product` → `miproduct`,
ts 1791050956; `vendor` → `mivendor`, ts 1790790271.

### 1.2 `care_map.pb` `[B]`
f1 = repeated {f1 partition, f2 `"<ver>,<slot>,<blocks>"` (4096 B blocks), f3 fp property, f4 fp value}.
| partition | blocks | fingerprint value |
| --- | --- | --- |
| `odm` | 1,431,708 | `Xiaomi/madrid/madrid:17/CQ2A.260712.001-CP2A.260605.016/OS4.0.17.1.XEOCN:user/release-keys` |
| `product` | 1,357,777 | `Xiaomi/madrid/miproduct:17/CP2A.260605.016/OS4.0.19.0.XEOCNXM:user/release-keys` |
| `system` | 234,052 | `Xiaomi/missi/missi:17/CP2A.260605.016/17OS4.0.261004.020338398.QCPECN.S:user/release-keys` |
| `system_dlkm` | 2,123 | `Xiaomi/madrid/madrid:17/CQ2A.260712.001-CP2A.260605.016/OS4.0.17.1.XEOCN:user/release-keys` |
| `system_ext` | 195,855 | `Xiaomi/missi/missi:17/CP2A.260605.016/17OS4.0.261004.020338398.QCPECN.S:user/release-keys` |
| `vendor` | 362,240 | `Xiaomi/mivendor/mivendor:17/CQ2A.260712.001-CP2A.260605.016/OS4.0.17.1.XEOCN:user/release-keys` |
| `vendor_dlkm` | 18,740 | `Xiaomi/madrid/madrid:17/CQ2A.260712.001-CP2A.260605.016/OS4.0.17.1.XEOCN:user/release-keys` |
| `mi_ext` | 41,779 | property `unknown`, value `unknown` |

All eight block counts were independently reproduced from the EROFS superblocks (§4.2) `[B]`.

### 1.3 `apex_info.pb` `[B]`
Top level: repeated **field 1** = one APEX record; inner **f1** = package name (string), **f2** varint,
**f3** varint, **f4** varint. No protobuf library was available or installed — decoded by hand from the
wire format. **42 records.** Fields are reported by number; `[D]` `f4` is always a 4 KiB-aligned byte
count, but no field name is asserted (`UNDETERMINED`) because no AOSP `.proto` source was present.
- **f2 = `0x1613daff` for 33 of 42.** Exceptions: `com.android.apex.cts.shim`=1, `com.android.devicelock`=1, `com.android.i18n`=1, `com.android.runtime`=1, `com.android.vndk.v34`=1, `com.android.hardware.cas`=1, `com.android.art.compatible`=`0x14455c90`, `com.google.android.gmssystem`=`0x282a80`, `com.google.android.widevine.lazy`=`0xb572590`.
- **f3 = 1 for 25 of 42**; the other 17 omit the field. **f4 is present exactly when f3 is present (25 records)**: `adbd`=0xbbf000, `adservices`=0xfda000, `appsearch`=0x474000, `art`=0x301e000, `configinfrastructure`=0x5bf000, `conscrypt`=0x83e000, `crashrecovery`=0x7e000, `extservices`=0x11fa000, `ipsec`=0xfd000, `media`=0x7bd000, `media.swcodec`=0x2dff000, `mediaprovider`=0x2c85000, `neuralnetworks`=0x7cc000, `npumanager`=0xa40000, `ondevicepersonalization`=0xe6e000, `permission`=0x1617000, `profiling`=0x28e000, `resolv`=0x5d000, `scheduling`=0x64000, `telephonycore`=0xd0000, `tethering`=0x2306000, `uprobestats`=0x430000, `uwb`=0x6d4000, `webapp`=0x5ea000, `wifi`=0x11ac000.
- **All 42 names, file order** (`com.android.` prefix except where marked): `adbd, adservices, apex.cts.shim, appsearch, art, bt, configinfrastructure, conscrypt, crashrecovery, devicelock, extservices, healthfitness, i18n, ipsec, media, media.swcodec, mediaprovider, neuralnetworks, npumanager, ondevicepersonalization, os.statsd, permission, profiling, resolv, rkpd, runtime, scheduling, sdkext, telephonycore, tethering, tzdata, uprobestats, uwb, virt, webapp, wifi, art.compatible, compos, vndk.v34, com.google.android.gmssystem, hardware.cas, com.google.android.widevine.lazy`.
These 42 names are byte-identical, in the same order, to `DeltaArchiveManifest` field 17 `[B]`.

### 1.4 OTA package file hashes `[B]`
| file | bytes | SHA-256 |
| --- | --- | --- |
| `payload_properties.txt` | 157 | `b0ea9169d4e5ab812a72f3dd2343a6d69208c0364b46e304609df48b6ee0ebe4` |
| `apex_info.pb` | 1,465 | `1276826b4ad4c1605deeb54643f20547be57bb5a3a8abd0ce892147c6289192b` |
| `care_map.pb` | 1,061 | `4a7e66db31fde86a06875c7bba99cdce3f3a405cc609735ad662a757bd72621c` |
| `META-INF/com/android/metadata` | 727 | `433b662abd443274853d629986a83a7344176c286c8c126d693a43c8f6aabbb7` |
| `META-INF/com/android/metadata.pb` | 1,603 | `b1201ba8e99e1910a0cb1bcf5a4d1a5eaf31b4c5e8b02a34928ddfba41ea95cd` |
| `META-INF/com/android/otacert` | 1,594 | `ff85d8bc50e4eed4c5f54734b20003e845a8ee5f206bfe717335ad594dd01a5e` |

## 2. Image inventory summary
Per-file detail (partition, bytes, SHA-256, container, libmagic text, ELF class/machine, AVB footer,
first-16-byte magic) is the bulk data and lives in `work\madrid_m00_intake\IMAGE_INVENTORY.csv`. `[B]`
**66 files · 16,044,277,760 B · 14.9424 GiB.** Container counts: ELF 39, EROFS 9, FAT12/16 7, Android
boot image (`ANDROID!`) 3, ext4 2, DT table (`[REDACTED_DEVICE_ID]`) 2, AVB vbmeta (`AVB0`) 2, raw-no-magic 1
(`countrycode`).
**16 of 66** images carry an `AVBf` footer at end-of-file `[B]`: `boot`, `countrycode`, `dtbo`,
`init_boot`, `mi_ext`, `mi_product`, `odm`, `product`, `pvmfw`, `qtvm_dtbo`, `system`, `system_dlkm`,
`system_ext`, `vendor`, `vendor_boot`, `vendor_dlkm`. For these the footer's `original_image_size` is
the true filesystem size and the remainder is dm-verity hashtree + FEC + padding `[B]` — e.g.
`system.img` is 977,055,744 B on disk but its EROFS is 958,676,992 B (234,052 × 4096) `[B]`.
## 3. boot / init_boot / vendor_boot / dtbo / vbmeta structure
### 3.1 `boot.img` `[B]`
| field | value |
| --- | --- |
| magic / header version | `ANDROID!` / **v4**; page_size 4096; header_size 1584; cmdline empty |
| `kernel_size` | **42,674,688** B |
| `ramdisk_size` | **0** |
| `os_version` | `0` (unset) |
| kernel banner (at kernel offset 20,251,038) | **`Linux version 6.18.21-android17-5-g1d099fcb35e0-abogki540753930-4k (kleaf@build-host) (Android (15323222, +pgo, +bolt, +lto, +mlgo, based on r584948c) clang version 22.0.1 (https://android.googlesource.com/toolchain/llvm-project 2d65e4108033380e6fe8e08b1f1826cd2bfb0c99), LLD 22.0.1 …` |
| AVB | footer v1.0, orig 42,696,704, vbmeta @42,696,704 (2432 B), `SHA256_RSA4096`, rollback index **1788220800** = 2026-09-01T00:00:00Z, key sha1 `bc713b7e9a337f5b88f9cda482bb6832a6cf2518` |

`[D]` The `-abogki…` tag and `kleaf@build-host` identify a Google-built GKI generic kernel; Xiaomi /
Qualcomm hardware support ships as modules in `vendor_dlkm` + `system_dlkm`.

### 3.2 `init_boot.img` `[B]`
Header v4; `kernel_size` 0; `ramdisk_size` **2,588,339** (LZ4 frame, magic `02 21 4c 18`);
`os_version` raw `0x220001a9` → **17.0.0**, patch **2026-09**; `header_size` 1584.
AVB footer v1.0, orig 2,592,768, vbmeta @2,592,768 (832 B), **Algorithm NONE** (hash-only, chained from
`vbmeta.img`); `com.android.build.init_boot.fingerprint` =
`Xiaomi/madrid/miproduct:17/CP2A.260605.016/OS4.0.19.0.XEOCNXM:user/release-keys`.
Ramdisk contents: `system/bin/{snapuserd,snapuserd_ramdisk,getprop,setprop,modprobe,toolbox_ramdisk,…}`,
`system/etc/init/snapuserd.rc` — generic, no `fstab`.

### 3.3 `vendor_boot.img` `[B]`
Header **v4**; page 4096; `vendor_ramdisk_size` 76,143,885; `dtb_size` 2,148,992;
`vendor_ramdisk_table_size` 324 (3 × 108); `bootconfig_size` 311; `header_size` 2128; addrs
kernel 0x8000 / ramdisk 0x1000000 / tags 0x100 / dtb 0x1F00000.
cmdline: `video=vfb:640x400,bpp=32,memsize=3072000 erofs.reserved_pages=64 nf_conntrack.hashsize=32768
nosoftlockup console=ttynull qcom_geni_serial.con_enabled=0 bootconfig
bootinfo.fingerprint=madrid:17/OS4.0.17.1.XEOCN:user mi_mtdoops.fingerprint=madrid:17/OS4.0.17.1.XEOCN:user bootconfig`
AVB: footer v1.0, orig 78,307,328, vbmeta @78,307,328 (640 B), **Algorithm NONE**;
`com.android.build.vendor_boot.fingerprint` = `Xiaomi/madrid/madrid:17/CQ2A.260712.001-CP2A.260605.016/OS4.0.17.1.XEOCN:user/release-keys`.
**vendor_ramdisk table (3 entries, all LZ4 frames)** `[B]`:
| idx | type | name | compressed B | cpio B | content |
| --- | --- | --- | --- | --- | --- |
| 0 | 1 platform | `""` | 22,405,123 | 55,232,256 | `first_stage_ramdisk/fstab.qcom`, `lib/modules` |
| 1 | 2 recovery | `recovery` | 29,988,606 | 53,387,008 | full recovery ramdisk (`system/bin`, `init.recovery.qcom.rc`, sepolicy, `miui.factoryreset.*`) |
| 2 | 0 | `16K` | 23,750,156 | 61,492,992 | `lib/modules` (16 KiB page-size module set) |

bootconfig `[B]`: `androidboot.hardware=qcom`, `memcg=1`, `usbcontroller=a600000.dwc3`,
`load_modules_parallel=true`, `hypervisor.vm.supported=true`, `hypervisor.protected_vm.supported=true`,
`hypervisor.version=gunyah`, `vendor.qspa=true`, `serialconsole=0`.
**DTB = 4 concatenated FDTs** `[B]`:
| idx | bytes | model | compatible | qcom,msm-id | qcom,board-id |
| --- | --- | --- | --- | --- | --- |
| 0 | 538,106 | Qualcomm Technologies, Inc. Art v2 SoC | `qcom,art` | `<0x2c3 0x20000>` | `<0x00 0x00>` |
| 1 | 541,231 | Qualcomm Technologies, Inc. Art SoC | `qcom,art` | `<0x2c3 0x10000>` | `<0x00 0x00>` |
| 2 | 533,263 | Qualcomm Technologies, Inc. ArtP v2 SoC | `qcom,artp` | `<0x2c4 0x20000>` | `<0x00 0x00>` |
| 3 | 536,392 | Qualcomm Technologies, Inc. ArtP SoC | `qcom,artp` | `<0x2c4 0x10000>` | `<0x00 0x00>` |

`[D]` All four DTBs share the single board-id `(0,0)`: madrid's vendor_boot offers **no board-id based
variant selection**, only SoC-id (`art` vs `artp`) and revision.
### 3.4 `first_stage_ramdisk/fstab.qcom` — full text `[B]`
Source: `vendor_boot.img` → vendor_ramdisk idx 0 → `first_stage_ramdisk/fstab.qcom`. The file is 107
lines; lines 1–31 are the verbatim BSD-3-Clause licence preamble and are omitted here **only** for
report length — the complete byte-identical file is at
`work\madrid_m00_intake\ramdisks\vendor_ramdisk00\first_stage_ramdisk\fstab.qcom` and in
`work\madrid_m00_intake\ramdisks\ramdisk_probe.txt`. Everything from `# Android fstab file.` onward:
```
# Android fstab file.
# The filesystem that contains the filesystem checker binary (typically /system) cannot
# specify MF_CHECK, and must come before any filesystems that do specify MF_CHECK

#<src>                                                 <mnt_point>            <type>  <mnt_flags and options>                            <fs_mgr_flags>
system                                                  /system                ext4    ro,barrier=1,discard                                 wait,slotselect,avb=vbmeta_system,logical,first_stage_mount,avb_keys=/avb/q-gsi.avbpubkey:/avb/r-gsi.avbpubkey:/avb/s-gsi.avbpubkey:/avb/t-gsi.avbpubkey:/avb/u-gsi.avbpubkey:/avb/v-gsi.avbpubkey
system                                                  /system                erofs   ro                                                   wait,slotselect,avb=vbmeta_system,logical,first_stage_mount,avb_keys=/avb/q-gsi.avbpubkey:/avb/r-gsi.avbpubkey:/avb/s-gsi.avbpubkey:/avb/t-gsi.avbpubkey:/avb/u-gsi.avbpubkey:/avb/v-gsi.avbpubkey

system_ext                                              /system_ext            ext4    ro,barrier=1,discard                                 wait,slotselect,avb=vbmeta_system,logical,first_stage_mount
system_ext                                              /system_ext            erofs   ro                                                   wait,slotselect,avb=vbmeta_system,logical,first_stage_mount

product                                                 /product               ext4    ro,barrier=1,discard                                 wait,slotselect,avb=vbmeta_system,logical,first_stage_mount
product                                                 /product               erofs   ro                                                   wait,slotselect,avb=vbmeta_system,logical,first_stage_mount

mi_ext                                                  /mnt/vendor/mi_ext     ext4    ro,barrier=1,discard                                 wait,slotselect,avb=vbmeta,logical,first_stage_mount,nofail
/mnt/vendor/mi_ext                                      /mi_ext                ext4    ro,bind                                              wait,nofail
mi_ext                                                  /mnt/vendor/mi_ext     erofs   ro                                                   wait,slotselect,avb=vbmeta,logical,first_stage_mount,nofail
/mnt/vendor/mi_ext                                      /mi_ext                erofs   ro,bind                                              wait,nofail
overlay                                                 /product/overlay          overlay ro,lowerdir=/mnt/vendor/mi_ext/product/overlay/:/product/overlay check,nofail
overlay                                                 /product/app              overlay ro,lowerdir=/mnt/vendor/mi_ext/product/app/:/product/app check,nofail
overlay                                                 /product/priv-app         overlay ro,lowerdir=/mnt/vendor/mi_ext/product/priv-app/:/product/priv-app check,nofail
overlay                                                 /product/lib              overlay ro,lowerdir=/mnt/vendor/mi_ext/product/lib/:/product/lib check,nofail
overlay                                                 /product/lib64            overlay ro,lowerdir=/mnt/vendor/mi_ext/product/lib64/:/product/lib64 check,nofail
overlay                                                 /product/bin              overlay ro,lowerdir=/mnt/vendor/mi_ext/product/bin/:/product/bin check,nofail
overlay                                                 /product/framework        overlay ro,lowerdir=/mnt/vendor/mi_ext/product/framework/:/product/framework check,nofail
overlay                                                 /product/media            overlay ro,lowerdir=/mnt/vendor/mi_ext/product/media/:/product/media check,nofail
overlay                                                 /product/opcust           overlay ro,lowerdir=/mnt/vendor/mi_ext/product/opcust/:/product/opcust check,nofail
overlay                                                 /product/data-app         overlay ro,lowerdir=/mnt/vendor/mi_ext/product/data-app/:/product/data-app check,nofail
overlay                                                 /product/etc/sysconfig    overlay ro,lowerdir=/mnt/vendor/mi_ext/product/etc/sysconfig/:/product/etc/sysconfig check,nofail
overlay                                                 /product/etc/permissions  overlay ro,lowerdir=/mnt/vendor/mi_ext/product/etc/permissions/:/product/etc/permissions check,nofail
overlay                                                 /system/app               overlay ro,lowerdir=/mnt/vendor/mi_ext/system/app/:/product/pangu/system/app/:/system/app check,nofail
overlay                                                 /system/priv-app          overlay ro,lowerdir=/mnt/vendor/mi_ext/system/priv-app/:/product/pangu/system/priv-app/:/system/priv-app check,nofail
overlay                                                 /system/framework         overlay ro,lowerdir=/product/pangu/system/framework/:/system/framework check,nofail
overlay                                                 /system/etc/sysconfig     overlay ro,lowerdir=/mnt/vendor/mi_ext/system/etc/sysconfig/:/system/etc/sysconfig check,nofail
overlay                                                 /system/etc/permissions   overlay ro,lowerdir=/mnt/vendor/mi_ext/system/etc/permissions/:/product/pangu/system/etc/permissions/:/system/etc/permissions check,nofail
overlay                                                 /product/usr              overlay ro,lowerdir=/mnt/vendor/mi_ext/product/usr:/product/usr check,nofail
overlay                                                 /product/etc/precust_theme  overlay ro,lowerdir=/mnt/vendor/mi_ext/product/etc/precust_theme:/product/etc/precust_theme check,nofail
overlay                                                 /product/etc/preferred-apps overlay ro,lowerdir=/mnt/vendor/mi_ext/product/etc/preferred-apps:/product/etc/preferred-apps check,nofail
overlay                                                 /product/etc/security       overlay ro,lowerdir=/mnt/vendor/mi_ext/product/etc/security:/product/etc/security check,nofail
overlay                                                 /system_ext/etc/permissions overlay ro,lowerdir=/mnt/vendor/mi_ext/system_ext/etc/permissions:/system_ext/etc/permissions check,nofail

vendor                                                  /vendor                ext4    ro,barrier=1,discard                                 wait,slotselect,avb=vbmeta,logical,first_stage_mount
vendor                                                  /vendor                erofs   ro                                                   wait,slotselect,avb=vbmeta,logical,first_stage_mount

vendor_dlkm                                             /vendor_dlkm           ext4    ro,barrier=1,discard                                 wait,slotselect,avb=vbmeta,logical,first_stage_mount
vendor_dlkm                                             /vendor_dlkm           erofs   ro                                                   wait,slotselect,avb=vbmeta,logical,first_stage_mount

system_dlkm                                             /system_dlkm           ext4    ro,barrier=1,discard                                 wait,slotselect,avb=vbmeta,logical,first_stage_mount
system_dlkm                                             /system_dlkm           erofs   ro                                                   wait,slotselect,avb=vbmeta,logical,first_stage_mount

odm                                                     /odm                   ext4    ro,barrier=1,discard                                 wait,slotselect,avb=vbmeta,logical,first_stage_mount
odm                                                     /odm                   erofs   ro                                                   wait,slotselect,avb=vbmeta,logical,first_stage_mount

/dev/block/by-name/boot                                 /boot                  emmc    defaults                                             slotselect,avb=vbmeta,first_stage_mount
/dev/block/by-name/init_boot                            /init_boot             emmc    defaults                                             slotselect,avb=vbmeta,first_stage_mount
/dev/block/by-name/vendor_boot                          /vendor_boot           emmc    defaults                                             slotselect,avb=vbmeta,first_stage_mount
/dev/block/by-name/dtbo                                 /dtbo                  emmc    defaults                                             slotselect,avb=vbmeta,first_stage_mount
/dev/block/by-name/metadata                             /metadata              ext4    noatime,nosuid,nodev,discard                         wait,check,formattable,first_stage_mount
/dev/block/bootdevice/by-name/persist                   /mnt/vendor/persist    ext4    noatime,nosuid,nodev,barrier=1                       wait
/dev/block/bootdevice/by-name/userdata                  /data                  f2fs    noatime,nosuid,nodev,discard,reserve_root=32768,resgid=1065,fsync_mode=nobarrier,inlinecrypt   latemount,wait,check,formattable,fileencryption=aes-256-xts:aes-256-cts:v2+inlinecrypt_optimized+wrappedkey_v0,keydirectory=/metadata/vold/metadata_encryption,metadata_encryption=aes-256-xts:wrappedkey_v0,quota,reservedsize=128M,sysfs_path=/sys/devices/platform/soc/1d84000.ufshc,checkpoint=fs
/dev/block/bootdevice/by-name/userdata                  /data                  ext4    noatime,nosuid,nodev,discard,resgid=1065,inlinecrypt   latemount,wait,check,formattable,fileencryption=aes-256-xts:aes-256-cts:v2+inlinecrypt_optimized+wrappedkey_v0,keydirectory=/metadata/vold/metadata_encryption,metadata_encryption=aes-256-xts:wrappedkey_v0,quota,reservedsize=128M,sysfs_path=/sys/devices/platform/soc/1d84000.ufshc,checkpoint=fs
/dev/block/by-name/misc                                 /misc                  emmc    defaults                                             defaults
/devices/platform/soc/1c44000.sdhci/mmc_host*           /storage/sdcard1       vfat    nosuid,nodev                                         wait,voldmanaged=sdcard1:auto,encryptable=footer
/devices/platform/soc/*.ssusb/*.dwc3/xhci-hcd.*.auto*   /storage/usbotg        vfat    nosuid,nodev                                         wait,voldmanaged=usbotg:auto
/dev/block/bootdevice/by-name/modem                     /vendor/firmware_mnt   vfat    ro,check=strict,uid=1000,gid=1000,dmask=227,fmask=337,context=u:object_r:firmware_file:s0 wait,slotselect
/dev/block/bootdevice/by-name/modemfirmware             /vendor/modem_firmware   vfat    ro,check=strict,uid=1000,gid=1000,dmask=227,fmask=337,context=u:object_r:firmware_file:s0 wait,slotselect
/dev/block/bootdevice/by-name/dsp                       /vendor/dsp            ext4    ro,nosuid,nodev,barrier=1                            wait,slotselect
/dev/block/bootdevice/by-name/vm-bootsys                /vendor/vm-system     ext4    ro,nosuid,nodev,barrier=1                            wait,slotselect
/dev/block/bootdevice/by-name/vm-persist                /mnt/vendor/vm-persist     ext4    noatime,nosuid,nodev,barrier=1                  wait
/dev/block/bootdevice/by-name/bluetooth                 /vendor/bt_firmware    vfat    ro,shortname=lower,uid=1002,gid=3002,dmask=227,fmask=337,context=u:object_r:bt_firmware_file:s0 wait,slotselect
/dev/block/bootdevice/by-name/qmcs                      /mnt/vendor/qmcs       vfat    noatime,nosuid,nodev,context=u:object_r:vendor_qmcs_file:s0   wait,check,formattable
/dev/block/bootdevice/by-name/spunvm                    /mnt/vendor/spunvm     vfat    noatime,nosuid,nodev,context=u:object_r:vendor_spunvm_file:s0   wait,check,formattable
/dev/block/bootdevice/by-name/soccp                     /vendor/soccp_firmware vfat    ro,shortname=lower,uid=0,gid=1000,dmask=227,fmask=337,context=u:object_r:vendor_soccp_file:s0 wait,slotselect
/dev/block/bootdevice/by-name/dcp                       /vendor/dcp_firmware   vfat    ro,shortname=lower,uid=0,gid=1000,dmask=227,fmask=337,context=u:object_r:vendor_dcp_file:s0 wait,slotselect
/dev/block/bootdevice/by-name/rescue                    /mnt/rescue            ext4    noatime,nosuid,nodev,barrier=1                       wait,check,nofail
```
Structural reading `[B]`: `system`, `system_ext`, `product`, `mi_ext`, `vendor`, `vendor_dlkm`,
`system_dlkm`, `odm` are all **`logical`** partitions whose live filesystem is **EROFS**;
`system`/`system_ext`/`product` chain to `avb=vbmeta_system` with GSI `avb_keys`, the rest to
`avb=vbmeta`. **`mi_product` does not appear in the fstab at all.** `/dev/block/by-name/cust` is
referenced only from `system_ext:/etc/fstab.other` (`erofs|ext4 ro avb,nofail`) and is not a payload
partition. A second first-stage fstab exists at `system:/system/etc/fstab.postinstall` (system_other).

### 3.5 `dtbo.img` and `qtvm_dtbo.img` `[B]`
`dt_table_header` is big-endian. `dtbo.img`: magic `0xd7b7ab1e`, total_size 848,330, header_size 32,
dt_entry_size 32, **dt_entry_count = 1**, page_size 4096, version 0. Entry 0: size 848,266, offset 64,
**id `0x00000000`**, rev `0x00000000`, custom `00000000`. AVB orig 851,968, vbmeta @851,968 (640 B),
Algorithm NONE, fingerprint `Xiaomi/madrid/madrid:17/CQ2A…OS4.0.17.1.XEOCN`.
`qtvm_dtbo.img`: total_size 28,977, **dt_entry_count = 1**, page_size 0, entry **id `0x0000002d`**,
size 28,913, offset 64; AVB orig 28,977, vbmeta @32,768 (2112 B). `[D]` madrid's dtbo container holds
exactly one entry whose ID is `0`.

### 3.6 `vbmeta.img` / `vbmeta_system.img` `[B]`
Both `AVB0`, min libavb 1.0, release string `avbtool 1.4.0`, key sha1 `bc713b7e9a337f5b88f9cda482bb6832a6cf2518`.
| | `vbmeta.img` (12,288 B) | `vbmeta_system.img` (4,096 B) |
| --- | --- | --- |
| header / auth / aux | 256 / 576 / 8384 | 256 / 576 / 2816 |
| algorithm | `SHA256_RSA4096` | `SHA256_RSA4096` |
| rollback index | 0 | 1788220800 |
| chain partitions | `boot` (ri loc 3), `vbmeta_system` (ri loc 2) | — |
| hash descriptors | `countrycode`(32 B), `dtbo`, `init_boot`, `pvmfw`, `vendor_boot` | — |
| hashtree descriptors | `mi_ext`, `mi_product`, `odm`, `system_dlkm`, `vendor`, `vendor_dlkm` | `product`, `system`, `system_ext` |

## 4. Dynamic partition ("super") map
**There is no `super.img` in this OTA** `[B]`. As in all A/B payloads, `payload.bin` ships each logical
partition as its own image; super geometry lives in the payload manifest. Nine of the 66 payload
partitions are dynamic `[B]`.

### 4.1 Super geometry, from `DeltaArchiveManifest` field 15 `[B]`
`payload.bin` header: magic `CrAU`, major version 2, manifest 443,342 B, metadata signature 267 B.
Manifest top-level fields `[B]`: **f3** = 4096 (block size), **f4** = 12,430,310,936, **f5** = 267,
**f12** = 0, **f13** = 66 partitions, **f14** = 1791056252, **f15** = dynamic partition metadata,
**f17** = 42 APEX records, **f18** = `'2026-09-01'`.
```
field 15 raw structure:
  field 1  msg/118 B -> { field 1 string = 'qti_dynamic_partitions'
                          field 2 varint = 18779996160      # group max_size (bytes)
                          field 3 string = 'odm','product','system','system_dlkm','system_ext',
                                           'vendor','vendor_dlkm','mi_product','mi_ext'  # 9 members }
  field 2 varint = 1 ; field 3 varint = 1 ; field 4 string = 'lz4' ; field 5 varint = 3
  field 7 varint = 65536
  field 9  msg/13 B  -> { field 1 string = 'super' ; field 2 varint = 18790481920 }
```
| quantity | value |
| --- | --- |
| group name | **`qti_dynamic_partitions`** |
| group `max_size` | **18,779,996,160 B = 17.4924 GiB** |
| `super` partition size (f15.9) | **18,790,481,920 B = 17.5021 GiB** |
| super − group delta | 10,485,760 B = 10 MiB (1 MiB aligned) `[D]` LP metadata/geometry reserve |
| group members | `odm`, `product`, `system`, `system_dlkm`, `system_ext`, `vendor`, `vendor_dlkm`, `mi_product`, `mi_ext` |

Field 15 sub-fields 2/3/5/7 and field 9's name are reported **by number only** — **`UNDETERMINED`**.
`[D]` f4 = `'lz4'` is consistent with the vendor property `ro.virtual_ab.compression.enabled=true`
(and `ro.virtual_ab.enabled=true`), so f2/f3 are plausibly snapshot/VABC enable flags.
`field 13` `PartitionUpdate` carries, for exactly those 9 dynamic partitions and no others, **f2**
run_postinstall, **f3** postinstall_path, **f19**, **f20** `[B]`:
| partition | run_post | postinstall_path | f19 | f20 |
| --- | --- | --- | --- | --- |
| `system` | 1 | `system/bin/otapreopt_script` | 936,205,019 | 14,911 |
| `odm` | 0 | – | 5,870,111,694 | 91,192 |
| `product` | 0 | – | 5,545,567,132 | 86,483 |
| `vendor` | 0 | – | 1,439,998,852 | 23,075 |
| `system_ext` | 0 | – | 768,051,833 | 12,478 |
| `mi_ext` | 0 | – | 177,507,985 | 2,655 |
| `vendor_dlkm` | 0 | – | 73,299,371 | 1,195 |
| `system_dlkm` | 0 | – | 10,529,899 | 138 |
| `mi_product` | 0 | – | 2,122,808 | 25 |

Σ f19 = **14,823,394,593 B (13.81 GiB)**. `[D]` f19/f20 look like Virtual A/B COW size and operation
count estimates; the names are not asserted. Field 15's group membership and field 13's f19 presence
agree exactly on the same 9 partitions `[B]`.
### 4.2 Per-partition filesystem + identity `[B]`
All nine are **EROFS**, 4096 B blocks, compat `sb_csum mtime xattr_filter`, incompat `LZ4_0PADDING`,
"required upstream Linux kernel version 5.4", inode metadata start block 0, created stamp
`2009-01-01 08:00:00`.
| partition | EROFS FS bytes (AVB orig) | EROFS blocks | dumped bytes | EROFS UUID | identity file | own identity |
| --- | --- | --- | --- | --- | --- | --- |
| `system` | 958,676,992 | 234,052 | 977,055,744 | `[REDACTED_DEVICE_ID]-a22d-58b6-b92b-8b1ed5826678` | `/system/build.prop` | `ro.product.system.device=missi`; `ro.system.build.fingerprint=Xiaomi/missi/missi:17/CP2A.260605.016/17OS4.0.261004.020338398.QCPECN.S:user/release-keys`; `ro.build.flavor=missi-user`; `ro.build.host=pangu-build-component-system-808836-rfv1r-fzl9f-84r3n` |
| `system_ext` | 802,222,080 | 195,855 | 817,614,848 | `90926002-1a9b-5d98-b1bb-e19319bb9ef4` | `/etc/build.prop` | `ro.product.system_ext.device=missi`; fingerprint `Xiaomi/missi/missi:17/CP2A.260605.016/17OS4.0.261004.020338398.QCPECN.S`; `ro.control_privapp_permissions=enforce` |
| `product` | 5,561,454,592 | 1,357,777 | 5,667,659,776 | `[REDACTED_DEVICE_ID]-c9e1-5e2e-93df-e814fe687553` | `/etc/build.prop` | `ro.product.product.name=miproduct_madrid`; `ro.product.product.device=miproduct`; `ro.product.build.fingerprint=Xiaomi/madrid/miproduct:17/CP2A.260605.016/OS4.0.19.0.XEOCNXM:user/release-keys`; `ro.build.flavor=miproduct_madrid-user`; `ro.product.ab_ota_partitions=product,pvmfw`; `ro.product.cpu.pagesize.max=16384` |
| `vendor` | 1,483,735,040 | 362,240 | 1,512,136,704 | `[REDACTED_DEVICE_ID]-aee0-57d3-a5db-a80995c09ff3` | `/build.prop` | `ro.product.vendor.device=mivendor`; `ro.product.vendor.name=mivendor_sm8950`; `ro.product.vendor.model=Xiaomi for arm64`; `ro.vendor.build.fingerprint=Xiaomi/mivendor/mivendor:17/CQ2A.260712.001-CP2A.260605.016/OS4.0.17.1.XEOCN`; `ro.board.platform=art`; `ro.vendor.build.ab_ota_partitions=vendor` |
| `odm` | 5,864,275,968 | 1,431,708 | 5,976,252,416 | `[REDACTED_DEVICE_ID]-02d0-56b8-bc3a-a0ec5727d724` | `/etc/build.prop` | `ro.product.odm.device=madrid`; `ro.product.odm.model=M154FF`; **`ro.product.odm.marketname=Xiaomi 18 Pro Max`**; `ro.odm.build.fingerprint=Xiaomi/madrid/madrid:17/CQ2A.260712.001-CP2A.260605.016/OS4.0.17.1.XEOCN`; `ro.odm.build.id=CQ2A.260712.001-CP2A.260605.016` |
| `mi_ext` | 171,126,784 | 41,779 | 173,858,816 | `[REDACTED_DEVICE_ID]-6b13-5ec3-b3f6-4be8afde2f3c` | `/etc/build.prop` | flat overlay, no fingerprint: `ro.product.mod_device=madrid`; `ro.mi.os.version.incremental=OS4.0.19.0.XEOCNXM`; `ro.mi.os.version.name=OS4.0`; `ro.build.version.smr_baseversion=OS4.0.17.0.XEOCNXM`; `ro.vendor.build.ab_ota_partitions=<all 66 payload partitions>` |
| `system_dlkm` | 8,695,808 | 2,123 | 8,949,760 | `[REDACTED_DEVICE_ID]-6201-5435-9c64-4b8ed5e14af7` | `/etc/build.prop` | `ro.product.system_dlkm.device=madrid`; `ro.product.system_dlkm.name=miodm_madrid`; `ro.product.system_dlkm.model=M154FF`; fingerprint `Xiaomi/madrid/madrid:17/CQ2A…OS4.0.17.1.XEOCN`; `/lib/modules` = GKI modules |
| `vendor_dlkm` | 76,759,040 | 18,740 | 78,315,520 | `[REDACTED_DEVICE_ID]-c61b-524d-b101-5c3eff6784ae` | `/etc/build.prop` | `ro.product.vendor_dlkm.device=madrid`; `ro.product.vendor_dlkm.name=miodm_madrid`; fingerprint `Xiaomi/madrid/madrid:17/CQ2A…OS4.0.17.1.XEOCN`; `/lib/modules` = Qualcomm/Xiaomi modules |
| `mi_product` | 4,096 | 1 | 348,160 | `[REDACTED_DEVICE_ID]-a6e2-5e31-891d-21b009a6898b` | `/etc/build.prop` | single line `ro.mi.version.mi_product=empty` — **empty stub** `[B]` |

`[D]` The identity is **not** uniformly madrid: `system`, `system_ext` and `init_boot` carry the
`missi` platform identity, `vendor` carries the generic `mivendor` / `mivendor_sm8950` identity, and
only `odm`, `product`, `mi_ext`, `system_dlkm`, `vendor_dlkm`, `dtbo`, `vendor_boot`, `boot`, `pvmfw`
carry `madrid` identity.

## 5. Firmware / non-dynamic partition size matrix `[B]`
Sizes are dumped file sizes; format from magic bytes plus libmagic/readelf. **`abl` and `devcfg` are
ABSENT from this payload** — the 66-partition list contains neither. Non-dynamic images total
832,086,016 B (0.775 GiB); dynamic images 15,212,191,744 B (14.167 GiB).
> **Never-flash warning.** Every row below is `art`/`artp` (SM8950-class) Qualcomm or Xiaomi firmware
> or a Qualcomm/madrid-signed config blob. The project target is Xiaomi 10S / `thyme` /
> Snapdragon 870 (SM8250-AC), a different SoC generation. `[D]` Writing any of these to a `thyme`
> device presents firmware encoded/signed for a different SoC and boot chain. Rows marked **QF** are
> executable Qualcomm firmware/config whose wrong-SoC or wrong-signature write is the
> highest-consequence class and must **never** be flashed to a different SoC.
Every partition of the requested matrix appears below exactly once, with its byte size. Rows are
grouped by detected container so that the whole set is visible at a glance; per-partition SHA-256 is
in `IMAGE_INVENTORY.csv`. "ELF" means the file begins with `[REDACTED_DEVICE_ID]`; "raw" means it does not.
| container (magic) | partitions and byte sizes | never-flash |
| --- | --- | --- |
| ELF64 AArch64, type EXEC | `xbl` 1,122,304; `xbl_ac_config` 57,344; `xbl_ramdump` 770,048; `tz` 4,325,376; `tz_ac_config` 81,920; `hyp_config` 16,384; `hyp_ac_config` 94,208; `bl31` 552,960 | **QF** — primary bootloader, bootloader config, TrustZone, hypervisor config, ATF BL31 |
| ELF64 AArch64, type DYN (PIE) | `hyp` 1,826,816; `keymaster` 1,208,320; `secretkeeper` 958,464 | **QF** — hypervisor, TEE apps |
| ELF64 AArch64, type DYN (shared obj) | `featenabler` 118,784; `uefisecapp` 192,512; `idmanager` 69,632; `spuservice` 86,016 | **QF** — TEE/secure apps |
| ELF64 AArch64, type NONE | `uefi_dtb` 319,488 | **QF** |
| ELF64 `EM_ARM`, EXEC / NONE | `uefi` 3,584,000 (EXEC); `tz_oem_config` 163,840 (NONE); `tz_qti_config` 86,016 (NONE); `multiimgqti` 12,288 (NONE) | **QF** — UEFI payload and TZ OEM/QTI config |
| ELF64 `WE32100` (e_machine 1, Qualcomm-reused), EXEC | `xbl_config` 126,976; `cpucp_dtb` 12,288; `tme_seq_patch` 8,192 | **QF** — bootloader / CPUCp config blobs |
| ELF64 **RISC-V**, EXEC | `cpucp` 454,656 | **QF** |
| ELF32 **RISC-V**, EXEC | `aop` 569,344; `aop_config` 73,728; `dcd_oem` 28,672; `shrm_lp5` 188,416; `shrm_lp6` 208,896; `tme_fw` 311,296; `tme_config` 69,632 | **QF** — AOP, DCD, SHRM (LP5/LP6 variants), TME |
| ELF32 `EM_ARM`, EXEC / NONE | `android_esp` 339,968 (EXEC); `imagefv` 6,303,744 (EXEC); `pdp_cdb` 12,288 (EXEC); `vplan` 258,048 (EXEC); `vplan_mini` 49,152 (EXEC); `qecp` 688,128 (NONE) | **QF** — ESP/ABL-class, feature-verification image, plan blobs |
| ELF32 **QUALCOMM DSP6 (Hexagon)**, EXEC | `qupfw` 81,920 | **QF** |
| ELF32, e_machine `None` (0), EXEC | `pdp` 282,624 | **QF** |
| Android boot image `ANDROID!` v3 | `pvmfw` 1,048,576 (kernel 755,648, ramdisk 0, os_version 17.0.0, patch 2026-09) | **QF** — protected-VM firmware, madrid/miproduct-AVB-signed |
| ext4 | `dsp` 100,663,296 (vol `dsp`, UUID `[REDACTED_DEVICE_ID]-2a39-7e5b-a5dc-201456d93103`); `vm-bootsys` 41,943,040 (UUID `[REDACTED_DEVICE_ID]-abf4-655f-bf67-946fc0f9f25b`) | **QF** — ADSP firmware; VM system image (`/vendor/vm-system`) |
| **FAT16** (OEM-ID `MSWIN4.1`, 4096 B/sector, 4 sectors/cluster) | `modem` 167,772,160 (40,960 sec); `modemfirmware` 209,715,200 (51,200 sec) | **QF** — modem images, mounted `vfat` |
| **FAT12** (4096 B/sector) | `bluetooth` 8,388,608 (2,048 sec); `soccp` 8,388,608 (2,048 sec); `dcp` 8,388,608 (2,048 sec); `dcb` 1,048,576 (256 sec); `pmic_psi` 1,048,576 (256 sec) | **QF** — BT / SOC coprocessor / display coprocessor / DCB / PMIC firmware |
| DT table `[REDACTED_DEVICE_ID]` | `qtvm_dtbo` 5,242,880 — 1 entry, id `0x2d` | madrid/AVB-signed |
| raw, no recognised magic | `countrycode` 1,048,576 — AVB `Image Size` = **32 B**, content ASCII `"cn"` + zero fill | format-only, still madrid-AVB-signed |
| **ABSENT from this payload** | `abl`; `devcfg` | — |

## 6. Notable findings
1. **Donor integrity is bit-exact** `[B]`: `payload.bin` reproduces `FILE_HASH` (`4cIklcMQ9pT3FGhI0S1pWzbMhyxZQtPm7QHsG9FPcLY=`), and all 66 dumped images were re-hashed in full.
2. **Super layout** `[B]`: one group, `qti_dynamic_partitions`, `max_size` 18,779,996,160 B, 9 members; `super` itself 18,790,481,920 B. **No `super.img` in this OTA.** `[D]` `mi_ext` and `mi_product` are ordinary members of the single QTI group, not a separate group.
3. **Kernel = Google GKI 6.18.21** `[B]`: `Linux version 6.18.21-android17-5-g1d099fcb35e0-abogki540753930-4k`, `kleaf@build-host`, clang 22.0.1 / LLD 22.0.1, `+pgo +bolt +lto +mlgo`, `-4k` page size. It lives **only** in `boot.img`; `vendor_boot.img` has no kernel and `init_boot.img` holds only the generic ramdisk.
4. **Identity is split, not uniformly madrid** `[B]`: `system`/`system_ext`/`init_boot` = `missi` platform; `vendor` = `mivendor`/`mivendor_sm8950`; `odm`/`product`/`mi_ext`/`system_dlkm`/`vendor_dlkm`/`dtbo`/`vendor_boot`/`boot`/`pvmfw` = `madrid`.
5. **Two version lines coexist in one OTA** `[B]`: `product`/`mi_ext`/`boot` side = `OS4.0.19.0.XEOCNXM` (`17OS4.0.261004.020338398.QCPECN.S` on the `missi` system side); `odm`/`vendor`/`vendor_dlkm`/`system_dlkm`/`dtbo`/`vendor_boot` = `OS4.0.17.1.XEOCN`; `mi_ext` records `ro.build.version.smr_baseversion=OS4.0.17.0.XEOCNXM`.
6. **SoC is `art`/`artp`, not `thyme`'s platform** `[B]`: `ro.board.platform=art`, `ro.product.vendor.name=mivendor_sm8950`; vendor_boot DTB models "Qualcomm Technologies, Inc. Art / ArtP (v2) SoC" with `qcom,msm-id` `0x2c3` / `0x2c4`.
7. **Single board-id and a single dtbo entry** `[B]`: all four vendor_boot DTBs use `qcom,board-id = <0x00 0x00>`; `dtbo.img` has exactly one entry with ID `0x00000000`.
8. **`mi_product` is an empty stub in this build** `[B]` — a 1-block EROFS whose only content is `ro.mi.version.mi_product=empty` — yet it is a super group member, an entry in `ro.vendor.build.ab_ota_partitions`, and has an AVB hashtree descriptor; it is **not** in the fstab.
9. **`countrycode` is 32 bytes of content** `[B]` (`"cn"`) padded to 1 MiB; its AVB descriptor records `Image Size: 32 bytes`.
10. **Generic vs madrid-specific firmware** `[D]`: the Qualcomm blobs (`xbl*`, `tz*`, `hyp*`, `aop*`, `cpucp*`, `bl31`, `qupfw`, `dsp`, `modem`, `modemfirmware`, `bluetooth`, `soccp`, `dcp`, `dcb`, `pmic_psi`, `tme_*`, `shrm_lp5/lp6`, `secretkeeper`, `keymaster`, `featenabler`, `imagefv`, `uefisecapp`, `uefi*`, `vplan*`, `pdp*`, `qecp`, `idmanager`, `spuservice`, `multiimgqti`, `dcd_oem`, `android_esp`, `vm-bootsys`, `pvmfw`, `qtvm_dtbo`, `countrycode`) are `art`-platform firmware. Nothing in the payload distinguishes them as madrid-board-specific rather than `art`-platform-specific, and that distinction is **`UNDETERMINED`** from payload evidence alone.
11. **fstab does not mount `super` by name** `[B]`: the 8 system-side logical partitions come up as `logical,first_stage_mount` dm devices, and `mi_product` is not mounted at all.

## 7. Open / UNDETERMINED items
- On-device **logical-partition (LV) sizes inside `super`** are `UNDETERMINED` from payload evidence alone (no `super.img`, no LP metadata in this OTA); a device-side LP dump would be needed.
- `apex_info.pb` f2/f3/f4 and `DeltaArchiveManifest` f15 sub-fields 2/3/4/5/7/9 and f19/f20 are reported **by number only** — no AOSP `.proto` source was present in this workspace.
- `ro.product.vendor.model=Xiaomi for arm64` is a placeholder `[B]`; the only marketing name found is `ro.product.odm.marketname=Xiaomi 18 Pro Max` `[B]`.
- Whether `mi_product` is physically a separate A/B partition on the shipped device (listed in `ro.vendor.build.ab_ota_partitions` while also being a super group member) is `UNDETERMINED`.
- Contents of the large `odm` / `product` / `vendor_dlkm` payloads were **not** content-audited here; only filesystems, containers, identity properties and hashes were established.
