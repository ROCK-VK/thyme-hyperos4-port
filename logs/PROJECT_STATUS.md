# THYME-OS4 Project Status

Updated: 2026-10-01 22:03 HKT

## Goal and current milestone
Port Xiaomi 15 (dada) HyperOS 4 / Android 17 to Xiaomi 10S (thyme, Snapdragon 870). The current milestone is to isolate why the primary Zygote SIGABRT path fails to leave a useful tombstone. No formal startup fix has been established.

## Candidate and device
- C32-DIAG has been built and flashed to slot A; it has not been booted. The phone remains in Bootloader Fastboot.
- Last live post-flash read: one device, product=thyme, slot A, unlocked, non-userspace Fastboot. A: unbootable=no, successful=no, retry=2. B: unbootable=no, successful=no, retry=7.
- Only super and vbmeta_system_a were flashed; both Fastboot commands returned success. No raw partition readback was performed, so byte-for-byte device contents are not independently verified.
- No reboot, set_active, erase, format, metadata write, or PixelOS restore occurred. The next C32 boot requires the user's explicit on-site confirmation.

## C32 diagnostic delta
- C31→C32 adds system/bin/c32_zygote_canary and changes system/etc/init/hw/init.rc plus system/etc/selinux/plat_file_contexts; no files were removed.
- The one-shot, noncritical native canary sets comm=main, logs a fixed marker, sets abort message THYME_C32_CANARY_ABORT, then calls abort() once after the boot trigger observes tombstoned running.
- It reuses the existing zygote_exec file type and init→zygote transition. No new SELinux allow, CIL, or property-context rule was added. Runtime domain is unknown until a tombstone's SELinux label confirms it.
- This canary does not reproduce Zygote's ART, seccomp, namespace, signal-handler, file descriptor, credential/capability, or linker-namespace context. No runtime result exists yet.

## Build and verification
- super.img: 7,703,595,992 bytes; SHA-256 690658F64A7AA6DE254358DF9728C3085A5FB24D23BD5E94158F18A395A7B06B.
- vbmeta_system.img (flashed to vbmeta_system_a): 131,072 bytes; SHA-256 FEEBAF0C5087CA4233B8BD5DA2F424C175840AEBB0ACEFE51D51E35743E65C01.
- Static gates passed for EROFS/fsck and readbacks, canary ELF byte identity, system AVB, vbmeta system descriptor, LP rebuild/readback, and unchanged non-system logical inputs.
- Build run3 is the accepted output. Two earlier partial runs remain local. A later tooling-only fix lets --preflight-only run when build output already exists; syntax and Ubuntu WSL preflight passed, without rebuilding images.

## C31 evidence context and next step
- C31's first main SIGABRT PID matched the init marker's primary Zygote PID. The log retained only a generic crash_dump helper EOF; abort reason/backtrace, helper PID/status/signal, and tombstoned result remain unknown.
- C31 pstore through 527.837 seconds lacks C30's approximately 32.9-second PID1 sysrq panic. This supports, but does not prove, no_fatal.zygote isolated critical escalation.
- Wait for explicit on-site confirmation before booting C32. If it fails, the first Unified First-Response Standalone capture must preserve Candidate pstore first, then all accessible THYME_DIAG files, raw metadata, misc, separately named Standalone dmesg, and a SHA-256 manifest.

## Safety and reports
- No userdata/metadata clearing, boot-control change, hardware persist/radio/NV/calibration/identity write, or bootloader relock.
- C/D/E were above the 50 GiB heavy-work threshold at the latest recorded check. Docker assets were not touched.
- Local full flash transcript and raw evidence remain private. Public materials are limited to sanitized text, source, and scripts; no ROM, partition image, device backup, serial, secret, or hardware identity data is included.
- Report: reports/c32_diag_zygote_domain_canary_20261001/C32_DIAG_BUILD_FLASH_STATIC_GATE.md.
