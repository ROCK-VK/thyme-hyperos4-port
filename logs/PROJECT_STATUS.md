# THYME-OS4 Project Status

Last updated: 2026-09-27 (Hong Kong time)

## Goal and current stage

Port the Xiaomi 15 (`dada`) HyperOS 4 / Android 17 userspace to Xiaomi Mi 10S (`thyme`). The immediate goal is to pass graphics initialization and reach the boot animation, setup wizard, or desktop.

**Current stage: C23 has had one controlled attempt and only Recovery console evidence was saved; the cause remains unresolved. An Init-fatal-to-Recovery path is configured, but no ordinary Android fatal was captured. The current BCB fields are empty after Recovery cleared BCB. A-slot retry budget has been restored to 7; the phone remains in Bootloader Fastboot, waiting for the user to confirm they are present before a C23 retest.**

## Device and flashed build

- Latest read-only state: the device is thyme, A slot, unlocked, Bootloader Fastboot, not userspace Fastboot. A slot is unbootable=no, successful=no, retry count 7; B slot retry count 7. The one explicitly authorized fastboot set_active a returned OKAY. C23 has not been restarted.
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
Keep the device in Fastboot. After the user confirms they are beside the phone and ready to observe, start the read-only observer with candidate label C23-retest, wait for ARMED, then perform one controlled C23 boot. Do not build C24 or clear userdata/metadata without a concrete need.
If C23 re-enters Recovery, save that evidence and do not confirm wipe prompts; the current Recovery path remains unproven as the root cause.

## Public evidence
The evidence index covers user-authorized C13–C23 diagnostic evidence. C23's accessible raw export and host observations are published with per-file source/public sizes and SHA-256 in the cumulative evidence manifest. The Recovery follow-up report is linked below; complete `misc.raw` and raw diagnostic state containing device identifiers remain local. No ROMs, firmware packages, partition images, userdata/metadata images, credentials, or hardware-identity partition backups are included.

C23 Recovery follow-up: [recovery cause and A-slot retest preparation](../reports/candidate23/RECOVERY_RETEST_20260927.md).
