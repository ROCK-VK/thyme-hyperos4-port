# THYME-OS4 Project Status

Last updated: 2026-09-27 (Hong Kong time)

## Goal and current stage

Port the Xiaomi 15 (`dada`) HyperOS 4 / Android 17 userspace to Xiaomi Mi 10S (`thyme`). The immediate goal is to pass graphics initialization and reach the boot animation, setup wizard, or desktop.

**Current stage: C23 has had one controlled boot attempt; the saved console is a PixelOS Recovery instance, and the cause of Recovery selection is unknown. C23's SurfaceFlinger experiment has not been evaluated.**

## Device and flashed build

- Latest read-only state after the user manually returned to Bootloader Fastboot: unique device, `product=thyme`, A slot, unlocked, not userspace Fastboot, A slot `unbootable=no`, `successful=no`, retry count 1. The pre-boot retry count was 2.
- C23 wrote only `super` and `vbmeta_system_a`. The inherited boot, vendor_boot, dtbo and root vbmeta were not rewritten.
- One C23 `fastboot reboot` was executed after the observer was ARMED. No userdata/metadata erase, slot change, BCB edit, other partition write, hardware identity change, PixelOS restore, or Bootloader relock occurred.
- The phone is currently in Fastboot. Do not treat the C23 build or flash as a successful Android boot.

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

## Validated history and remaining uncertainty

- C13 reached Android First/Second Stage, APEX, vold and `/data`; C14 bypassed the BPF/kernel-version restart gate.
- C16/C17 addressed graphics allocator `ion_device` read/open AVCs; the C17 retest did not reproduce those denials.
- C19/C20 repeatedly failed EGLConfig selection. C21's SkiaVk route passed that recorded failure but hit Vulkan RenderEngine initialization fatal. C22 passed that fatal and reached shader-cache prewarming.
- C23's visible `console-ramoops` contains one Recovery-mode boot instance: init skipped first-stage mounts for recovery mode and Recovery started. It records `bootonce-bootloader` and then clears BCB after Recovery starts; this does not establish why Recovery was selected or whether an earlier normal boot was overwritten.
- Host ADB was only `unauthorized`; no usable logcat was captured. The Standalone export copied all 7 accessible diagnostic-volume files (17,117,150 bytes) with source/copy SHA-256 matches. No pmsg was present; `oops.raw` matches the C22 historical residual, and Standalone dmesg belongs to the diagnostic environment.
- There is no C23 SurfaceFlinger, Skia, Vulkan, or shader-cache log. The effect of `service.sf.prime_shader_cache=0`, normal composition, and any progress to HyperOS UI are unknown.

## Next step

Do not repeat C23 or build C24 yet. First determine the most useful read-only way to distinguish a direct Recovery request from a later Recovery boot; preserve current Fastboot state and evidence. If another normal boot is proposed, arm the observer first and get the user's on-site confirmation. Do not erase userdata/metadata without a specific need and authorization.

## Public evidence

The evidence index covers user-authorized C13–C23 diagnostic evidence. C23's accessible raw export and host observations are published with per-file source/public sizes and SHA-256 in the cumulative evidence manifest. No ROMs, firmware packages, partition images, userdata/metadata images, credentials, or hardware-identity partition backups are included.
