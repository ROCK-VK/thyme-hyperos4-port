# THYME-OS4 Project Status

Updated: 2026-10-01 23:40 HKT

## Goal and current milestone
Port Xiaomi 15 (dada) HyperOS 4 / Android 17 to Xiaomi 10S (thyme, Snapdragon 870). The current blocker is the repeated primary Zygote SIGABRT and failure of its crash-dump helper; no normal HyperOS boot has been achieved.

## Candidate and live device state
- C32-DIAG is flashed to slot A and has completed exactly one controlled boot attempt. It is not to be booted again.
- Live read-only Fastboot query: one device, `product=thyme`, `current-slot=a`, `unlocked=yes`, `is-userspace=no`. A: `unbootable=no`, `successful=no`, `retry=1`. B: `unbootable=no`, `successful=no`, `retry=7`.
- User manually returned the device from Standalone UMS to Bootloader Fastboot. A fresh full read-only readback is in `evidence/candidate32/standalone/firstboot/run_20261001_224407/observer/fastboot_state_after_standalone_user_return.redacted.txt`. No `set_active`, further reboot, flash, erase, userdata/metadata operation, or PixelOS restore was performed after the C32 attempt.
- Preserve the remaining A-slot retry budget; do not repeat C32 or change slot metadata without a separately scoped decision.

## C32 first-boot evidence
- The observer was ARMED before one `fastboot reboot` (2026-10-01 14:29:35.333 UTC, exit 0). The host saw Bootloader Fastboot again at 14:38:01.484 UTC, about 506 seconds later. The user reported seeing only the Xiaomi first screen with “Powered by Android”; the report timestamp is not synchronized closely enough to attribute that exact screen to the host reconnect instant. ADB never came online and both observer logcat outputs are 0 bytes.
- At uptime 15.541 seconds, the C31DIAG marker identified primary Zygote PID 1068, secondary PID 1069, and netd PID 1059. Pmsg contains 98 `main` SIGABRT PIDs; one is the canary PID 1453. The other 97 each match one `crash_dump helper failed to exec, or was killed` PID record.
- The one-shot native canary produced a tombstone with fixed abort message `THYME_C32_CANARY_ABORT` and a three-frame backtrace. This shows an init-launched native abort could be captured in this run; the tombstone has no SELinux label, so the canary's runtime domain is not proven. It does not establish why real Zygote helper requests fail.
- `UltraFrameworkComponentFactoryImpl` ClassNotFoundException precedes primary PID 1068's SIGABRT, but no abort message/backtrace was retained for that process; causation remains unproven. There is no evidence of `system_server`, SystemUI, SetupWizard, Launcher, or `sys.boot_completed`.
- Unified First-Response Standalone captured pstore first, then raw metadata/misc, Standalone dmesg, and the complete THYME_DIAG volume. All 13 volume entries passed size/SHA-256 comparison with zero copy errors. Local originals remain unchanged.

## Diagnostic interpretation and next step
- The evidence supports a process-context difference between the canary and real Zygote crash-dump paths. It does not identify SELinux as the cause. Do not add broad or speculative permissions and do not build a repair Candidate from this evidence alone.
- Next, do a host-side, targeted comparison of the real Zygote crash handler/helper execution context against the successful canary, focusing on the helper handshake, process credentials, namespaces, descriptors, and signal handler. No C33 build is justified yet.

## Safety and publication
- No bootloader relock, hardware persist/radio/NV/calibration/identity write, userdata/metadata clear, or Docker operation.
- The local raw originals are retained. The public C32 bundle includes exact PMSG (scanned for the known serial/CPUID and common credential markers) plus explicitly redacted text views and the host timeline. Raw `metadata.raw` and `misc.raw` are excluded; their local source sizes/hashes are enumerated in the public provenance manifest.
- Runtime report: `reports/c32_diag_zygote_domain_canary_20261001/C32_FIRST_BOOT_RESULT_20261001.md`. Public evidence: `evidence/candidate32/standalone/firstboot/run_20261001_224407/`.
