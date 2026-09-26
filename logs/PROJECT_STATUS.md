# THYME-OS4 Project Status

## Goal

Port the Xiaomi 15 (dada) HyperOS 4 / Android 17 userspace to Xiaomi Mi 10S (thyme). Current priority is reaching HyperOS boot animation, setup wizard, or desktop by resolving SurfaceFlinger EGL initialization.

## Device and flashed build

- Target: Xiaomi Mi 10S (`thyme`); public materials redact the physical serial.
- C20 is flashed to slot A: only `super` and `vbmeta_system_a` were written. The phone remains in Bootloader Fastboot and C20 has not booted.
- Read-only post-flash checks reported `product=thyme`, slot A, unlocked bootloader, Bootloader Fastboot (not userspace fastboot), and A-slot `unbootable=no`.
- No userdata/metadata erase, other partition write, slot switch, BCB/misc modification, hardware `persist`, modemst, EFS/NV change, or bootloader relock occurred. PixelOS has not been restored.

## C20 implementation and verification

- Based on the C19 RGBX experiment. Retains `ro.surface_flinger.default_composition_pixel_format=2`.
- Sets `persist.graphics.egl=angle` in system defaults and again after persistent `/data` properties load; removes the prior conflicting Adreno override.
- Adds process-scoped linker `dlopen`/`dlerror` diagnostics for `surfaceflinger` and `graphicsengine`. When ADB is available, the observer records relevant properties and process maps. These diagnostics are best-effort; runtime backend selection is not yet confirmed.
- No GPU/Vulkan, HWC/Gralloc, SELinux, kernel, vendor_boot, DTBO, fstab, encryption, or userdata/metadata changes.
- Build checks passed: final EROFS check and property/init readback; system AVB descriptor matched the rebuilt system; inherited product/system_ext descriptors and LP layout were checked; system extracted from super matched the built image byte-for-byte. Only `super` and `vbmeta_system_a` were flashed successfully.
- C20 runtime behavior, actual ANGLE loading, EGLConfig result, Vulkan interaction, and UI progress are unknown until first boot.

## Relevant validated history

- C13 reached Android First/Second Stage, APEX and `/data`; C14 bypassed the later BPF loader/kernel-version reboot gate.
- C16/C17 addressed graphics allocator `ion_device` read/open AVCs; C17 logs did not reproduce those allocator denials.
- C18 tested native Adreno routing without proving the actual backend.
- C19 proved that RGBX format 2 reached SurfaceFlinger, but 43 EGLConfig selection attempts still failed. A separate graphicsengine Vulkan enumeration SIGSEGV was observed; causality remains unproven.

## Next action

Wait for the user to confirm they are present to observe. Then arm the C20 observer (`C20-angle-route-diag`) before one controlled first boot. If ADB comes online, capture full logcat, runtime properties, and SurfaceFlinger/graphicsengine maps. If boot fails, return to Fastboot and preserve the full Standalone diagnostic volume before analysis. Do not infer ANGLE loading from property text alone.

## Key files

- C20 report: [`reports/candidate20/REPORT.md`](../reports/candidate20/REPORT.md)
- C20 build manifest: [`reports/candidate20/BUILD_MANIFEST.json`](../reports/candidate20/BUILD_MANIFEST.json)
- Build/flash/start/observer scripts: `tools/build_candidate20_angle_diag.py`, `tools/flash_candidate20_angle_diag.ps1`, `tools/start_candidate20_observed_boot.ps1`, `tools/observe_candidate13_readonly.py`
- Public evidence: [`evidence/README.md`](../evidence/README.md)