# M01-R2 Controlled Experiment and Failure Evidence (Sanitized)

Updated: 2026-10-05

## Summary

The Known-Good top-level vbmeta_a write completed successfully. After one authorized boot session, Fastboot USB disappeared for about 33 seconds and then enumerated again. ADB did not appear. The A-slot retry count fell from 7 to 5. Standalone was then RAM-booted and its full THYME_DIAG volume was copied and verified. No M01-R2 kernel or pstore log was recovered, so the earliest failure point remains unknown.

R2 showed no observable Android boot progress. This lowers the hypothesis that top-level vbmeta was the sole or main blocker, but does not rule it out completely. R1 did not reproduce the full Known-Good flash matrix, so these failures do not invalidate the original reference package.

## Controlled write and boot

- Pre-write Fastboot checks confirmed the expected product, active slot, unlocked state, and A-slot retry state.
- Only the Known-Good top-level vbmeta image was written to vbmeta_a. Fastboot reported success.
- No other OS partition or firmware was written. Userdata and metadata were not erased. The bootloader was not relocked.
- One fastboot reboot was issued after authorization. The host observer recorded Fastboot USB leaving and returning after about 33 seconds; ADB remained absent.
- The post-failure A-slot retry count was 5, down from 7; the slot remained bootable and unsuccessful.
- Physical screen frames were not captured by the host, so the exact Mi Logo/black-screen sequence and boot stage cannot be independently confirmed.

## RAM evidence salvage

After Fastboot was confirmed, the existing Standalone diagnostic image was booted into RAM. No diagnostic image was flashed.

The complete THYME_DIAG directory tree was copied: 6 files, 16,936,141 bytes. Source and copy directory/file lists matched; every file passed size and SHA-256 comparison; copy errors were zero. FILE_MANIFEST, SIZE_MANIFEST, SHA256SUMS, and COPY_ERRORS were generated in the private workspace. The raw diagnostic volume and manifests are not included in this public repository.

## Evidence attribution

- The THYME_DIAG file list contained no console-ramoops or pmsg-ramoops file.
- diag_status reported that pstore mounted successfully but contained zero records.
- The available 4.19.325-perf kernel banner and dmesg belong to Standalone, not the Known-Good Android boot.
- oops.raw matched the older R1/C47 contents and is historical residue.
- There was no bootloader log in THYME_DIAG. Host USB/Fastboot/ADB timing is the only R2 boot observation.

The evidence does not establish whether the Known-Good kernel ran, whether init or first-stage init was reached, or whether the boot attempted super/dm/AVB, dtbo, vendor_boot/ramdisk, SELinux, firmware, or watchdog paths. No specific root cause is confirmed. The earlier R1 inference that the failure necessarily preceded second-stage init remains unverified.

## Next review

Before another device boot or expanded flash, review the original Known-Good flash matrix against the current setup. Focus on firmware dependencies, the boot/vendor_boot/ramdisk pairing, dtbo, and any clean-data requirement. Do not treat the R1/R2 safe subsets as full reproduction of the successful reference package.
