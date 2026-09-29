# C26 Standalone and host observations — 2026-09-29

This folder contains the C26 first-boot host timeline and the files recovered from the `THYME_DIAG` volume during the RAM-only Standalone session `run_20260929_133135`. The host observer run was `run_20260929_131953`.

The ten published files under `standalone/THYME_DIAG/` are byte-identical to their local source except for the explicitly redacted `diag_status.log`, `C25_METADATA_COPY_VERIFY.txt`, and C26 logcat. Host records are sanitized derivatives where local paths or the device USB serial occurred. Each published file's byte count, SHA-256, source path, and transformation are listed in `PUBLIC_EVIDENCE_MANIFEST.csv`.

Excluded from publication: the complete 4 MiB `misc.raw` backup, its SHA-256 sidecar, the source `FILE_MANIFEST.csv` and `SHA256SUMS.txt` because they disclose the misc digest, and Windows `System Volume Information` files. The misc SHA line and the device CPUID value were redacted from text derivatives. No passwords, private keys, or reusable access tokens were found in the selected text files.

The THYME_DIAG volume had no `console-ramoops`, `pmsg-ramoops`, `oops.raw`, or `dmesg_diag_boot.txt`. The C26 Android userspace evidence is the persistent logcat, zygote event/tail files, C25 sampler output and init trigger marker. Empty host logcat capture files are retained to document that ADB did not become available.