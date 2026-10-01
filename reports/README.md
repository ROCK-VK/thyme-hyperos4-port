# Reports and boot evidence

Reports retain conclusions at the evidence level documented when they were written. Older reports are historical snapshots; the current project state and later execution records take precedence when results changed.

Some historical reports use emphatic phrases such as “100%” or “司法级”. These are original wording, not an independent certification; judge each claim by its listed validation and the linked primary evidence.

- `k40/` contains the three-way K40, Xiaomi 15 donor, and thyme comparison plus its review. It is a static package analysis, not a claim that every K40 change can be transplanted.
- `candidate13/` contains the Recovery/fs_mgr analysis and data-safety preparation report. The newer clean-data first-boot summary updates the earlier Recovery hypothesis.
- `candidate22/` documents the K40 Android 17 Vulkan UMD experiment and the real SurfaceFlinger shader-cache prewarm fatal from the C22 pmsg evidence.
- `candidate23/` documents the minimal `service.sf.prime_shader_cache=0` diagnostic bypass, host build checks, six-image manifest, and current pre-boot state. C23 runtime behavior remains unverified.
- `boot-logs/` contains selected text console, decoded pmsg, and USB/ADB/Fastboot timelines attributed to specific Candidate runs. Standalone's own boot log, binary pmsg containers, and historical `oops.raw` are excluded where they could be confused with Candidate evidence.

The C13 clean-data `console-ramoops` ends around 3.75 seconds after first-stage mount, dynamic policy compilation, enforcing second-stage init, and APEX bootstrap. It does not establish later HAL, vold, `/data`, boot animation, or desktop status. It is not a complete system log.

Raw `misc`/BCB, partition backups, `persist`, radio/NV/EFS data, user data, complete images, and vendor binaries are not published.

- reports/third_party_milo_hyperos4_audit_20260930/ contains the offline Milo package audit, file/image manifests, static Windows Fastboot and Recovery write plans, and the netd rc diff. Original executables, APK, firmware and images are excluded.
- `third_party_milo_c30_startup_diff_20260930/` contains a scoped four-way startup-tree comparison (Milo, C30, Xiaomi 15 donor, K40), small file/hash manifests, and the limited SELinux rule comparison. No ROM binaries are included; the report found no Milo-only fix ready to port into C31.

- `k40_milo_c30_author_change_sets_20260930/` records the K40/Milo/C30 blocker cross-check, candidate matrix, and direct EROFS readback of the BoringSSL init symlinks. It documents a C30 Zygote vendor-property AVC clue without asserting causality; no C31 patch was selected. No ROM, executable, APK, or raw partition dump is included.

- c30_zygote_vendor_property_avc_20260930/ contains the seven C30 Zygote property-area AVCs, C30 context/type mapping, the four-way vendor policy comparison using the latest Milo 4.0.11.0 upload, and DEX literal candidates. The report records a tight AVC-to-SIGABRT timing correlation but does not claim causality or select a C31 SELinux change.
- `c30_ultraframework_closure_20261001/` closes the C30 `UltraFrameworkComponentFactoryImpl` and Zygote vendor-property AVC review against the successful K40 Android 17 sample. It records the caught fallback, exact framework/preload hashes, seven raw AVC rows, K40 policy grants, and why the evidence is still insufficient for C31. No ROM or partition binaries are included.
- `c30_init_fatal_chain_20261001/` adds a focused C26-to-C30 netd/Zygote/init timeline. Five C30 `main` SIGABRTs end about 43 ms before PID1's sysrq panic, and the primary Zygote remains configured as critical; this supports a diagnostic hypothesis but does not prove PID/service identity or the init fatal trigger. No C31 was built, and no raw pstore or device dump is included.
- c31_diag_critical_20261001/ documents the C31-DIAG single-variable primary Zygote critical-escalation experiment, static build gates, restricted flash scope, and explicit unbooted runtime boundary. It contains text only; no images or raw device evidence.

- c31_diag_critical_20261001/C31_DIAG_RUNTIME_RESULT_20261001.md records the C31-DIAG controlled boot and complete local Standalone capture. It finds strong differential support for suppressed Zygote critical escalation, but the missing gate readback and init reap/fatal records leave the causal chain incomplete. Raw pstore/metadata/misc and device identifiers remain local.

- c32_diag_zygote_abort_20261001/ documents the C31 first primary-Zygote SIGABRT and the repeated crash_dump handshake EOF. It confirms the abort reason remains unknown, distinguishes static crash_dump/tombstoned assets from runtime helper success, and proposes one noncritical one-shot canary as the next diagnostic step. No raw pstore, metadata/misc, ROM, or device dump is included.
- c32_diag_crash_handler_20261001/ records the direct-instrumentation feasibility review of C31's actual runtime APEX linker64. The compiled handler is identified, but the inspected project build assets contain no matching Bionic source or validated APEX rebuild/signing path, so no C32 was produced. It defines one zygote-domain canary as the next isolation experiment; no raw evidence, ROM, APEX, or binary is published.

- `c32_diag_zygote_domain_canary_20261001/` records C32 static gates and the 2026-10-01 first boot. The canary produced a tombstone, while 97 real main SIGABRT PIDs match crash_dump helper failures; the runtime SELinux domain and real Zygote abort cause remain unknown. The report is `c32_diag_zygote_domain_canary_20261001/C32_FIRST_BOOT_RESULT_20261001.md`. The complete capture bundle (exact PMSG plus redacted text views and host timeline) is at `../evidence/candidate32/standalone/firstboot/run_20261001_224407/`; raw metadata/misc remain local.
