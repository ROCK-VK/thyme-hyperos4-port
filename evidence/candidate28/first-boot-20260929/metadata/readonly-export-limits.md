# C28 metadata read-only export status

- Export source was `metadata` ext4 mounted `ro,relatime,norecovery` (requested `ro,noload`).
- The exported directory contained 14 existing C25/C26/C27 files and no visible `C28_*` files.
- Journal replay was disabled, so this view cannot establish whether C28 marker/logger writes remained only in ext4 journal after the PID 1 panic. Absence is inconclusive.
- The metadata-only Standalone image did not create required top-level `dmesg_diag_boot.txt`; export returned nonzero for that missing file. The 20 files it exposed were size/SHA verified with zero mismatches.
- The image also exported `misc.raw` incidentally. It remains local and is excluded from public release; no BCB parsing or write was done in this task.
- Older C25/C26/C27 metadata contents were not republished in this C28 increment.
