# C32-DIAG first boot evidence (2026-10-01)

This bundle records one C32-DIAG boot and the following Unified First-Response Standalone capture. The phone was observed in Bootloader Fastboot before/after the controlled boot; an additional live post-Standalone read-only state capture is included under `observer/fastboot_state_after_standalone_user_return.redacted.txt`. No repeat boot, slot change, flash, erase, or PixelOS restore was performed after capture.

## Evidence and integrity

- `THYME_DIAG/pstore/pmsg-ramoops-0` is the exact original PMSG byte stream. Its SHA-256 is recorded in `PUBLIC_EVIDENCE_MANIFEST.csv`. The source PMSG was scanned for the known device serial, CPUID, and common credential markers; none were found.
- `console-ramoops-0.redacted.txt`, `standalone_dmesg.redacted.txt`, `diag_status.redacted.log`, and host observation files are UTF-8 text derivatives. They are not byte-identical to local originals. Device serial/CPUID, full boot command-line identity/panel details, and private host paths were redacted.
- `standalone_dmesg` is the Standalone diagnostic kernel log, not C32 Android's kernel log.
- `logcat_all_monotonic.txt` and `logcat_client_stderr.txt` are present as zero-byte files; ADB never became available.
- `PUBLIC_EVIDENCE_MANIFEST.csv` inventories all 13 source THYME_DIAG entries plus the host capture. It records source sizes/hashes, whether a file was published, and published sizes/hashes.
- `PUBLIC_SHA256SUMS.txt` verifies the public files. Local originals remain unmodified.

## Exclusions

`metadata.raw` and `misc.raw` are raw partition images and are not published; their exact source sizes and SHA-256 remain listed in the manifest. Windows `System Volume Information` files are also excluded. The original source manifests are replaced by the public manifest. No ROM, firmware, partition image, user-data image, private key, or reusable access token is included.
