# Candidate 13 clean-data first-boot evidence (2026-09-26)

## Result

After the authorized C13 flash and one `userdata` plus one `metadata` erase, the user observed the Xiaomi logo for over 20 seconds, followed by a black screen and logo again; the cycle was seen twice before the user manually returned to Fastboot. No successful ADB session, boot animation, setup screen, or desktop was observed.

Standalone RAM evidence contains one visible C13 kernel/init boot record. It shows:

1. Android first-stage init started.
2. The metadata ext4 mount and filesystem check completed successfully.
3. Multiple logical filesystem mounts completed.
4. The precompiled SELinux policy hash did not match, so init compiled policy dynamically; the log records enforcing mode and second-stage init startup.
5. `apexd-bootstrap` scanned 41 preinstalled APEX packages and completed.

The record ends at about 3.75 seconds. It does not show what happened afterward, whether additional attempts occurred, or why the device returned to the Xiaomi logo. The earlier C13 run with old data entered a Recovery branch; that earlier evidence remains a separate run and is not the clean-data result.

## SELinux status

Candidate 13 adds Keymaster and Gatekeeper access rules for `ion_device` in `system_ext_sepolicy.cil`. Host-side compilation and permission queries succeeded. The clean-data pstore confirms dynamic policy compilation and enforcing second-stage startup, but it does not name the effective rule set or show Keymaster/Gatekeeper startup. The ION AVC, QSEECom, HAL, vold, metadata-encryption, and `/data` outcomes remain unverified on-device.

The host policy compile used `secilc -N`; that result is not an independent neverallow validation.

## Evidence files

- [C13 clean-data console-ramoops](../boot-logs/candidate13_clean_data_console-ramoops.txt)
- [Earlier C13 Recovery console-ramoops](../boot-logs/candidate13_recovery_console-ramoops.txt)
- [USB/ADB/Fastboot timeline from the clean-data run](../boot-logs/candidate13_usb_adb_fastboot_timeline.csv)
- Detailed earlier analyses: [Recovery analysis](20260925_CANDIDATE13_RECOVERY_ANALYSIS.md), [root-cause and next-experiment analysis](20260925_CANDIDATE13_ROOT_CAUSE_AND_NEXT_EXPERIMENT.md)

## Later recovery state

After this C13 experiment, PixelOS A0′ six-image recovery flashing completed on 2026-09-26 and the device remained in Bootloader Fastboot. That restore write was successful, but PixelOS has not yet been boot-verified after the latest restore. This later state is recorded in [`logs/PROJECT_STATUS.md`](../../logs/PROJECT_STATUS.md).
