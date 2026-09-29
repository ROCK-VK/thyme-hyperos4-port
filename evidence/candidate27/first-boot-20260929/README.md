# C27 first boot and Recovery evidence — 2026-09-29

This archive corresponds to one C27 fastboot reboot attempt. The user observed Xiaomi logo → black screen → logo → PixelOS Recovery. Host ADB appeared as unauthorized; no shell/logcat was available.

The C27 post-fs-data marker is present. The C27 logger status and Zygote event/tail files are empty, so the netd→Zygote change and system_server progress remain unverified.

The pstore console is a Recovery boot, not the preceding C27 Android boot. Its boot-recovery BCB write occurs after Recovery has started and does not establish the initial Recovery cause. No pmsg was present.

The Standalone diag_status and dmesg files are from the Standalone diagnostic environment, not C27. The old oops.raw was identified as unrelated 2024 vendor-kernel content and is not included. misc.raw is a post-Recovery partition backup and is intentionally excluded.

Text logs are public redacted copies. Device serial, CPUID, host name and local paths were replaced; unmodified local originals remain in the project evidence directory. MANIFEST.csv records local-source and published-copy sizes and SHA-256 values. C27 metadata text files and empty outputs are byte-identical to the read-only export.

No ROM, firmware, partition image, misc backup, or credential is included.
