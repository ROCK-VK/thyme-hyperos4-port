# THYME-OS4 Project Status

Last updated: 2026-09-28 (Hong Kong time)

## Goal and current stage

Port the Xiaomi 15 (`dada`) HyperOS 4 / Android 17 userspace to Xiaomi Mi 10S (`thyme`). The immediate goal is to pass graphics initialization and reach the boot animation, setup wizard, or desktop.

**Current stage: A full C23 boot window ran for more than 11 minutes. The user reports a steady Xiaomi logo throughout and manually returned to Fastboot; ADB never appeared. pmsg spans about 11m38s and records /data/fscrypt initialization plus BootAnimation shown-timing, but no direct `sys.boot_completed=1`, `service.bootanim.exit`, SystemUI, SetupWizard, or Launcher record. No fatal has yet been tied to the missing UI; C24 is not built.**

## Device and flashed build

- Latest read-only state (2026-09-28 16:19 HKT): unique device 1384e684, thyme, A slot, unlocked, Bootloader Fastboot (not userspace). A: unbootable=no, successful=no, retry=5; B: unbootable=no, successful=no, retry=7. The long-window retest consumed one A-slot attempt; no set_active was run.
- C23 wrote only `super` and `vbmeta_system_a`. The inherited boot, vendor_boot, dtbo and root vbmeta were not rewritten.
- C23 had an earlier Recovery-only attempt and a 2026-09-28 retest. The retest observer was ARMED before one fastboot reboot; user observed a steady Xiaomi logo and manually returned to Fastboot. ADB did not come online.
- The phone is currently in Bootloader Fastboot on C23. PixelOS has not been restored; no userdata/metadata erase, BCB edit, other partition write, hardware identity write, or Bootloader relock occurred in this retest.

## C22 result

- C22 reached First/Second Stage, APEX, vold and `/data` initialization. SurfaceFlinger then aborted 89 times with `output buffer not gpu writeable` in `Cache::primeShaderCache` / `SkiaRenderEngine::primeCache`.
- The C22 pmsg did not identify the runtime Vulkan ICD/backend. The underlying reason the output buffer lacked the expected GPU usage remains unknown.
- All 19 accessible C22 host-observation and Standalone export files were copied and checksum-verified. The public evidence manifest records source and published hashes.
- [C22 report](../reports/candidate22/REPORT.md) and [C22 evidence](../evidence/candidate22/).

## C23 experiment

- The only system change is `service.sf.prime_shader_cache=0` in `/system/build.prop`, intended to skip the optional startup shader-cache prewarm that directly appeared in the C22 fatal stack.
- C23 retains C22's K40 Android 17 Vulkan UMD experiment, C21 SkiaVk RenderEngine route, prior validated fixes, and thyme kernel/hardware stack.
- This is a diagnostic bypass, not a proven fix for regular composition or the underlying buffer-usage mismatch.
- Host checks passed for final EROFS readback, system AVB descriptor, retained product/system_ext descriptors, and LP layout. The build manifest lists all six image identities. Only `super` and `vbmeta_system_a` were flashed successfully.
- [C23 report](../reports/candidate23/REPORT.md), [build report](../reports/candidate23/BUILD_REPORT.md), and [six-image manifest](../reports/candidate23/BUILD_MANIFEST.json).

## C23 retest (2026-09-28)

- The console contains one normal Linux/Init instance: First Stage about 2.048s, Second Stage about 3.212s, enforcing SELinux, APEX, metadata and /data/vold initialization; F2FS /data mounted successfully. Console continues to about 126s.
- pmsg spans about two minutes and contains BootAnimation plus BootAnimationShownTiming start time: 42129ms. This is evidence of a BootAnimation-related stage, not proof of the visible screen contents, setup wizard, desktop, or boot completion. The user reported only the steady Xiaomi logo.
- The captured pmsg does not reproduce C22 output buffer not gpu writeable, primeShaderCache, EGLConfig, or Vulkan RenderEngine fatal messages. This is positive stage evidence, but runtime service.sf.prime_shader_cache=0 was not sampled; its effect is not independently verified.
- pmsg contains repeated netd SIGABRT in libnetd_updatable_init.cfi+576 and Xiaomi fingerprint-service SIGSEGV at fault address 0xd0 in libudfpshandler.so. Neither is proven to have blocked BootAnimation/UI. No additional broad fix is justified from this run alone.
- The standalone export has 8 source files (17,805,353 bytes), all copied and SHA-256 matched. oops.raw matches C13-C22 historical content; Standalone dmesg is diagnostic-system output. See [C23 retest report](../reports/candidate23/C23_RETEST_20260928.md) and [full retest evidence](../evidence/candidate23/).

## C23 complete boot-window retest (2026-09-28)

- The observer was ARMED before one `fastboot reboot` at 15:47:14.282 HKT. The user reports the screen remained a static Xiaomi logo for the entire wait and manually entered Fastboot. Host Fastboot was first detected again about 11m52.8s after reboot; ADB never appeared.
- pmsg records successful F2FS `/data` mount and fscrypt initialization, plus `BootAnimationShownTiming start time: 40943ms`. This is not proof that the user saw the HyperOS animation. No direct `sys.boot_completed=1`, `service.bootanim.exit`, SystemUI/SetupWizard/Launcher record was found. The pmsg did not reproduce the earlier EGLConfig, Vulkan RenderEngine, or shader-cache output-buffer fatal strings; the runtime value of `service.sf.prime_shader_cache` was not sampled.
- Repeated pmsg failures: `netd` SIGABRT 138 times, fingerprint HAL SIGSEGV 137 times, `audio.service` SIGSEGV 74 times; 23 `UltraFrameworkComponentFactoryImpl` ClassNotFoundException messages include `SurfaceControl.<clinit>`. Their relationship to the missing UI is unknown. No specific fatal explains the static logo, so C24 is not built.
- Standalone export: 8 diagnostic-volume files (20,433,856 bytes) copied with zero errors and source/copy SHA-256 matches. Console covers kernel uptime 120.114755–702.552956s without a panic; pmsg spans about 697.883s. The 16 MiB `oops.raw` is identical historical residue, not C23. Full report: [C23 long-boot report](../reports/candidate23/C23_LONG_BOOT_RETEST_20260928.md); [all raw host and Standalone evidence](../evidence/candidate23/long_boot_retest/).
- Postboot read-only status: thyme/A, unlocked Bootloader Fastboot, non-userspace; A retry 6→5, unbootable=no and unsuccessful; B retry=7, unbootable=no and unsuccessful. No flash, data erase, slot change, BCB edit, PixelOS restore, or relock occurred.
## Validated history and remaining uncertainty

- C13 reached Android First/Second Stage, APEX, vold and `/data`; C14 bypassed the BPF/kernel-version restart gate.
- C16/C17 addressed graphics allocator `ion_device` read/open AVCs; the C17 retest did not reproduce those denials.
- C19/C20 repeatedly failed EGLConfig selection. C21's SkiaVk route passed that recorded failure but hit Vulkan RenderEngine initialization fatal. C22 passed that fatal and reached shader-cache prewarming.
- C23's visible `console-ramoops` contains one Recovery-mode boot instance: init skipped first-stage mounts for recovery mode and Recovery started. It records `bootonce-bootloader` and then clears BCB after Recovery starts; this does not establish why Recovery was selected or whether an earlier normal boot was overwritten.
- Host ADB was only `unauthorized`; no usable logcat was captured. The Standalone export copied all 7 accessible diagnostic-volume files (17,117,150 bytes) with source/copy SHA-256 matches. No pmsg was present; `oops.raw` matches the C22 historical residual, and Standalone dmesg belongs to the diagnostic environment.
- There is no C23 SurfaceFlinger, Skia, Vulkan, or shader-cache log. The effect of `service.sf.prime_shader_cache=0`, normal composition, and any progress to HyperOS UI are unknown.

## Next step
Keep C23 in Fastboot; do not repeat set_active or blindly reboot. Do not build C24 or clear userdata/metadata yet. The next work should target the gap between BootAnimation timing and missing framework/UI completion, including the repeated `SurfaceControl` component-factory lookup; no item is confirmed as the cause. The Recovery trigger from the earlier C23 attempt remains unknown.
If C23 re-enters Recovery, save that evidence and do not confirm wipe prompts; the current Recovery path remains unproven as the root cause.

## Public evidence
The evidence index covers user-authorized C13–C23 diagnostic evidence. The C23 long-window Standalone export and host observations are published with per-file source/public sizes and SHA-256 in the cumulative evidence manifest. The Recovery follow-up report is linked below; complete `misc.raw` and partition backups remain local. No ROMs, firmware packages, partition images, userdata/metadata images, credentials, or hardware-identity partition backups are included.

C23 Recovery follow-up: [recovery cause and A-slot retest preparation](../reports/candidate23/RECOVERY_RETEST_20260927.md). Earlier retest: [normal boot and BootAnimation evidence](../reports/candidate23/C23_RETEST_20260928.md). Latest: [complete boot-window report](../reports/candidate23/C23_LONG_BOOT_RETEST_20260928.md).
