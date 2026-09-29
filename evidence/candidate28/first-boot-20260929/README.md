# Candidate 28 首次启动证据（2026-09-29）

本目录收录 C28 单次启动的 pstore、Standalone 导出状态和主机 USB/ADB/Fastboot 观察副本。本机完整、未经修改的导出仍保存在项目目录中。

- `pstore/console-ramoops-0.redacted.txt`：设备身份和主机/构建路径已脱敏。
- `pstore/pmsg-ramoops-0`：原始 pmsg 字节，发布前未发现设备序列号/CPUID；旁边 searchable 文本视图有损，不能代替原始文件。
- `standalone/dmesg_diag_boot.txt.redacted.txt`：Standalone 自身启动日志，不是 C28 Android kernel log。
- `standalone/oops.raw.redacted.bin`：同长度脱敏副本；头部指向 2024 long-press 历史记录，不属于 C28。
- `host/`：观察器副本，设备序列号和本机路径已脱敏。
- `metadata/readonly-export-limits.md`：metadata 只读且禁用 journal replay 的导出局限；没有复发布旧 C25/C26/C27 logcat，也没有发布 `misc.raw`。
- `MANIFEST.csv`：本地来源与公开副本的大小/SHA-256 对照。

结论见 [`C28 首启与 PID 1 panic 报告`](../../../reports/C28_FIRST_BOOT_PID1_FATAL_PANIC_REPORT.md)。
