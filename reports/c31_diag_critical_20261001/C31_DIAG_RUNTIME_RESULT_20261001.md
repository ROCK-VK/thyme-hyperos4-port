# C31-DIAG Runtime Result and Causal Boundary

Updated: 2026-10-01 14:27 HKT

## Result

Under the experiment's strict evidence criteria, this is **Result C: the causal chain is not fully closed**. The differential result strongly supports the hypothesis that primary Zygote critical-fatal escalation explains C30's PID1 panic: C31-DIAG preserved Candidate console through uptime 527.84 seconds with no sysrq/PID1 panic record while pmsg still contains 103 main SIGABRT events. C30 had a PID1 sysrq panic at about 32.922 seconds.

The runtime value of init.svc_debug.no_fatal.zygote was not independently confirmed. The expected early-init critical_gate marker is absent from the saved pstore; only the zygote_start marker was found. No init child-reap, per-restart service PID/state, critical-count, or fatal-target records were retained. The Zygote SIGABRT cause remains unresolved.

## Controlled boot window

- The C31-DIAG observer was ARMED before the one authorized fastboot reboot.
- Preboot: thyme, slot A, unlocked, bootloader Fastboot. Slot A was unbootable=no, successful=no, retry=3; slot B was no/no/retry=7.
- The sole reboot command returned success at 2026-10-01 05:54:57.126 UTC.
- Fastboot was observed again at 06:03:56.250 UTC, about 539.124 seconds after the command. The user reported seeing only the static Xiaomi first screen and manually returning to Fastboot; no automatic Fastboot transition is inferred.
- ADB never became available. No HyperOS second screen, Setup Wizard, SystemUI, Launcher, or desktop was observed.
- The Candidate console reaches uptime 527.837 seconds. pmsg spans approximately 21:56:11.367–22:04:53.401 in the device log clock.
- After failure, Unified First-Response Standalone was RAM-booted. The complete diagnostic volume was copied to a new local directory: 13 files, all source/copy sizes and SHA-256 values matched, with no copy issues. Candidate pstore was captured before raw metadata and misc; Standalone dmesg was separately named.
- Final readback: slot A remains active, unbootable=no, successful=no, retry=2; slot B remains no/no/retry=7. The phone is in Bootloader Fastboot. No set_active, partition flash, erase, metadata write, or PixelOS restore occurred during this runtime/capture phase.

## Direct service/PID/signal evidence

A single C31 init-native marker at uptime 15.404966 seconds recorded primary zygote running with PID 1059, secondary Zygote PID 1060, and netd PID 1044. The first main SIGABRT is PID 1059, directly matching the primary zygote PID recorded by init.

pmsg contains 103 main SIGABRTs, 103 netd SIGABRTs, and 102 SIGSEGV events whose process name is truncated to android.hardwar. No later init state markers or child-reap/wait-status records were found, so later main PIDs and restart counts cannot all be directly mapped to init's zygote service.

Comparison:

- C30: five main SIGABRT events; the last was around uptime 32.879 seconds, followed by PID1 writing sysrq-trigger around 32.921975 seconds.
- C31-DIAG: 103 main SIGABRT events; no sysrq-trigger, init_fatal, kernel panic, or recovery record appears in the saved Candidate console through uptime 527.837 seconds.

This is strongly consistent with suppressing the primary Zygote critical-fatal path while leaving process crashes intact, but missing runtime gate readback and init reap/fatal records prevent a definitive causal claim.

## Gate and diagnostic-marker status

The only system-tree change was system/etc/init/hw/init.rc: set init.svc_debug.no_fatal.zygote=true during early-init, followed by an intended critical_gate kmsg marker; the file also defines a zygote_start marker and service-state markers. The saved console contains one zygote_start marker, proving at least one diagnostic action executed.

The captured console/pmsg contain no critical_gate or no_fatal readback marker, no later zygote/secondary/netd state markers, and no init critical/fatal or child-reap lines. The reason for the missing records is unknown. A property present in the image is not equivalent to a confirmed runtime value.

## main SIGABRT and UltraFramework correlation

There are 104 Failed to create UltraFrameworkComponentFactoryImpl records. Their timestamped log-record PIDs include all 103 main SIGABRT PIDs; the extra record is from initial secondary zygote PID 1060.

For the first primary PID:

1. PID 1059 logs ClassNotFoundException for android.os.ufw.UltraFrameworkComponentFactoryImpl at 21:56:21.627.
2. The same PID logs ThirdAppOptImpl has been initialized at 21:56:21.943.
3. The same PID receives SIGABRT at 21:56:22.230, about 603 ms after the ClassNotFound record.

This is a tight same-process correlation, not proof of cause. The process continues logging initialization after the exception, and no abort message/backtrace is available. pmsg says the crash_dump helper failed to exec or was killed. Earlier C30/K40 bytecode review found a fallback path, so the missing class is not declared the root cause.

## Framework/UI boundary and next step

pmsg contains BootAnimationShownTiming start time 39133ms, but this is not proof that the user saw an animation. There is no direct sys.boot_completed=1 or service.bootanim.exit=1 record, no confirmed system_server PID, and no SystemUI/SetupWizard/Launcher evidence. Keystore2 continues waiting for sys.boot_completed.

The highest-value next host investigation is why crash_dump could not exec or was killed, so the next useful experiment can retain the main abort message/backtrace. In parallel, inspect the same-PID UltraFramework class-init/fallback path. Do not add SELinux permissions based only on temporal correlation, repeat C31, or build a repair Candidate without a specific cause.

## Evidence handling

Original pstore, metadata, misc, Standalone dmesg, and host transcripts remain local. The Standalone command line includes device-specific identifiers; no raw diagnostic or partition backup is included in this public report.