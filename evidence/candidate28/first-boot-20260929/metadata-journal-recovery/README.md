# C28 metadata journal recovery: recovered init markers

This directory contains only the `C28_*` diagnostic files recovered from a host-side working copy of the device's metadata image.

## Provenance

- Standalone identified the metadata partition from its unique `PARTNAME=metadata` sysfs entry and checked its block-device identity and exact 16 MiB capacity before reading it.
- The complete device-side read and host copy had matching length and SHA-256. The raw metadata image remains local and is not published here.
- The host working copy was bit-for-bit checked against that read-only export before ext4 journal recovery. Journal replay was performed only on the host copy; the device partition was never replayed or written.
- The listed files were extracted from the recovered host copy. `MANIFEST.csv` records each extracted file's byte length and SHA-256.
- The incidental `misc.raw` and the full metadata image are excluded. No ROM or partition image is included.

## What these markers establish

- Init recorded `netd` as both `restarting` and `running`.
- Init recorded `zygote` as both `running` and `restarting`, and `zygote_secondary` as `running`.
- Init recorded `surfaceflinger`, `bootanim`, and the C28 watcher service as `running`; the C28 logcat service was recorded as `stopped`.
- The marker triggers are defined by `init.svc.*` property transitions in the C28 diagnostic rc. The watcher `running` marker is consistent with the `post-fs-data` action having started it.
- These marker files do not contain timestamps. Their presence proves the corresponding state transitions were recorded, but does not establish precise ordering or that the netd restart caused the Zygote restart.
- The C28 logcat status, Zygote event, and Zygote tail files are present but zero bytes. They do not establish that logcat data was captured. `system_server`, SystemUI, HOME, boot completion, and physical-display presentation remain unverified.

The standalone diagnostic kernel log is not part of this directory and must not be confused with C28 Android logs.
