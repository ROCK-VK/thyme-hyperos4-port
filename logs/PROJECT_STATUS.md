# THYME-OS4 Project Status

Updated: 2026-10-01 20:19 HKT

## Goal and current milestone
Port Xiaomi 15 (dada) HyperOS 4 / Android 17 to Xiaomi 10S (thyme, Snapdragon 870). The active investigation is the first primary-Zygote SIGABRT and the missing debuggerd/crash_dump failure details. No formal startup fix has been established.

## Candidate and device
- C31-DIAG is the last known flashed Candidate on slot A. It booted once but did not reach the HyperOS second screen; ADB did not come online. The user later reported manually returning to Bootloader Fastboot.
- Last historical read-only slot state: A unbootable=no/successful=no/retry=2; B no/no/retry=7. The device was not queried during the current offline analysis, so this is not a live state.
- No C32 was built, flashed, or booted. No set_active, erase, metadata write, PixelOS restore, or device operation occurred.

## C31 first-scene evidence
- Init recorded primary Zygote PID 1059, secondary PID 1060, and netd PID 1044 at uptime 15.404966 s. The first `main SIGABRT` PID 1059 matches the primary Zygote PID.
- There are 103 distinct `main` SIGABRT PIDs, but init reap/service-PID lifecycle records are insufficient to call these 103 Zygote service restarts. There are also 103 distinct netd SIGABRT PIDs and 102 fingerprint HAL SIGSEGVs; no one-to-one causal mapping is established.
- Each Zygote crash retained only the generic `crash_dump helper failed to exec, or was killed` line. Abort reason/backtrace, handler fork/exec errno, crash_dump PID/status/signal, and tombstoned request result are absent.
- C31 `system/bin/linker64` resolves to `/apex/com.android.runtime/bin/linker64`. The actual ELF contains a debuggerd handler symbol and the generic EOF message. C31 runtime APEX SHA-256: `45A073DD…D36E595`; extracted linker64 SHA-256: `00E5DC0E…DA0ADB50`, Build ID `d8fc879ba0f57538f2e66cd324ffa7a3`. C30 has the same runtime APEX hash.
- Inspected project/build assets lack C31-matched Bionic/debuggerd source, a Soong platform tree, source revision proof, and a validated runtime-APEX rebuild/re-sign workflow. Upstream source or an unverified binary patch cannot produce a reproducible, trustworthy C32; this turn is Result C and did not build C32.
- C31 pstore through uptime 527.837 s has no C30-like PID1 sysrq panic seen around 32.922 s. This strongly supports, but does not directly prove, that `no_fatal.zygote` suppressed critical escalation. “Why Zygote aborts” and “whether its abort escalates to PID1 panic” remain separate questions.

## Next step
- The sole proposed isolation experiment is a one-shot, noncritical fixed-SIGABRT canary explicitly launched in the `zygote` SELinux domain, after static validation of init transition, executable type, policy, and trigger ordering. It must wait for tombstoned running and use independent init start/PID/stop markers; the first post-failure Unified First-Response Standalone capture must save pstore first.
- This canary uses the same Bionic handler/runtime APEX, crash_dump, and zygote domain, but does not reproduce real Zygote ART, seccomp, namespace, or process state. It has not been implemented or run. Do not build C32 before static feasibility is confirmed.
- Do not add SELinux permissions or change UltraFramework, ART, netd, fingerprint, graphics, kernel, or other startup behavior without direct evidence. A formal fix target remains unknown.

## Evidence and safety
- Full local C31 capture is under `work/reports/candidate31_diag_20261001/standalone/run_20261001_140648/`. Raw pstore, metadata/misc, Standalone dmesg, and host records remain local; public sync contains sanitized analysis only.
- C/D/E free space recorded for this turn: about 90.66/191.83/161.25 GiB, all above the 50 GiB gate. No cleanup; Docker untouched.
- No live device mode/slot was queried. Do not treat historical A retry=2 as current. New Candidate first boot still requires the user's explicit on-site confirmation.

## Reports
- Current report: `reports/c32_diag_crash_handler_20261001/C31_C32_HANDLER_INSTRUMENTATION_FEASIBILITY.md`
- Previous crash-dump evidence-gap report: `reports/c32_diag_zygote_abort_20261001/C31_CRASH_DUMP_FIRST_SCENE_GAP.md`
- This status and the linked feasibility report are published together as the current offline-analysis snapshot; no binary or raw device evidence is included.
