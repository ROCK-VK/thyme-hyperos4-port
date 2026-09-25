# Tools in this repository

This folder is a curated subset of scripts from the full local workspace. The required donor ROMs, WSL build roots, extracted partition trees, prebuilt diagnostic images, and recovery image payloads are intentionally absent. Most build and precheck scripts therefore document a workflow and need local project inputs before they can run.

## Build and host-side checks

- `build_candidate9.py` — Candidate 9 Property Contexts repair build.
- `build_candidate10_warm_dtb.py` — Candidate 10 WarmDtb diagnostic build.
- `build_candidate11.py` — Candidate 11 system_ext metadata/APEX fix.
- `build_candidate12.py` — Candidate 12 `/dev/ion` label repair.
- `build_candidate13.py` — Candidate 13 Keymaster/Gatekeeper policy update.
- `build_candidate13_1_data_guard.py` — untested host-side C13.1 fstab variant.
- `build_standalone_diag.py` — builds the RAM-only diagnostic environment; it does not represent a partition-flashing tool.
- `audit_candidate8_property_contexts.py`, `audit_c13_selinux.py`, `audit_salvaged_ramoops.py` — focused policy and pstore analysis helpers.
- `precheck_candidate*.py` — Candidate-specific host and artifact preconditions; a PASS does not establish successful device boot.

## Device observation, recovery, and writing

- `observe_candidate13_readonly.py` — ADB/Fastboot polling and read-only startup evidence capture.
- `salvage_c10_diag.py` through `salvage_c13_diag.py` — Standalone RAM-boot evidence export helpers. A `fastboot boot` temporarily starts an image in RAM; inspect each script and image source before use.
- `flash_candidate13.ps1` — can write the six Candidate 13 target partitions when explicitly invoked in execute mode.
- `restore_pixelos_a0_prime.ps1` — can write the six PixelOS A0′ recovery partitions when explicitly invoked in execute mode.

**Device-writing warning:** the flash and restore scripts can modify partition contents. They are included as historical engineering artifacts, not as a recommendation to run them. They expect local images that are not included here. Review the script and verify device, slot, image provenance, size, and hash before any authorized use. These scripts do not grant permission to flash a device.

## Runtime requirements

The original workflow used Windows 11, WSL Ubuntu, local Android platform-tools, and project-specific extraction/AVB/LP/EROFS/SELinux tools. Exact versions and required local inputs vary by script. No third-party executable distributions or full ROMs are included.
