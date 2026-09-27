# THYME-OS4 Project Status

## Goal and current stage

Port the Xiaomi 15 (dada) HyperOS 4 / Android 17 userspace to Xiaomi Mi 10S (thyme). The immediate goal is to reach the HyperOS boot animation, setup wizard, or desktop.

**Current stage: Candidate 21 is built and flashed; first boot is waiting for the user's onsite confirmation.**

## Device and flashed build

- Latest read-only Fastboot check: one device, product=thyme, slot A, unlocked Bootloader Fastboot (not userspace fastboot); A slot unbootable=no, successful=no, retry count 4.
- C21 wrote only super and vbmeta_system_a; inherited boot/vendor_boot/dtbo/vbmeta remain unchanged from C20.
- No reboot, userdata/metadata erase, other partition write, slot change, BCB/misc edit, hardware identity change, or Bootloader relock occurred in the C21 step.
- C21 has not booted. SkiaVk selection and thyme Vulkan initialization are unverified.

## C21 implementation

Based on C20, C21 added the K40 OS4.0.0.8 Android 17 profile:
- debug.renderengine.vulkan=true
- debug.renderengine.backend=skiavkthreaded
- debug.hwui.renderer=skiavk

It retains C20 ANGLE routing, RGBX format 2, validated prior boot fixes, and the thyme kernel/vendor graphics stack. No K40 vendor/Vulkan/Gralloc/HWC binaries were copied.

The K40 system EGL/SurfaceFlinger/RenderEngine libraries matched the Xiaomi 15 donor and C20; its relevant adaptation was framework RenderEngine routing. C20 pmsg proves that SurfaceFlinger repeatedly failed SkiaGLRenderEngine::chooseEglConfig(), but does not identify the EGL backend behind the generic Android META-EGL frontend or report EGLConfig counts. C20 also recorded a separate graphicsengine Vulkan enumeration SIGSEGV; its relationship to the SurfaceFlinger failure is unproven.

## Build and flash

- [C21 report](../reports/candidate21/REPORT.md)
- [C21 image manifest](../reports/candidate21/BUILD_MANIFEST.json)
- [C21 build script](../tools/build_candidate21_k40_vk_renderengine.py)
- [C21 flash script](../tools/flash_candidate21_k40_vk_renderengine.ps1)
- [C21 observed-start gate](../tools/start_candidate21_observed_boot.ps1)
- [Read-only observer](../tools/observe_candidate13_readonly.py)

Build checks recorded in the report include final EROFS validation, property readback, system AVB descriptor and LP layout checks, and inherited boot image identity. C21 has not received device-side startup validation.

## Validated history

- C13 reached Android First/Second Stage, APEX, vold, and /data; C14 bypassed the BPF/kernel-version reboot gate.
- C16/C17 addressed graphics allocator ion_device read/open AVCs; C17 logs did not reproduce those denials.
- C19/C20 continued to reach graphics startup, but SurfaceFlinger repeatedly failed EGLConfig selection with format 2.
- C21 tries the K40 threaded SkiaVk RenderEngine route to bypass the failing SkiaGL EGLConfig path. Vulkan initialization on thyme remains to be tested.

## Next step

After the user confirms they are onsite and ready to observe, arm the C21 read-only observer and execute one controlled first boot. Do not repeat the flash or erase data before that test. If startup fails, return to Fastboot and preserve the full Standalone diagnostic volume before analysis.

## Public evidence

Raw diagnostic evidence through C20 is indexed in [evidence/README.md](../evidence/README.md). No C21 startup evidence exists yet. This repository excludes full ROMs, firmware packages, partition images, user-data backups, credentials, and hardware identity backups.