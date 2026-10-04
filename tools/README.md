# Tools in this repository

This folder is a curated subset of scripts from the full local workspace. The required donor ROMs, WSL build roots, extracted partition trees, prebuilt diagnostic images, and recovery image payloads are intentionally absent. Most build and precheck scripts therefore document a workflow and need local project inputs before they can run.

## Build and host-side checks

- `build_candidate9.py` — Candidate 9 Property Contexts repair build.
- `build_candidate10_warm_dtb.py` — Candidate 10 WarmDtb diagnostic build.
- `build_candidate11.py` — Candidate 11 system_ext metadata/APEX fix.
- `build_candidate12.py` — Candidate 12 `/dev/ion` label repair.
- `build_candidate13.py` — Candidate 13 Keymaster/Gatekeeper policy update.
- `build_candidate13_1_data_guard.py` — untested host-side C13.1 fstab variant.
- `build_candidate14_bpf_bootstrap_bypass.py` — rebuilds the BPF init bypass used to pass the C13 reboot gate.
- `build_candidate15_angle_egl.py` — starts from the verified C14 artifacts and adds the Android 17 ANGLE EGL selector; local system/build inputs are required.
- `build_candidate16_graphics_allocator_ion.py` and `build_candidate17_graphics_allocator_open.py` — add only the graphics allocator ion_device permissions directly observed in C14–C16 logs; C17 extends the exact runtime domain permission to `open read`.
- `build_candidate18_native_adreno.py` — rebuilds system, vbmeta_system, and super from the C17 baseline to select thyme's declared native Adreno EGL route; it does not replace vendor GPU binaries or modify SELinux.
- `build_candidate20_angle_diag.py` — builds the C20 ANGLE route and process-scoped linker diagnostic variant from the C19 baseline; required local images/build inputs are not included.
- `build_candidate21_k40_vk_renderengine.py`, `build_candidate22_k40_vulkan_umd.py`, and `build_candidate23_sf_prime_skip.py` — focused graphics-startup experiments. C21 selects the K40 SkiaVk route; C22 pairs its Vulkan ICD with isolated K40 UMD dependencies; C23 skips the shader-cache prewarm path seen in the C22 fatal stack. Local ROM/build inputs are required.
- `build_standalone_diag.py` — builds the RAM-only diagnostic environment; it does not represent a partition-flashing tool.
- `audit_candidate8_property_contexts.py`, `audit_c13_selinux.py`, `audit_salvaged_ramoops.py` — focused policy and pstore analysis helpers.
- `precheck_candidate*.py` — Candidate-specific host and artifact preconditions; a PASS does not establish successful device boot.

Some historical build scripts contain the generic WSL root `/path/to/thyme-os4-local` in place of the original machine path. Set the local project root and required ROM/build inputs before using them.

Device serials and private host paths are sanitized in the public copies. Supply the intended local device serial explicitly with `-Serial` to Candidate 15, C18, and C20 flash/start scripts; the C20 Python observer requires `--serial`. Older observation/startup/RAM-export scripts may need their serial configured before use. Do not treat a published placeholder as a device identity check.

## Device observation, recovery, and writing

- `observe_candidate13_readonly.py` — ADB/Fastboot polling and read-only startup evidence capture.
- `start_candidate13_observed_boot.ps1` — checks a fresh observer arm record and Fastboot identity; default is dry-run, and `-Execute` issues one `fastboot reboot` only after separate startup authorization.
- `record_candidate13_event.ps1` — records operator screen observations with UTC timestamps in the same run directory.
- `salvage_c10_diag.py` through `salvage_c13_diag.py` — Standalone RAM-boot evidence export helpers. A `fastboot boot` temporarily starts an image in RAM; inspect each script and image source before use.
- `salvage_c13_diag.py` defaults to a host-only image hash check; a separately authorized RAM start requires the explicit `--execute-authorized-ram-boot` flag. It requires one `THYME_DIAG` volume and Standalone evidence markers before copying.
- `flash_candidate13.ps1` — can write the six Candidate 13 target partitions when explicitly invoked in execute mode.
- `flash_candidate14_bpf_bootstrap_bypass.ps1` — defaults to Dry-Run; explicit execute mode can write only `vbmeta_system_a` and `super` and leaves the phone in Fastboot.
- `flash_candidate15_angle_egl.ps1` — defaults to Dry-Run; accepts `-Serial`, and explicit execute mode can write only the C15 `vbmeta_system_a` and `super` images and leaves the phone in Fastboot.
- `flash_candidate16_graphics_allocator_ion.ps1` and `flash_candidate17_graphics_allocator_open.ps1` — default to Dry-Run; explicit execute mode writes only the corresponding Candidate `vbmeta_system_a` and `super` images and does not reboot.
- `flash_candidate18_native_adreno.ps1` — defaults to Dry-Run; explicit execute mode verifies the C18 manifest and target, then sequentially writes only `super` and `vbmeta_system_a` without rebooting or erasing data.
- `flash_candidate20_angle_diag.ps1` — defaults to Dry-Run; requires an explicit `-Serial` and execute switch to write only `super` and `vbmeta_system_a`, without rebooting or erasing data.
- `flash_candidate23_sf_prime_skip.ps1` — defaults to Dry-Run; requires an explicit `-Serial` and execute switch to write only `super` and `vbmeta_system_a`, without rebooting or erasing data.
- `start_candidate20_observed_boot.ps1` — validates the C20 observer ARMED record and requires a separate user-watching confirmation before one Fastboot reboot.
- `start_candidate23_observed_boot.ps1` — validates the C23 observer ARMED record and requires a separate user-watching confirmation before one Fastboot reboot.
- `start_candidate18_observed_boot.ps1` — checks a fresh `C18-native-adreno` observer ARMED record and Fastboot identity; execution also requires an explicit user-watching confirmation before one Fastboot reboot.
- `restore_pixelos_a0_prime.ps1` — can write the six PixelOS A0′ recovery partitions when explicitly invoked in execute mode.

**Device-operation warning:** flash/restore scripts write partitions, `start_candidate13_observed_boot.ps1 -Execute` starts Android, and a salvage script with its explicit flag uses `fastboot boot` to start a RAM diagnostic image. These are included as engineering tools, not as permission to operate a device. The scripts expect local images not included here; review device identity, slot, image provenance, size, and hash and obtain the required authorization before use.

## Runtime requirements

The original workflow used Windows 11, WSL Ubuntu, local Android platform-tools, and project-specific extraction/AVB/LP/EROFS/SELinux tools. Exact versions and required local inputs vary by script. No third-party executable distributions or full ROMs are included.

## Candidate 21

- build_candidate21_k40_vk_renderengine.py applies the K40 OS4 SkiaVk RenderEngine routing properties to the C20 system tree. Required ROM and build inputs are not included.
- flash_candidate21_k40_vk_renderengine.ps1 defaults to Dry-Run. With an explicit Serial and Execute switch, it writes only super and vbmeta_system_a; it does not reboot or erase data.
- start_candidate21_observed_boot.ps1 validates a fresh C21 observer ARMED record and explicit onsite confirmation before one Fastboot reboot.
- The public C21 flash/start scripts require an explicit Serial parameter. Review all local inputs and device checks before use.

## Candidate 22

- `build_candidate22_k40_vulkan_umd.py` builds the C22 Vulkan UMD compatibility experiment from the local C21/vendor inputs; those ROM/build inputs are not included.
- `flash_candidate22_k40_vulkan_umd.ps1` defaults to Dry-Run. Supply `-Serial` and `-Execute` to write only `super` and `vbmeta_a`; it does not reboot or erase data.
- `start_candidate22_observed_boot.ps1` requires `-RunDir`, `-Serial`, `-Execute`, and `-UserWatchingConfirmed`; it verifies a fresh C22 observer ARMED record and device/slot state before one Fastboot reboot.
- Public C22 scripts require the target serial explicitly rather than embedding a machine-specific default.

## Candidate 23

- `build_candidate23_sf_prime_skip.py` sets `service.sf.prime_shader_cache=0` to bypass only the optional shader-cache prewarm implicated by C22's SurfaceFlinger fatal; this is diagnostic, not a proven regular-composition fix.
- `flash_candidate23_sf_prime_skip.ps1` defaults to Dry-Run and requires `-Serial` and `-Execute` to write only `super` and `vbmeta_system_a`.
- `start_candidate23_observed_boot.ps1` requires a fresh C23 observer ARMED record, `-Serial`, and the explicit user-watching confirmation before a single Fastboot reboot.
- C23's user-space BootAnimation code emitted a shown-timing record, but the user observed only the static Xiaomi logo and no boot-complete/UI evidence was captured. Do not describe the property bypass as a verified visible animation or a fix for the underlying output-buffer usage issue.

## Candidate 24

- `build_candidate24_framework_display_diag.py` builds a diagnostic-only system addition from the local C23 inputs; ROM/build inputs and generated images are not included.
- `candidate24_bootdiag/` contains the init service and script. It samples boot completion, boot-animation/service properties, process PIDs, WindowManager/ActivityManager, SurfaceFlinger/display state and HOME resolution to logd/pmsg for up to 15 minutes. Actual execution and pmsg retention remain unverified until C24 boots.
- `flash_candidate24_framework_display_diag.ps1` requires an explicit `-Serial` and `-Execute`; it writes only `super` and `vbmeta_system_a` and does not reboot or erase data.
- See [C24 diagnostic report](../reports/candidate24/C23_FRAMEWORK_DISPLAY_C24_DIAGNOSTIC_20260928.md), [build report](../reports/candidate24/BUILD_REPORT.md), and [manifest](../reports/candidate24/BUILD_MANIFEST.json).

## Candidate 25

- build_candidate25_first_screen_diag.py replaces the C24 unverified logd-only sampler with a bounded persistent Framework/display sampler. ROM inputs and generated images are not included.
- candidate25_bootdiag contains the native AArch64 helper, init service and narrow CIL fragment. Samples are capped and written to logd plus a dedicated metadata directory; real startup behavior remains unverified until C25 boots.
- flash_candidate25_first_screen_diag.ps1 requires an explicit serial and Execute switch; it writes only super and vbmeta_system_a and never reboots.
- start_candidate25_observed_boot.ps1 verifies a fresh C25 ARMED record and current device/slot state. It defaults to no reboot; a single reboot requires both Execute and UserWatchingConfirmed.
- See the [C25 build and flash report](../reports/candidate25/C25_FIRST_SCREEN_DIAGNOSTIC_BUILD_FLASH_20260928.md).

## Candidate 40 to Candidate 43 Tools

- `build_candidate40.py` — Builds Candidate 40 system image injecting single-variable `ro.media.xml_variant.codecs=_V1_0` into `system/build.prop`, resolving the Zygote MediaProfiles fatal crash.
- `flash_candidate40.ps1` — Restrictive flashing tool writing `super` and `vbmeta_system_a` for Candidate 40 with strict prechecks.
- `build_candidate42.py` — Builds Candidate 42 updating `/vendor/etc/displayconfig/display_id_4630946545580055169.xml` minimum brightness point from `0.001709819` to `0.000854597`, resolving `DisplayDeviceConfig` crashes.
- `verify_c42_build_gates.py` — 12-gate build verification suite verifying byte-diff, XML structure, AVB descriptors, and partition integrity for Candidate 42.
- `flash_candidate42.ps1` — Restrictive flashing tool for Candidate 42 with slot-budget verification.
- `build_candidate43.py` — Builds Candidate 43 with minimal 4-byte NOP patch to `/apex/com.android.tethering/lib64/libnetd_updatable.so` resolving netd eBPF abort loops on Linux 4.19, resigning APEX with dual-layer APK Signature Scheme v3.
- `verify_c43_build_gate.py` — 6-gate deep verification script covering SO binary/ELF, APEX container & v3 signature, EROFS fsck, AVB root digest, Super LP metadata, and strict single-variable isolation.
- `flash_candidate43.ps1` — Restrictive flashing script for Candidate 43 featuring `-RestoreRetryBudget` logic to safely restore slot A retry budget to 7.

## Candidate 44 Tools

- `build_candidate44.py` — Builds Candidate 44 by dynamically injecting the exact AVB root digest (`4bdfe2f9...`) of `apex_payload.img` into outer `apex_manifest.pb.capexMetadata.originalApexDigest`, retaining C43's patched inner `original_apex` byte-for-byte, and enforcing 8-fold runtime equivalence build gates.
- `flash_candidate44.ps1` — Restrictive flashing script for Candidate 44 with `-RestoreRetryBudget` logic and post-flash Fastboot hold state.
- `start_candidate44_observed_boot.ps1` — Controlled observation boot script for Candidate 44 issuing `fastboot reboot` with timeout protection.
- `salvage_c44_when_ready.py` — Standalone RAM diagnostic export tool for Candidate 44 non-destructively salvaging `console-ramoops-0`, `pmsg-ramoops-0`, and diagnostics files from RAM.

