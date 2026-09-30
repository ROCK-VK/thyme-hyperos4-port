# C30 首次启动与 Standalone 取证

本目录按用户授权保存 C30 本轮主机观察和启动诊断证据。pstore console/pmsg、Standalone 自身日志及观察器源文件均保留原始字节；各文件 SHA-256 在 PUBLIC_EVIDENCE_MANIFEST.csv 中核对。diag_status.log 对设备 serial/cpuid、metadata/misc 原始分区哈希和本机构建路径做了脱敏，未经修改的本地原件仍保存在项目工作区。

C30 启动前观察器已 ARMED，唯一 fastboot reboot 于 2026-09-30 03:54:45.3978599 UTC 返回 exit 0。用户报告屏幕始终是静止小米第一屏。主机约 10 分 17 秒后重新看到 Fastboot；其后一次 Unified First-Response Standalone RAM boot 导出 THYME_DIAG。ADB 未上线。

关键原始证据：
- standalone/pstore/console-ramoops-0：C30 kernel console；约 32.922 秒记录 PID 1 init 通过 write_sysrq_trigger 主动触发 panic。
- standalone/pstore/pmsg-ramoops-0：C30 pmsg；记录 /data/fscrypt/keystore2 推进以及重复 netd SIGABRT。
- standalone/standalone_dmesg.txt：Standalone 诊断内核日志，不是 C30 Candidate 内核日志。
- standalone/diag_status.log：Standalone 取证过程状态，已按上文说明脱敏。
- host/：启动前 Fastboot 状态、观察器、USB/ADB/Fastboot 时间线和空的 host logcat 文件。
- standalone/analysis/pmsg_ascii_strings.txt：从二进制 pmsg 提取的可打印 ASCII 字符串视图，可能丢失 framing/字段；仅供搜索，不替代原始 pmsg。

完整来源导出包含 13 个文件、2 个目录，主机复制时每个源/副本的大小与 SHA-256 对照通过，0 复制失败。本公开目录不包含 metadata.raw、misc.raw、它们的 checksum sidecar，也不包含任何 ROM/分区镜像。原始 FILE_MANIFEST/SHA256SUMS 因包含这些本地分区副本的哈希而不公开，由 PUBLIC_EVIDENCE_MANIFEST.csv 取代；Windows 自动生成的 System Volume Information 文件也不属于设备诊断证据。两个 raw 分区副本只保存在本机。公开 manifest 对未发布文件列出名称、大小和原因，不披露分区哈希。

详细结论见 [C30 首次启动与取证报告](../../../../reports/C30_FIRST_BOOT_AND_PSTORE_REPORT.md)。