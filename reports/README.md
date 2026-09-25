# Reports and boot evidence

Reports retain conclusions at the evidence level documented when they were written. Older reports are historical snapshots; the current project state and later execution records take precedence when results changed.

Some historical reports use emphatic phrases such as “100%” or “司法级”. These are original wording, not an independent certification; judge each claim by its listed validation and the linked primary evidence.

- `k40/` contains the three-way K40, Xiaomi 15 donor, and thyme comparison plus its review. It is a static package analysis, not a claim that every K40 change can be transplanted.
- `candidate13/` contains the Recovery/fs_mgr analysis and data-safety preparation report. The newer clean-data first-boot summary updates the earlier Recovery hypothesis.
- `boot-logs/` contains selected text console, decoded pmsg, and USB/ADB/Fastboot timelines attributed to specific Candidate runs. Standalone's own boot log, binary pmsg containers, and historical `oops.raw` are excluded where they could be confused with Candidate evidence.

The C13 clean-data `console-ramoops` ends around 3.75 seconds after first-stage mount, dynamic policy compilation, enforcing second-stage init, and APEX bootstrap. It does not establish later HAL, vold, `/data`, boot animation, or desktop status. It is not a complete system log.

Raw `misc`/BCB, partition backups, `persist`, radio/NV/EFS data, user data, complete images, and vendor binaries are not published.
