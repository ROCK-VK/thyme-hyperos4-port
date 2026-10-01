# THYME-OS4 Project Status

Updated: 2026-10-01 18:23 HKT

## Goal and current milestone
Port Xiaomi 15 (dada) HyperOS 4 / Android 17 to Xiaomi 10S (thyme, Snapdragon 870). Current focus: capture the primary Zygote SIGABRT first scene and improve the crash_dump evidence path. No formal startup fix has been identified.

## Candidate and device
- C31-DIAG is the last known flashed Candidate on slot A. It was booted once but did not reach the HyperOS second screen or desktop; ADB never came online.
- After evidence capture, the user reported manually returning to Bootloader Fastboot. The phone was not queried in this offline analysis turn.
- Last read-only slot state: A unbootable=no/successful=no/retry=2; B no/no/retry=7.
- This turn did not build, flash, or boot C32, change slot state, erase data, write metadata, or restore PixelOS.

## C31 runtime evidence
- The init marker at uptime 15.404966 seconds recorded primary zygote PID 1059, secondary PID 1060, and netd PID 1044. The first main SIGABRT was PID 1059, matching the primary zygote PID.
- pmsg contains 103 main SIGABRTs from distinct PIDs. Missing init reap/service PID lifecycle records mean these cannot be equated with 103 init service restarts.
- Every main SIGABRT has only the generic crash_dump helper handshake EOF message; there is no abort message/backtrace, exec errno, or child exit/signal record.
- crash_dump64, its static dependency paths, tombstoned configuration, and relevant merged SELinux transition/access rules are present. No crash_dump/tombstoned AVC was found in the targeted logs. A netd crash produced a native tombstone in the same C31 runtime, so the dump path is not proven globally unavailable. The Zygote-specific helper failure remains unknown.
- The first UltraFrameworkComponentFactoryImpl ClassNotFound in PID 1059 precedes its SIGABRT by about 603 ms; the process logs more initialization in between. No direct causal trace exists.
- C31 console through uptime 527.837 seconds has no PID1 sysrq/panic, unlike C30's panic around uptime 32.922 seconds. This strongly supports, but does not directly prove, no_fatal suppressing critical escalation. No runtime property or critical-branch readback was captured.

## Current decision and next step
- Strict result: Result C. Zygote SIGABRT is confirmed; abort reason is unknown. The retained evidence demonstrates a crash-dump handshake/evidence gap but does not identify a safe SELinux, linker, or service fix.
- No broad permissions or unrelated changes are justified. No C32 was built this turn.
- Proposed next diagnostic experiment: one noncritical, one-shot native crash-dump canary, started by init only after tombstoned is running, with a fixed abort message and independent init PID/start/stop markers. Before implementation, statically validate the explicit zygote seclabel transition, executable file type, SELinux, and one-shot startup ordering. It would distinguish a general zygote-domain dump-path issue from real Zygote runtime-context behavior, but would not reproduce ART, seccomp, namespace, or Zygote signal-handler state.
- A readable no_fatal property value alone would not prove that init's critical-fatal branch consumed it; any follow-up must keep those claims distinct.

## Evidence and safety
- Local full C31 capture: work/reports/candidate31_diag_20261001/standalone/run_20261001_140648/. Raw pstore, metadata/misc, Standalone dmesg, and host records remain local.
- This publication contains only a sanitized analysis report and project status/history. No ROM, image, raw backup, or device identity data is published.
- Docker assets remain excluded from project cleanup.