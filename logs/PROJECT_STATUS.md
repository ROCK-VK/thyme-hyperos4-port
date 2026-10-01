# THYME-OS4 Project Status

Updated: 2026-10-01 13:28 HKT

## Goal and current milestone
Port Xiaomi 15 (dada) HyperOS 4 / Android 17 to Xiaomi 10S (thyme, Snapdragon 870). The current milestone is a diagnostic experiment for the suspected primary Zygote critical escalation preceding C30's PID1 sysrq panic.

## Current candidate and device
- C31-DIAG is flashed to slot A but has not been booted. It is a diagnostic build, not a startup fix.
- Last read-only Fastboot check: one device, product=thyme, slot A, unlocked, non-userspace Fastboot. Slot A: unbootable=no, successful=no, retry=3. Slot B: no/no/retry=7.
- Only super and vbmeta_system_a were flashed. No reboot, set_active, erase/format, userdata/metadata write, or other partition write was issued. The device remains in Bootloader Fastboot.
- C31-DIAG changes only system/etc/init/hw/init.rc: set init.svc_debug.no_fatal.zygote=true during early-init; emit low-frequency init-native /dev/kmsg markers for the gate, initial Zygote/secondary/netd state and PIDs, subsequent service state changes, sys.boot_completed, and sys.powerctl.
- All C30 service definitions, critical and onrestart behavior, SELinux/property contexts, diagnostics, framework/ART, graphics, kernel, fstab, encryption, and other partitions are retained. No SELinux rule was added.
- Static build gates and restricted flashing passed. Runtime effect of no_fatal and service-to-PID-to-signal mapping remain unverified. Wait for explicit user instruction “开始启动” before booting.

## C30 evidence boundary
- C30 pmsg recorded five main SIGABRT events at estimated uptimes 16.095, 18.014, 22.855, 27.842, and 32.879 seconds. PID1 wrote sysrq-trigger around 32.921975 seconds, about 43 ms after the last SIGABRT.
- Primary service is named zygote and remains configured critical with a 10-minute window. This is a diagnostic hypothesis, not a proven causal chain: the main PIDs are not mapped to init services, and no init critical-fatal line or abort backtrace was preserved.
- C30 netd/Linux 4.19 BPF failure is an independent known issue; the direct netd-to-Zygote restart callbacks were removed in C27/C30. Seven vendor-property AVCs lack exact keys/PIDs/consumers; no broad SELinux grant is justified.
- The UltraFrameworkComponentFactoryImpl loading path has a fallback and is not established as the fatal cause.

## Other evaluated tracks
- The third-party Milo packages remain static references only; old package mapping/write scope is not reliable, and their EXE/BAT/APK were not run.
- DSU feasibility was assessed statically only; no device-side DSU was attempted.

## Storage and safety
- C/D/E free space at 13:28 HKT: approximately 90.77/191.84/162.43 GiB; all above the 50 GiB gate. No cleanup was performed this turn.
- Bootloader stays unlocked. Do not relock or modify persist hardware data, modemst, EFS/NV, radio calibration, or device identity.
- Docker assets are always excluded from cleanup.

## Next step
1. Keep the phone in Bootloader Fastboot until the user explicitly says “开始启动”.
2. Before boot, arm the correctly labeled observer. If boot fails, the first Unified Standalone response must capture Candidate pstore first, then all THYME_DIAG files, raw metadata, misc, and its own dmesg with hashes.
3. Judge the hypothesis from THYME_C31DIAG markers, init reap/service PID/signal/restart records, critical/fatal events, and sysrq/panic timeline. Suppressing a PID1 panic would support only the escalation layer, not resolve Zygote's own SIGABRT.

## Latest report
- reports/c31_diag_critical_20261001/C31_DIAG_BUILD_FLASH_AND_RUNTIME_BOUNDARY.md
