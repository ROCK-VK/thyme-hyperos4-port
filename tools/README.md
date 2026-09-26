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
- `build_standalone_diag.py` — builds the RAM-only diagnostic environment; it does not represent a partition-flashing tool.
- `audit_candidate8_property_contexts.py`, `audit_c13_selinux.py`, `audit_salvaged_ramoops.py` — focused policy and pstore analysis helpers.
- `precheck_candidate*.py` — Candidate-specific host and artifact preconditions; a PASS does not establish successful device boot.

Some historical build scripts contain the generic WSL root `/path/to/thyme-os4-local` in place of the original machine path. Set the local project root and required ROM/build inputs before using them.

Device serials and private host paths are sanitized in the public copies. Supply the intended local device serial explicitly to the Candidate 15 flash precheck with `-Serial`; set the serial in the older observation/startup/RAM-export scripts before using them. Do not treat a published placeholder as a device identity check.

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
- `restore_pixelos_a0_prime.ps1` — can write the six PixelOS A0′ recovery partitions when explicitly invoked in execute mode.

**Device-operation warning:** flash/restore scripts write partitions, `start_candidate13_observed_boot.ps1 -Execute` starts Android, and a salvage script with its explicit flag uses `fastboot boot` to start a RAM diagnostic image. These are included as engineering tools, not as permission to operate a device. The scripts expect local images not included here; review device identity, slot, image provenance, size, and hash and obtain the required authorization before use.

## Runtime requirements

The original workflow used Windows 11, WSL Ubuntu, local Android platform-tools, and project-specific extraction/AVB/LP/EROFS/SELinux tools. Exact versions and required local inputs vary by script. No third-party executable distributions or full ROMs are included.
