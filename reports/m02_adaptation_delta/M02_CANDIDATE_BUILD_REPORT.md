# MADRID-M02 candidate r3 build report

Date: 2026-10-05 HKT
Candidate: `work/madrid_m02_candidate_r3/`
Status: offline build, static gates, Fastboot staging and post-stage gates passed; formal first boot has not been started.

## Composition

- `system_a`: Known-Good thyme system tree with the 219 Official madrid 4.0.19 changed paths overlaid.
- `system_ext_a`: Known-Good thyme system_ext tree with the 60 Official madrid 4.0.19 changed paths overlaid; VNDK30 retained.
- `product_a`: Known-Good thyme product tree with allowlisted 4.0.19 release properties merged.
- `vendor_a`, `odm_a`: Known-Good thyme images retained byte-for-byte.
- `mi_ext_a`: Known-Good hybrid tree retained with same-length allowlisted build-property updates; `ro.product.mod_device=thyme` preserved.
- `boot_noroot.img`, `vendor_boot.img`, `dtbo.img`, `vbmeta.img`, `vbmeta_system.img`: exact frozen Known-Good images.
- `super.img`: sparse A-slot-only LP image containing the six selected dynamic partitions. No Madrid firmware, DLKM, `mi_product`, B-slot images, or protected partitions are included.

## Candidate hashes and sizes

The authoritative 12-image SHA256 and size manifests are:

- `work/madrid_m02_candidate_r3/metadata/SHA256SUMS`
- `work/madrid_m02_candidate_r3/metadata/SIZE_MANIFEST`
- `work/madrid_m02_candidate_r3/metadata/inventory/IMAGE_INVENTORY.json`
- `work/madrid_m02_candidate_r3/metadata/inventory/IMAGE_INVENTORY.csv`

Key deployment images:

| Image | Bytes | SHA256 |
| --- | ---: | --- |
| `boot_noroot.img` | 134,217,728 | `b059e885daaa11f0032e05ff5b16c7ee6a13d84b8cdbd51033ac2b4999c3fa0f` |
| `vendor_boot.img` | 100,663,296 | `ed5391f9ad2be11a0636657968972d005600658c45ff631e5462ce9779840b07` |
| `dtbo.img` | 33,554,432 | `a0f550a32c15b95a6ba0bbe141976bad905d23fc74367e3e3ff0f41bc90c6d3a` |
| `super.img` (sparse) | 8,063,690,032 | `51cf39c0d456c5bd2dd1e8fdf0d560d2a1deb647cf877c73678c6d259a73dfcd` |
| `vbmeta.img` | 4,096 | `d2e1979739ec67076a90b0fc625dae84a1aa2ed72d05d2b55d52539e3462b442` |
| `vbmeta_system.img` | 4,096 | `d2e1979739ec67076a90b0fc625dae84a1aa2ed72d05d2b55d52539e3462b442` |

The three frozen boot images and two vbmeta images match the Known-Good stack. The vbmeta headers retain flags `2`, algorithm `NONE`, and no partition descriptors. The v3 boot header advertises an old OS version field; the actual candidate platform version is carried in rebuilt userspace properties, so the boot header field is not used to identify the candidate release.

## Static validation

- Candidate inventory contains 12 images; the inventory, `SHA256SUMS`, and file sizes agree.
- `validate_m02_candidate.py` reports `passed=true`, `errors=[]`, six A-slot partitions populated, and six B-slot partitions empty.
- The expanded sparse super is exactly 9,126,805,504 bytes. `lpdump` and the independent LP parser agree on all partition sizes. LP geometry, header and tables checksums pass.
- Six populated extents total 8,140,926,976 bytes. Raw-capacity residual is 985,878,528 bytes before separately accounting LP reservations/alignment.
- Rebuilt EROFS sizes: `system_a` 959,004,672 bytes; `system_ext_a` 849,969,152 bytes; `product_a` 4,109,991,936 bytes. Each `fsck.erofs` check passed.
- Tree round-trip comparisons for the three EROFS images each report zero differences. Retained/rebuilt `mi_ext_a`, `vendor_a`, and `odm_a` pass read-only `e2fsck -fn`.
- Both allowlisted build-property merges pass validation. Thyme identity, density and device configuration keys remain preserved.
- Full gate output: `work/madrid_m02_candidate_r3/metadata/STATIC_GATE_REPORT.json`.

## Device state and next action

Candidate r3 passed the static validation and was staged to A/shared partitions. All six image flash commands and both data erases returned exit code 0; `set_active a` returned exit 0. Post-stage state: `thyme`, slot A, unlocked, Bootloader Fastboot (`is-userspace=no`), `slot-unbootable:a=no`, `slot-successful:a=no`, retry budget 7, Fastboot still online. The `userdata`/`metadata` erase responses included filesystem format suggestions, but each erase itself returned `OKAY`; no format command ran. No firmware or protected partition was touched, and no formal reboot occurred. See `MADRID_M02_STAGING_REPORT.md`.

Runtime compatibility remains unverified. Stop at Bootloader Fastboot until the user gives the sole first-boot confirmation: `开始启动 MADRID-M02`.
