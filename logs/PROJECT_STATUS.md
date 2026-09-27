# THYME-OS4 Project Status

## Goal and current stage

Port the Xiaomi 15 (dada) HyperOS 4 / Android 17 userspace to Xiaomi Mi 10S (thyme). The immediate goal is to pass graphics initialization and reach the boot animation, setup wizard, or desktop.

**Current stage: Candidate 22 is built and flashed to the A slot; first boot is pending the user's onsite confirmation.**

## Device and flashed build

- Latest read-only Fastboot state after C22: one target, `product=thyme`, slot A, unlocked Bootloader Fastboot (not userspace Fastboot), A slot `unbootable=no`, retry count 3.
- C22 wrote only `super` and `vbmeta_a`; `boot_a`, `vendor_boot_a`, `dtbo_a`, and `vbmeta_system_a` were inherited unchanged from the established candidate base.
- No C22 reboot, userdata/metadata erase, slot switch, other partition write, misc/BCB edit, hardware identity change, or Bootloader relock occurred.
- C22 remains unstarted. User has reported the phone is manually in Fastboot.

## C21 result

- C21 reached Android Second Stage, APEX Bootstrap, vold, and `/data` initialization. SurfaceFlinger then repeatedly aborted with `Could not initialize Vulkan RenderEngine!` in `SkiaVkRenderEngine::createContexts()`; no boot animation, setup wizard, or desktop evidence was obtained.
- A separate `graphicsengine` process hit a null-pointer SIGSEGV at `vkEnumeratePhysicalDevices+4` about 0.08 seconds before the first SurfaceFlinger fatal. Timing is established; causality is not.
- Complete accessible C21 host-observation and Standalone export copies are under [`evidence/candidate21/`](../evidence/candidate21/). The public copies redact device serial `[REDACTED_DEVICE_ID]`; local originals are unchanged. `PUBLIC_EVIDENCE_MANIFEST.csv` records source and published checksums.
- `oops.raw` is a 2026-06-17 historical artifact, not a C21 crash record; Standalone `dmesg_diag_boot.txt` belongs to the diagnostic environment.

## C22 implementation and host checks

C22 replaces the vendor Vulkan ICD with the cached K40 OS4.0.0.8 Android 17 ICD and adds isolated K40 GSL/Adreno Utils/LLVM support libraries for the Vulkan dependency path. The original thyme EGL/GLES, Gralloc/HWC, kernel, and device-specific boot stack are retained.

The build passed vendor `e2fsck -f -n`, AVB footer/hashtree verification, root-vbmeta vendor descriptor checks, and LP layout checks. `super.img` is 7,701,892,056 bytes with SHA-256 `6145D602D17321EFF1AD55A7AC10B9314AF9E7C23C0BD60D681115CD54B1330D`; `vbmeta.img` for `vbmeta_a` is 131,072 bytes with SHA-256 `66A53C2EC38247193CC86B7F5DE887556864413D1142C3C1994645DE1E3BAB10`. Runtime compatibility with thyme Linux 4.19/KGSL is unverified.

- [C22 report](../reports/candidate22/REPORT.md)
- [C22 build manifest](../reports/candidate22/BUILD_MANIFEST.json)
- [C22 build script](../tools/build_candidate22_k40_vulkan_umd.py)
- [C22 restricted flash script](../tools/flash_candidate22_k40_vulkan_umd.ps1)
- [C22 observed-start gate](../tools/start_candidate22_observed_boot.ps1)
- [Read-only observer](../tools/observe_candidate13_readonly.py)

## Validated history and remaining uncertainty

- C13 reached First/Second Stage, APEX, vold, and `/data`; C14 bypassed the BPF/kernel-version restart gate.
- C16/C17 addressed graphics allocator `ion_device` read/open AVCs; C17 logs did not reproduce those denials.
- C19/C20 reached graphics startup but repeatedly failed EGLConfig selection. C21's SkiaVk route avoided that recorded EGLConfig fatal but failed Vulkan RenderEngine initialization.
- C22's K40 Vulkan UMD/GSL/LLVM pairing is a host-built compatibility experiment. It is not yet proven to load or run on thyme.

## Next step

After the user confirms they are onsite and ready to observe, start the C22 read-only observer, verify `ARMED`, then use the C22 start gate for one controlled boot. Do not erase userdata/metadata or restore PixelOS before obtaining C22 evidence. If it fails, return to Fastboot and preserve the complete Standalone diagnostic volume before analysis.

## Public evidence

The evidence index covers C13–C21. Candidate 21 public files have serial redactions and source/public hashes; earlier Candidate directories retain their established publication format. No ROMs, firmware packages, partition images, userdata/metadata images, credentials, or hardware-identity partition backups are included.
