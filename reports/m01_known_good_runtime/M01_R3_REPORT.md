# M01-R3 Known-Good clean-data reproduction: runtime report

Date: 2026-10-05 (HKT)

Status: Android framework/UI boot verified; read-only runtime capture completed; no second reboot was issued.

## Result

After clearing only `userdata` and `metadata`, the existing Known-Good madrid OS4.0.15 → thyme A-slot stack booted into Android 17. No OS image or firmware was reflashed for R3. The user confirmed a successful boot and opened USB debugging in Settings. Host evidence recorded `sys.boot_completed=1`; ADB became `device` at T+238 seconds and remained online through the 900-second observation window. This meets the Android framework/UI boot threshold (Level 2 or higher). No screen recording was made, so SetupWizard, lockscreen, or desktop was not independently distinguished.

The clean-data condition is strongly associated with the progress from R1/R2 (no ADB) to R3 (Android framework and Settings access). Since userdata and metadata were erased together, this does not isolate which partition or stored state caused the earlier failure.

## Controlled changes and observation

- R3 retained the existing Known-Good `boot_a`, `vendor_boot_a`, `dtbo_a`, `super`, `vbmeta_a`, and `vbmeta_system_a` stack. It did not reflash these images.
- Bootloader Fastboot ran `erase userdata` and `erase metadata`; both returned exit code 0. No format or `fastboot -w` was used. FRP, firmware, B slot, and protected identity/calibration partitions were untouched.
- One authorized `fastboot reboot` was issued. Fastboot disappeared at about T+21 seconds, Android USB enumeration appeared around T+96 seconds, ADB was briefly unauthorized at T+237 seconds, then became `device` after USB debugging was enabled. At T+899 seconds ADB was still `device` and Fastboot remained absent.

## Runtime findings

- `ro.product.device=thyme`; Android 17 / SDK 37; `sys.boot_completed=1`.
- `/proc/version` confirms the Known-Good custom `4.19.325-cxk` kernel executed. Empty pstore in R1/R2 therefore cannot be used to infer that their kernel did not run.
- SELinux reported Permissive. Shell access to `/proc/cmdline` and `/proc/<netd-pid>/maps` was denied by the production `user` build; no adb root was attempted. The exact netd shared-library map remains unverified.
- `/data` is f2fs, `/metadata` ext4; bpffs and cgroup2 are mounted.
- `com.android.tethering` is an Active APEX and is mounted under `/apex`; `INetd` and the Tethering connector services are present. `netd` is running and reports `libnetd_updatable_init success`.
- Tethering reports BPF enabled and its primary IPv4/IPv6 and statistics maps as `OK`. No upstream or forwarding session was active, so real hotspot/tethering traffic was not tested.
- A property snapshot showed `traced` restarting and `sys.init.updatable_crashing=1`. This is an ancillary post-boot issue for review, not a boot blocker in this run.

## Evidence boundaries and next step

The raw ADB dumps, logcat, dmesg, host timeline, and other device-specific captures remain in the private project workspace. This public report contains only a sanitized summary; no ROM, image, proprietary firmware, raw device log, or device identifier is included.

The Tethering APEX being inactive is contradicted by the active/mounted APEX and service evidence. The exact netd mappings and an actual tethering data path remain unverified. R3 is complete; stop device experiments here and review this Known-Good runtime baseline before planning the official madrid OS4.0.19 port.
