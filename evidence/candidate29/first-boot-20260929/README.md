# C29 首次启动与 pstore 归属证据

此目录保存 Candidate 29 首次启动观察及后续 Standalone pstore 采集的可公开证据。原始本地导出保持不变；公开文本中的设备序列号和本机/构建路径已脱敏。`PUBLIC_EVIDENCE_MANIFEST.csv` 为每份文件记录本地来源 SHA-256、公开副本 SHA-256 和处理说明。

## C29 直接可证实的状态

- C29 正常启动命令仅执行一次，Fastboot 返回成功；主机观察到 Fastboot 后消失，ADB 未上线，用户现场持续看到静态 Xiaomi 第一屏。
- 从 metadata 主机副本恢复出的 init markers 记录 primary/secondary zygote 与 netd 的运行状态；primary zygote 和 netd 也都出现 restarting 状态。markers 无可靠时间顺序。
- C29 event log 与 logcat status 文件为空。已公开 helper 源码的动态文件名与 C29 文件相符，支持 logger/watcher 执行到输出文件创建阶段；首条写入为何未留存仍未知。没有 system_server PID、fatal backtrace 或 C29 Android pstore 记录。因此当前仍不能判定 Zygote restart 的原因、system_server 是否成功 fork，或静态第一屏的具体阻塞。

## pstore 归属

本次专门 pstore 采集成功，只得到一个 `console-ramoops-0`，没有 pmsg。该 console 包含 Standalone 专属内核标识和日志，属于前一轮 Standalone 诊断会话，不是 C29 Android 启动证据。`dmesg_standalone` 同样是 Standalone 自身日志。不得把它们引用为 C29 kernel log。

## 目录

- `metadata-journal-recovery/`：只含 C29 marker、空 event 和 logcat status 文件；这些文件由已校验 metadata 的主机工作副本 journal recovery 提取。
- `host/`：完整观察器和两次 Standalone 导出时间线的脱敏文本副本。
- `standalone/`：第二次 Standalone 全量取证中与 pstore 归属判断相关的日志副本。
- `PUBLIC_EVIDENCE_MANIFEST.csv`：来源与公开文件完整性清单。

完整 THYME_DIAG 导出在本地共 40 个文件，源/副本字节数及 SHA-256 对照通过，0 个复制错误。公开副本不包括 `metadata.raw`、`misc.raw`、其原始校验 sidecar、Windows `System Volume Information` 或 ROM/分区镜像。C25–C28 carry-forward 历史证据已按各自 Candidate 发布，因此这里不重复上传。

详细分析见 [C29 首启与 pstore 归属报告](../../../reports/C29_FIRST_BOOT_AND_PSTORE_CLASSIFICATION_REPORT.md)。