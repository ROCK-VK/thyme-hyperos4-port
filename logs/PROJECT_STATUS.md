# THYME-OS4 Project Status

## Goal

Port the Xiaomi 15 (dada) HyperOS 4 / Android 17 userspace to Xiaomi Mi 10S (thyme). Current priority is reaching HyperOS boot animation, setup wizard, or desktop by resolving SurfaceFlinger EGL initialization.

## Device and flashed build

- Target: Xiaomi Mi 10S (`thyme`); public materials redact the physical serial.
- C20 is installed in slot A; only `super` and `vbmeta_system_a` were written. One controlled C20 boot was attempted. The user saw a persistent Mi logo and manually returned the phone to Bootloader Fastboot.
- Latest read-only checks: one Fastboot device, `product=thyme`, slot A, unlocked bootloader, Bootloader Fastboot (not userspace fastboot), A-slot `unbootable=no`, `successful=no`, retry count 4; ADB is offline.
- No userdata/metadata erase, extra partition write, slot switch, BCB/misc modification, hardware `persist`, modemst, EFS/NV change, PixelOS restore, or bootloader relock occurred.

## C20 implementation and verification

- Based on the C19 RGBX experiment. Retains `ro.surface_flinger.default_composition_pixel_format=2`.
- Sets `persist.graphics.egl=angle` in system defaults and again after persistent `/data` properties load; removes the prior conflicting Adreno override.
- Adds process-scoped linker `dlopen`/`dlerror` diagnostics for `surfaceflinger` and `graphicsengine`. When ADB is available, the observer records relevant properties and process maps. These diagnostics are best-effort; runtime backend selection is not yet confirmed.
- No GPU/Vulkan, HWC/Gralloc, SELinux, kernel, vendor_boot, DTBO, fstab, encryption, or userdata/metadata changes.
- Build checks passed: final EROFS check and property/init readback; system AVB descriptor matched the rebuilt system; inherited product/system_ext descriptors and LP layout were checked; system extracted from super matched the built image byte-for-byte. Only `super` and `vbmeta_system_a` were flashed successfully.
- C20 has now booted once. Pstore confirms First/Second Stage, activated APEX, vold using the existing metadata key, and successful F2FS `/data` mount. SurfaceFlinger still logged 47 `no suitable EGLConfig found` aborts, all requesting format 2. No bootanimation or completed-boot evidence was recorded.
- The pmsg log contains no ANGLE/libEGL/linker route record; ADB never came online, so runtime EGL properties and process maps were unavailable. Whether ANGLE actually loaded remains unknown. `graphicsengine` SIGSEGV in `vkEnumeratePhysicalDevices+4` occurred about 0.48 seconds before the first EGL abort; causality is unproven.
- The full C20 Standalone export and host observer run are published under [`evidence/candidate20/`](../evidence/candidate20/). The `oops.raw` hash matches C19 and is treated as historical residue; Standalone dmesg is not a C20 log.

## Relevant validated history

- C13 reached Android First/Second Stage, APEX and `/data`; C14 bypassed the later BPF loader/kernel-version reboot gate.
- C16/C17 addressed graphics allocator `ion_device` read/open AVCs; C17 logs did not reproduce those allocator denials.
- C18 tested native Adreno routing without proving the actual backend.
- C19 proved that RGBX format 2 reached SurfaceFlinger, but 43 EGLConfig selection attempts still failed. A separate graphicsengine Vulkan enumeration SIGSEGV was observed; causality remains unproven.

## Next action

Do not repeat C20 or clear userdata/metadata. Prepare a minimal C21 diagnostic hook that logs runtime `persist.graphics.egl`/`ro.hardware.egl` and read-only EGL/GLES/Vulkan mappings for SurfaceFlinger and graphicsengine to logd/pmsg after SurfaceFlinger first starts. First verify the init hook is non-blocking and that the records persist to pmsg. Do not switch GPU libraries or widen SELinux without backend evidence.

## Key files

- C20 report: [`reports/candidate20/REPORT.md`](../reports/candidate20/REPORT.md)
- C20 build manifest: [`reports/candidate20/BUILD_MANIFEST.json`](../reports/candidate20/BUILD_MANIFEST.json)
- Build/flash/start/observer scripts: `tools/build_candidate20_angle_diag.py`, `tools/flash_candidate20_angle_diag.ps1`, `tools/start_candidate20_observed_boot.ps1`, `tools/observe_candidate13_readonly.py`
- Public evidence: [`evidence/README.md`](../evidence/README.md)
