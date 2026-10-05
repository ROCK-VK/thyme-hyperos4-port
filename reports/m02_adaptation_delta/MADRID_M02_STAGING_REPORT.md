# MADRID-M02 Fastboot staging report

Date: 2026-10-05 HKT
Status: candidate staged; device left in Bootloader Fastboot; formal first boot not started.

## Read-only preflight

The host saw exactly one Fastboot device. Device gates passed:

| Gate | Value |
| --- | --- |
| product | `thyme` |
| current slot | `a` |
| unlocked | `yes` |
| userspace Fastboot | `no` |
| slot-unbootable:a | `no` |
| slot-successful:a | `yes` |
| slot-retry-count:a | `4` |

All six deployment image hashes were recomputed immediately before writes and matched the frozen candidate r3 manifest. Each image fit its Fastboot-reported target partition. In particular, `super` reported 9,126,805,504 bytes capacity; the sparse file was 8,063,690,032 bytes and its expanded LP image is exactly the device's 9,126,805,504-byte physical size.

## Executed staging operations

| Operation | Result |
| --- | --- |
| `fastboot flash boot_a boot_noroot.img` | exit 0; `OKAY` |
| `fastboot flash vendor_boot_a vendor_boot.img` | exit 0; `OKAY` |
| `fastboot flash dtbo_a dtbo.img` | exit 0; `OKAY` |
| `fastboot flash super super.img` | exit 0; all 11 sparse chunks sent and written `OKAY` |
| `fastboot flash vbmeta_a vbmeta.img` | exit 0; `OKAY` |
| `fastboot flash vbmeta_system_a vbmeta_system.img` | exit 0; `OKAY` |
| `fastboot erase userdata` | exit 0; `Erasing 'userdata' OKAY` |
| `fastboot erase metadata` | exit 0; `Erasing 'metadata' OKAY` |
| `fastboot set_active a` | exit 0; current slot set to A |

Fastboot printed format-suggestion notices for the F2FS userdata and ext4 metadata partitions, but both requested `erase` commands returned `OKAY`; no `format`, `fastboot -w`, FRP erase or additional data command was issued. Fastboot also printed its sparse-super AVB-footer notice; the command completed with exit 0 and all chunks `OKAY`.

No firmware, B-slot, FRP, persist, modemst, fsg/EFS, NV, calibration, identity or bootloader-lock operation occurred. No reboot command was issued.

## Post-stage state

| Gate | Value |
| --- | --- |
| product | `thyme` |
| current slot | `a` |
| unlocked | `yes` |
| userspace Fastboot | `no` |
| slot-unbootable:a | `no` |
| slot-successful:a | `no` |
| slot-retry-count:a | `7` |
| Fastboot device presence | online |

The phone is staged for MADRID-M02 and remains in Bootloader Fastboot. The user confirmation for formal startup is still required: `开始启动 MADRID-M02`.

Full Fastboot command output and the machine-readable result remain in the private project workspace and are not part of the public report set. Device serials and host-specific details are intentionally excluded from this report.
