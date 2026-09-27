# Candidate 21 public evidence copy

This directory contains the complete accessible C21 host-observation run and Standalone THYME_DIAG export from the local source run. Source files remain unchanged locally. Public copies replace the device serial `[REDACTED_DEVICE_ID]`: text occurrences use `[REDACTED_DEVICE_ID]`; the same-length binary replacement `REDACTED` is used in `oops.raw` to preserve offsets and file length. No files or directories from these two source runs were omitted.

`PUBLIC_EVIDENCE_MANIFEST.csv` records every copied file, local source size/SHA-256, published size/SHA-256, and identifier redaction count. The copied source `SHA256SUMS.txt`, `oops.raw.sha256`, and `FILE_MANIFEST.csv` retain their original source-side values; where they cover a redacted public file, use the published SHA-256 in `PUBLIC_EVIDENCE_MANIFEST.csv` as the integrity value for the public copy. The local originals still match their original checksums.

`oops.raw` is a historical 2026-06-17 record, not a C21 crash dump. Standalone `dmesg_diag_boot.txt` describes the diagnostic environment, not the C21 Android kernel. See the C21 report for interpretation and event attribution.
