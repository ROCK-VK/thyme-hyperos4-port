# C13–C23 启动诊断证据

本目录保存经用户明确授权公开的 C13–C23 Standalone 诊断卷导出和对应主机观察记录。C13–C20 按此前发布记录保留其原始字节；C21 全量可访问文件均已复制到公开副本，并按既有发布记录对设备序列号脱敏。C22 与 C23 的主机观察和 Standalone 文件按用户授权以原始字节发布，逐文件来源/发布大小及 SHA-256 见累积清单 [RAW_EVIDENCE_MANIFEST.csv](RAW_EVIDENCE_MANIFEST.csv)。

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
- candidate19/standalone 与 host-observations：C19 RGBX EGL 实验的完整诊断卷导出和主机观察记录。
- candidate20/standalone 与 host-observations：C20 ANGLE 路由诊断实验的完整诊断卷导出和主机观察记录；包含 console、pmsg、oops、Standalone dmesg、diag_status、设备生成文件、导出清单和启动观察时间线。
- candidate21/standalone 与 host-observations：C21 全部可访问 Standalone 导出文件及主机观察目录，共 19 个源文件；包括 console、pmsg、历史 oops.raw、Standalone dmesg、diag_status、导出元数据、空 logcat 文件及系统生成文件。公开副本序列号脱敏，逐文件源/公开哈希见该 Candidate 的发布清单。
- candidate22/standalone 与 host-observations：C22 的 8 个诊断卷文件和 11 个主机观察文件，共 19 项。完整保留本轮实际存在的文件及目录结构；源与公开副本逐文件大小/SHA-256 一致。Standalone dmesg 属于诊断环境，`oops.raw` 为历史/诊断残留，不能作为 C22 Android 启动日志。
- candidate23/standalone 与 host-observations：包含 2026-09-27 首次 Recovery 现场，以及 2026-09-28 retest 的 8 个诊断卷文件和 10 个主机观察文件。retest console 证明正常 First/Second Stage 与 /data 初始化，pmsg 记录 BootAnimationShownTiming；用户仍只看到静态小米 Logo，桌面未确认。首次尝试的 Recovery 原因仍未知。

每个 Standalone 导出保留当时实际存在的原始 console-ramoops、pmsg-ramoops、oops.raw、Standalone dmesg、diag_status、源端校验文件、主机导出时间线和清单。缺失的文件不会补造。

## 完整性和排除项

C13–C20 的既有公开内容保持此前发布形态，可能包含设备标识、内核命令行和主机路径。C21 公开副本对设备序列号作了可追溯替换；C22/C23 原始诊断文件按用户授权逐字节发布。各自来源与公开副本 SHA-256 见累积清单。

RAW_EVIDENCE_EXCLUSIONS.csv 记录同步器因识别凭据特征、分区/固件镜像名称或单文件超过 100 MiB 而排除的文件。已发布诊断文件经过私钥 PEM、常见访问令牌、Bearer token 和密码赋值模式筛查；如发现真正凭据则从公开副本排除并记录。C21 序列号替换数量及各文件哈希见其专用清单。

完整 ROM、固件包、boot/system/super 镜像、userdata/metadata 分区镜像以及 misc/校准/身份分区备份不在本目录。
