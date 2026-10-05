# M02 adaptation rebase conflict report

Updated: 2026-10-05 20:05 HKT
Intersection checked: `Known-Good − Official 4.0.15` changed paths ∩ `Official 4.0.15 → 4.0.19` changed paths.

## Exact intersections

| Path | Conflict class | Decision |
| --- | --- | --- |
| `product/etc/build.prop` | **MANUAL_MERGE** | Keep Known-Good thyme settings and device identity. Take only Official 4.0.19 release identity/build properties: description, incremental, dates/UTC, host/UUID and product fingerprint/version keys. Preserve `ro.sf.lcd_density=440`, `persist.miui.density_v2=440`, thyme scheduler/affinity/minfree, and other Known-Good tuning. |
| `mi_ext/etc/build.prop` | **MANUAL_MERGE** | Preserve `ro.product.mod_device=thyme`; update `ro.build.version.incremental`, `ro.build.version.smr_baseversion`, `ro.mi.os.version.incremental`, and `ro.product.build.version.incremental` from Official 4.0.19. |

There are no path intersections in `system` or `system_ext`. This means there is no same-file collision in those partitions; it does not prove every cross-library dependency is runtime-compatible.

## Non-conflicting adaptation paths

| Path set | Class | Decision |
| --- | --- | --- |
| `system/etc/selinux/mapping/30.0.cil`, `30.0.compat.cil` | **KEEP_THYME** | Keep; added by Known-Good for the thyme vendor compatibility stack. |
| `system/etc/init/hw/init.rc`, `system/framework/services.jar` | **KEEP_THYME** + **NEEDS_RUNTIME_TEST** | Preserve Known-Good versions. Check first-stage/system-server behavior after boot. |
| `system_ext/apex/com.android.vndk.v30.apex` and system_ext SELinux v30 mapping files | **KEEP_THYME** | Keep as the tested A13-vendor compatibility additions. |
| `system_ext/etc/vintf/manifest.xml` | **KEEP_THYME** + **NEEDS_RUNTIME_TEST** | Keep the Known-Good declaration set and verify with runtime VINTF/HAL enumeration. |
| `system_ext/app/PowerKeeper/PowerKeeper.apk`, `framework/framework-ext-res/framework-ext-res.apk`, `framework/miui-services.jar` | **KEEP_THYME** + **NEEDS_RUNTIME_TEST** | Preserve Known-Good bytes; Official 4.0.19 does not change these paths. Validate power/framework behavior at runtime. |
| Known-Good's removed six-entry MiSightService tree | **KEEP_THYME** | Keep absent as in the proven baseline; no Official 4.0.19 path delta reintroduces it. |
| Official 4.0.19's 219 `system` and 60 `system_ext` modified paths | **TAKE_4.0.19** | Overlay exact 4.0.19 bytes onto the Known-Good trees; the path intersection is empty. |
| Known-Good `vendor`, `odm`, `mi_ext`, `product` adaptation content | **KEEP_THYME** / **MANUAL_MERGE** for build.prop | Retain the tested hardware stack; only product/mi_ext release properties are merged as above. |

## Excluded source partitions

- Do not take Madrid `vendor`/`odm`: Known-Good versions are the thyme hardware stack proven on this device.
- Do not include Official Madrid `system_dlkm` or `vendor_dlkm`: their sampled modules report 6.18.21 vermagic; the booted Known-Good kernel is 4.19.325. Known-Good's fstab mounts six logical partitions and has no DLKM mount; its vendor carries 4.19 modules.
- Omit `mi_product`: Official's one-block empty stub is not mounted and is absent from Known-Good.
- No firmware or boot-chain image from Madrid enters M02.

## Merge gate

Before building, the property merge must be key-by-key and recorded in a generated diff. After building, compare the output trees with the intended merged trees, verify modes/owners/symlinks and filesystem config, run EROFS checks, validate LP metadata/physical size, then freeze hashes. Do not silently replace whole `product` or `mi_ext` build.prop files.
