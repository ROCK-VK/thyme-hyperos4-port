# THYME-OS4 Project Status

Updated: 2026-10-01 14:27 HKT

## Goal and current milestone
Port Xiaomi 15 (dada) HyperOS 4 / Android 17 to Xiaomi 10S (thyme, Snapdragon 870). Current work is to identify the primary Zygote main SIGABRT cause and determine whether C30's PID1 panic was caused by critical-service escalation.

## Candidate and device
- C31-DIAG remains flashed to slot A and has been booted once. It did not reach the HyperOS second screen or desktop.
- The user saw only the static Xiaomi first screen; ADB never became available. Host Fastboot reappeared about 539.124 seconds after the reboot command; the user confirmed returning manually.
- Last read-only slot state: thyme, slot A, unlocked, non-userspace Fastboot. A unbootable=no/successful=no/retry=2; B no/no/retry=7. The user confirmed the phone is back in Bootloader Fastboot.
- Exactly one C31-DIAG reboot was issued. No set_active, partition flash, erase, metadata write, or PixelOS restore occurred during the runtime/capture phase. The only subsequent device action was a RAM boot of Unified First-Response Standalone.
- C31-DIAG is a diagnostic image, not a startup fix. No C32 was built.

## C31 runtime evidence
- At uptime 15.404966 seconds, one C31 init-native marker recorded primary zygote running as PID 1059, secondary Zygote PID 1060, and netd PID 1044. The first main SIGABRT was PID 1059, directly matching the initial primary Zygote PID.
- pmsg contains 103 main SIGABRTs, 103 netd SIGABRTs, and 102 SIGSEGV events with truncated comm android.hardwar. No later init service/PID/reap/critical/fatal records exist in the retained evidence, so all main PIDs/restarts cannot be mapped to init's zygote service.
- 104 UltraFrameworkComponentFactoryImpl ClassNotFound records cover all 103 main SIGABRT PIDs, plus one record from secondary PID 1060. PID 1059 logged further initialization about 316 ms after ClassNotFound and SIGABRT about 603 ms after it. This is strong same-process timing correlation, not proven causation; no abort message/backtrace was retained.
- Candidate console saved through uptime 527.837 seconds contains no sysrq-trigger, init_fatal, or kernel panic record. Against C30's PID1 sysrq panic at about 32.922 seconds, this strongly supports but does not prove that no_fatal suppressed primary Zygote critical escalation.
- The expected no_fatal critical_gate/readback marker is absent; only one zygote_start marker was found. Runtime property value is unconfirmed. Strict classification is Result C: strong differential support, causal chain incomplete.
- No direct sys.boot_completed=1, service.bootanim.exit=1, system_server PID, SystemUI, SetupWizard, Launcher, or HyperOS second-screen evidence was found. BootAnimationShownTiming start time 39133ms does not establish what appeared on the physical screen.
- The experiment did not fix main SIGABRT. The next host task is to determine why crash_dump failed to exec or was killed and recover an abort message/backtrace, then inspect the same-PID UltraFramework class-init/fallback path. Do not add SELinux permissions based only on correlation.

## First-response capture
- Unified First-Response Standalone saved Candidate pstore first, then read-only raw metadata and misc, its own dmesg, and all accessible THYME_DIAG contents.
- The host copy contains 13 files; all source/copy sizes and SHA-256 values match and the issue list is empty. Raw metadata is 16 MiB and misc is 4 MiB; no journal replay occurred.
- Original pstore, raw metadata/misc, Standalone dmesg, and host transcripts remain local. Only a sanitized analysis report and status/history are published.
- Standalone diag_status contains a stale “C28” text label for metadata capture. Unique source mapping, capacity checks, raw copy, and hashes succeeded; correct the label in a future diagnostic tooling revision.

## Boundaries and next step
- Do not repeat C31. Any future Candidate requires a separate user-present confirmation before its formal boot.
- Never relock the bootloader or modify persist hardware data, modemst, EFS/NV, radio calibration, or device identity. Do not clear userdata/metadata or change boot-control without a specific need.
- Do not attribute main SIGABRT to UltraFramework, property AVCs, or netd without direct abort/backtrace evidence.
- First inspect the crash_dump/debuggerd execution and tombstone path. Decide on a new Candidate only after a concrete failure is identified.
- Docker assets are always excluded from project cleanup.

## Latest report
- reports/c31_diag_critical_20261001/C31_DIAG_RUNTIME_RESULT_20261001.md
- Current commit URL will be added after publication.