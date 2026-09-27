# THYME-OS4 Project Status

Last updated: 2026-09-27 (Hong Kong time)

## Goal and current stage

Port the Xiaomi 15 (`dada`) HyperOS 4 / Android 17 userspace to Xiaomi Mi 10S (`thyme`). The immediate goal is to pass graphics initialization and reach the boot animation, setup wizard, or desktop.

**Current stage: Candidate 23 is built and flashed; its first boot is waiting for the user's on-site confirmation.**

## Device and flashed build

- Latest post-flash read-only state: `product=thyme`, A slot, unlocked Bootloader Fastboot (not userspace Fastboot), A slot `unbootable=no`, `successful=no`, retry count 2.
- C23 wrote only `super` and `vbmeta_system_a`. The inherited boot, vendor_boot, dtbo and root vbmeta were not rewritten.
- No C23 boot, userdata/metadata erase, slot change, BCB edit, other partition write, hardware identity change, or Bootloader relock has occurred.
- The phone remains in Fastboot. Do not treat the host-side build or flash as a successful Android boot.

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
- C23 has not been booted. Whether SurfaceFlinger skips prewarming, whether normal output buffers work, and whether HyperOS reaches boot animation or later UI are unknown.

## Next step

Wait for the user to confirm they are present and ready to observe. Then start the C23 read-only observer, verify `ARMED`, and use the C23 observed-start gate for one controlled first boot. If it fails, return to Fastboot and preserve the full Standalone diagnostic volume before analysis. Do not erase userdata/metadata without a new specific need and authorization.

## Public evidence

The evidence index covers complete user-authorized C13–C22 diagnostic evidence. C22's accessible raw export and host observations were copied byte-for-byte with per-file source/public hashes. No ROMs, firmware packages, partition images, userdata/metadata images, credentials, or hardware-identity partition backups are included.
