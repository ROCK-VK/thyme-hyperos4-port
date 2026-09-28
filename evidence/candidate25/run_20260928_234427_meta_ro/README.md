# C25 首屏诊断证据（2026-09-28）

本目录包含 C25 首启的主机观察文件，以及 Standalone run3 对 `/metadata/thyme_os4_diag` 的只读导出。公开前的 redacted 副本不覆盖本机原始证据；逐文件源/公开大小及 SHA-256 见 `PUBLIC_EVIDENCE_MANIFEST.csv`。

- 唯一识别的 THYME_DIAG 卷已在本机完整备份：8 个文件、4,272,050 bytes、8/8 大小和 SHA-256 一致；卷动态盘符 G: 仅为本次主机枚举结果。
- C25 metadata 导出包括 init 触发标记、持久启动采样日志和只读拷贝校验记录。采样持续看到 zygote/zygote_secondary restarting，system_server PID 不存在；采样没有 COMPLETE 标记，停止原因未确定。
- 本次卷中没有 console-ramoops、pmsg-ramoops 或 oops.raw；Standalone dmesg 也不存在。因此没有伪造缺失的内核/用户空间日志。
- 本目录不含 `misc.raw`、其散列文件、原始设备分区备份或镜像。`diag_status.log` 公开为 redacted 版本，设备序列号、CPUID、主机名、私人路径与 misc 散列已去标识；原始文件保留在本机。
- 主机原始 logcat 文件实际为 0 bytes；ADB 在 C25 启动观察期间未上线。