# THYME-OS4 Project Status

Last updated: 2026-09-28 (Hong Kong time)

## Goal and current stage

Port the Xiaomi 15 (`dada`) HyperOS 4 / Android 17 userspace to Xiaomi Mi 10S (`thyme`). The immediate goal is to pass graphics initialization and reach the boot animation, setup wizard, or desktop.

**Current stage: C24 completed one observed boot lasting about 16m43s. The user saw only the first Xiaomi splash (central Xiaomi logo + `powered by Android`), never the HyperOS second screen with three dots, then manually entered Fastboot. ADB never appeared. pmsg records BootAnimation code activity, but the planned C24BootDiag sampler left no marker. Framework/UI progress, boot-animation completion and HWC/panel present remain unknown; do not infer that system_server or WMS failed solely from missing samples. C24 is still installed. No C25 built.**

## Device and flashed build

- Latest read-only state (2026-09-28 after the C24 Standalone export and final Fastboot recheck): one device, thyme, A slot, unlocked, Bootloader Fastboot (not userspace). A: unbootable=no, successful=no, retry=3; B: unbootable=no, successful=no, retry=7. A retry was 4 immediately before the one C24 boot and 3 afterward; no set_active was run.
- C24 wrote only `super` and `vbmeta_system_a`. The inherited boot, vendor_boot, dtbo and root vbmeta were not rewritten.
- C23 had an earlier Recovery-only attempt and a 2026-09-28 retest. The retest observer was ARMED before one fastboot reboot; user observed a steady Xiaomi logo and manually returned to Fastboot. ADB did not come online.
- The phone is currently in Bootloader Fastboot on C24. PixelOS has not been restored; no userdata/metadata erase, BCB edit, hardware identity write, or Bootloader relock occurred in this C24 experiment.

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
- Repeated pmsg failures: `netd` SIGABRT 138 times, fingerprint HAL SIGSEGV 137 times, `audio.service` SIGSEGV 74 times; 23 `UltraFrameworkComponentFactoryImpl` ClassNotFoundException messages include `SurfaceControl.<clinit>`. Their relationship to the missing UI is unknown. No specific fatal explained the static logo in that run.
- Standalone export: 8 diagnostic-volume files (20,433,856 bytes) copied with zero errors and source/copy SHA-256 matches. Console covers kernel uptime 120.114755–702.552956s without a panic; pmsg spans about 697.883s. The 16 MiB `oops.raw` is identical historical residue, not C23. Full report: [C23 long-boot report](../reports/candidate23/C23_LONG_BOOT_RETEST_20260928.md); [all raw host and Standalone evidence](../evidence/candidate23/long_boot_retest/).
- Postboot read-only status: thyme/A, unlocked Bootloader Fastboot, non-userspace; A retry 6→5, unbootable=no and unsuccessful; B retry=7, unbootable=no and unsuccessful. No flash, data erase, slot change, BCB edit, PixelOS restore, or relock occurred.

## C23 Framework/UI and physical display breakpoint investigation; C24 diagnostics

- The C23 pmsg has 11,775 timestamped records across about 697.883s. It records F2FS `/data` and fscrypt initialization, keystore2 waiting for `sys.boot_completed=1` through about 680s, SurfaceFlinger-domain activity, and BootAnimation PID activity including `BootAnimationShownTiming start time: 40943ms`.
- It does not record a system_server phase/PID, ActivityManager, WindowManager/WMS enable-screen, SystemUI, SetupWizard, Launcher/HOME, `service.bootanim.exit`, a sampled `sys.boot_completed=1`, HWC present/fences, or confirmed physical display update. The user saw only the static Xiaomi logo and ADB did not appear. Thus Android progressed into BootAnimation code, but Framework readiness versus an unupdated physical display remains unknown.
- `netd` SIGABRT, fingerprint/audio crashes and 23 `UltraFrameworkComponentFactoryImpl` CNFE messages are present, but none is tied by evidence to system_server, WMS, or display blocking. The class was not found in the scanned K40 OS4 system/system_ext JARs; this weakens, but does not prove away, a required-class hypothesis.
- Targeted Redmi K40 OS4.0.0.8 Android 17 comparison: `framework.jar`, `framework-res.apk`, `miui-framework.jar`, and `miui-services.jar` match the Xiaomi 15 OS4 donor and C23. K40 `services.jar`, `MiuiSystemUI.apk`, and device overlays differ, but no directly applicable boot-ready/WMS/panel-present fix was identified. `bootanim.rc` is identical; no K40 hardware-specific components were copied.
- The actual C23 product `bootanimation.zip` is 188,294 bytes, hash `44FE368CFD028F3CB89E7DCCAD75DF96EA9F77C3C1F417CE86C2853996721EB8`, with 5 frames at 5fps; pixel comparison shows frame changes only in the small bottom progress-dot region. The K40 success package uses a different 32-frame 31.7fps resource with different canvas parameters. This is a candidate visual adaptation, not a proven Framework/HWC fix, and was not copied into C24.
- C24 adds a post-fs-data diagnostic service sampling completion/boot-animation/service properties and key PIDs every 10s, plus bounded WindowManager, ActivityManager, SurfaceFlinger/display, layer/latency, and HOME-resolution dumps about once a minute for 15 minutes. It emits to logd/pmsg. The C24 run produced no `C24BootDiag` marker in console or pmsg, so service launch, script/log success, and output retention cannot be distinguished. The run did not change SELinux, GPU routing, HWC/vendor, kernel, fstab, encryption, or userdata.
- Static checks passed for EROFS readback/fsck, system AVB hashtree and vbmeta descriptor, LP layout, shell/Python/PowerShell syntax, and system_file xattrs. The first build attempt stopped on a reused AVB extent assertion when system grew by 4096 bytes; the second build updated the system descriptor and passed checks.
- Only `super` and `vbmeta_system_a` were flashed, both successfully. One C24 boot was observed for about 16m43s; the user saw only the first Xiaomi splash (`powered by Android`), not the HyperOS second screen with dots. ADB did not appear. No userdata/metadata erase, set_active, BCB write, PixelOS restore, other partition write, or Bootloader relock occurred.
- C24 Standalone full export contains 8 THYME_DIAG source files (20,977,071 bytes), all source/copy sizes and SHA-256 matched. `oops.raw` matches C13–C23 historical data; Standalone `dmesg_diag_boot.txt` is not Android C24 output. Host pre/postboot observation files are preserved separately. [C24 first-boot report](../reports/candidate24/C24_FIRST_BOOT_EVIDENCE_20260928.md), [complete raw evidence and host observations](../evidence/candidate24/framework_display/20260928_194944/).
- pmsg has no `C24BootDiag` marker, so no valid sampler count is available. It cannot establish system_server, WMS, SystemUI/HOME, bootanim exit, boot completion or physical present. A single enforcing `{ find }` AVC for `vendor.xiaomi.hardware.display.mihwcextension.IMiHwcExtension/default` repeats from C23 and is not proven causal.
## Validated history and remaining uncertainty

- C13 reached Android First/Second Stage, APEX, vold and `/data`; C14 bypassed the BPF/kernel-version restart gate.
- C16/C17 addressed graphics allocator `ion_device` read/open AVCs; the C17 retest did not reproduce those denials.
- C19/C20 repeatedly failed EGLConfig selection. C21's SkiaVk route passed that recorded failure but hit Vulkan RenderEngine initialization fatal. C22 passed that fatal and reached shader-cache prewarming.
- C23's visible `console-ramoops` contains one Recovery-mode boot instance: init skipped first-stage mounts for recovery mode and Recovery started. It records `bootonce-bootloader` and then clears BCB after Recovery starts; this does not establish why Recovery was selected or whether an earlier normal boot was overwritten.
- Host ADB was only `unauthorized`; no usable logcat was captured. The Standalone export copied all 7 accessible diagnostic-volume files (17,117,150 bytes) with source/copy SHA-256 matches. No pmsg was present; `oops.raw` matches the C22 historical residual, and Standalone dmesg belongs to the diagnostic environment.
- There is no C23 SurfaceFlinger, Skia, Vulkan, or shader-cache log. The effect of `service.sf.prime_shader_cache=0`, normal composition, and any progress to HyperOS UI are unknown.

## Next step
Do not repeat C24. First repair the diagnostic service's observable/readback path with explicit init-start, first-sample, periodic-sample and completion markers that are demonstrably recoverable from pstore/Standalone. Then perform a targeted read-only check of Xiaomi HWC extension registration, service label and client fallback; compare K40 only if the same interface exists. Do not grant a broad SELinux rule from the one AVC alone. Current device is A-slot Bootloader Fastboot, A retry=3; no `set_active` or boot-control change is warranted by current evidence.

## Public evidence
The evidence index covers user-authorized C13–C24 diagnostic evidence. C24 host observations and the complete accessible Standalone export are published with per-file source/public sizes and SHA-256 in the cumulative evidence manifest. Complete `misc.raw` and partition backups remain local. No ROMs, firmware packages, partition images, userdata/metadata images, credentials, or hardware-identity partition backups are included.

C23 Recovery follow-up: [recovery cause and A-slot retest preparation](../reports/candidate23/RECOVERY_RETEST_20260927.md). Earlier retest: [normal boot and BootAnimation evidence](../reports/candidate23/C23_RETEST_20260928.md). Latest: [complete boot-window report](../reports/candidate23/C23_LONG_BOOT_RETEST_20260928.md).
