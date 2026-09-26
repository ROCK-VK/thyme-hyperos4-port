# C13–C18 原始启动诊断证据

本目录保存经用户明确授权公开的 C13–C18 Standalone 原始诊断卷导出和对应主机观察记录。源文件按原始字节复制；每个公开文件的大小与 SHA-256 见 [RAW_EVIDENCE_MANIFEST.csv](RAW_EVIDENCE_MANIFEST.csv)。每次同步均检查公开复制件与本地来源一致。

## 目录

- candidate13/standalone：三个已保存的 C13 Standalone 导出。
- candidate13/host-observations：C13 启动观察记录。run_20260926_001542 来源于 C13 项目观察目录，但该旧记录没有 Candidate 元数据，因此明确标为 unlabeled。
- candidate14/standalone 和 host-observations：C14 取证与启动观察。
- candidate15/standalone 和 host-observations：C15 取证与启动观察。
- candidate16/standalone 和 host-observations：C16 取证与启动观察。
- candidate17/standalone：C17 首次取证和复验取证。
- candidate17/host-observations：C17 复验观察。C17 首次启动当时没有保存独立 host observer 目录。
- candidate18/standalone：C18 两次因 A 槽 unbootable 状态被拒绝的 RAM 启动时间线，以及恢复 A 槽状态后成功启动的完整 THYME_DIAG 卷导出。
- candidate18/host-observations：C18 首次启动 USB/ADB/Fastboot 观察时间线。

每个 Standalone 导出保留当时实际存在的原始 console-ramoops、pmsg-ramoops、oops.raw、Standalone dmesg、diag_status、源端校验文件、主机导出时间线和清单。缺失的文件不会补造。

## 完整性和排除项

原始日志包含诊断所需的未脱敏设备标识、内核命令行、工具版本和主机路径；它们按原样公开，以保留独立技术审核所需的上下文。文件内容没有被改写或脱敏。

RAW_EVIDENCE_EXCLUSIONS.csv 记录同步器因识别凭据特征、分区/固件镜像名称或单文件超过 100 MiB 而排除的文件。C13–C18 选定诊断文件经过私钥 PEM、常见访问令牌、Bearer token 和密码赋值模式扫描；同步结果及任何排除项以清单为准。

完整 ROM、固件包、boot/system/super 镜像、userdata/metadata 分区镜像以及 misc/校准/身份分区备份不在本目录。
