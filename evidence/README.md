# C13–C25 启动诊断证据

本目录保存经用户明确授权公开的 C13–C25 Standalone 诊断卷导出和对应主机观察记录。C13–C20 按此前发布记录保留其原始字节；C21 全量可访问文件均已复制到公开副本，并按既有发布记录对设备序列号脱敏。C22–C24 的主机观察和 Standalone 文件按此前授权以原始字节发布。C25 持久采样和主机观察按 Candidate/时间独立归档；其中设备序列号、CPUID、主机名与私人路径已在公开副本去标识，原始 misc 与其散列不公开。逐文件来源/发布大小及 SHA-256 见累积清单 [RAW_EVIDENCE_MANIFEST.csv](RAW_EVIDENCE_MANIFEST.csv) 及 C25 本轮清单。

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
- candidate23/standalone 与 host-observations：包含 2026-09-27 首次 Recovery 现场、2026-09-28 两次正常启动复验及其主机观察记录。`long_boot_retest/` 中保存 2026-09-28 15:47 启动后的 10 项主机观察文件和 12 项 Standalone/导出元数据文件；其中 THYME_DIAG 原始卷的 8 个文件共 20,433,856 bytes，全部复制校验通过。用户全程看到静态小米 Logo；主机观察约 11m52 后重新发现 Fastboot；pmsg 约 11m38，记录 `/data`/fscrypt 与 BootAnimation shown-timing，但没有 boot-completed 或桌面直接证据。SHA-256 和来源见累积 manifest 及该轮 `PUBLIC_EVIDENCE_MANIFEST.csv`。旧 `oops.raw` 与更早取证完全相同，不归属本轮 C23。
- candidate24/framework_display/20260928_194944/：C24 启动前后主机观察，以及 THYME_DIAG 全量可访问文件的原始副本。含 29 个源文件（包括两个空 logcat 文件、Standalone 元数据及 Windows volume 文件），源/公开副本逐文件大小和 SHA-256 一致；清单见该目录的 `PUBLIC_EVIDENCE_MANIFEST.csv`。本轮 `oops.raw` 与 C13–C23 历史副本一致，不归属 C24；Standalone dmesg 是诊断环境日志。用户约 16 分 43 秒始终看到第一屏小米 Logo + `powered by Android`，未见带三点的 HyperOS 第二屏；ADB 未上线，pmsg 没有 `C24BootDiag` 样本，Framework 与 display present 状态仍未知。C24 首次启动报告位于 `../reports/candidate24/C24_FIRST_BOOT_EVIDENCE_20260928.md`。
- candidate25/run_20260928_234427_meta_ro/：C25 首屏观察与 Standalone run3 导出的完整可访问诊断文件。主机观察原件和 C25 metadata 诊断日志的公开副本已去标识，逐文件来源/公开哈希见 `PUBLIC_EVIDENCE_MANIFEST.csv`。本机 THYME_DIAG 全量副本含 8 个文件、4,272,050 bytes，逐文件校验 8/8；公开副本不含 `misc.raw`、其散列或原始设备分区备份。卷内没有 console-ramoops、pmsg-ramoops、oops.raw，也没有 Standalone dmesg；缺失项未补造。C25 持久 helper 写入 56 个样本：除首个早期样本外，55 个样本持续显示 `zygote`/`zygote_secondary` restarting，system_server/zygote64 PID 不存在；SurfaceFlinger 可列出 HWC display 0 与 BootAnimation layer，但没有成功物理 present 的直接证据。日志无 COMPLETE 标记、未达到设定 900 秒。用户全程看到中央小米 Logo + `powered by Android` 第一屏，未见 HyperOS 三点第二屏；ADB 未上线。

每个 Standalone 导出保留当时实际存在的原始 console-ramoops、pmsg-ramoops、oops.raw、Standalone dmesg、diag_status、源端校验文件、主机导出时间线和清单。缺失的文件不会补造。

## 完整性和排除项

C13–C20 的既有公开内容保持此前发布形态，可能包含设备标识、内核命令行和主机路径。C21 公开副本对设备序列号作了可追溯替换；C22–C24 原始诊断文件按用户授权逐字节发布。各自来源与公开副本 SHA-256 见累积清单。

RAW_EVIDENCE_EXCLUSIONS.csv 记录同步器因识别凭据特征、分区/固件镜像名称或单文件超过 100 MiB 而排除的文件。已发布诊断文件经过私钥 PEM、常见访问令牌、Bearer token 和密码赋值模式筛查；如发现真正凭据则从公开副本排除并记录。C21 序列号替换数量及各文件哈希见其专用清单。

完整 ROM、固件包、boot/system/super 镜像、userdata/metadata 分区镜像以及 misc/校准/身份分区备份不在本目录。C24 发布材料检查未发现常见可复用凭据特征；没有因此排除 C24 文件。


C25 的主机观察及持久 metadata 诊断已经公开；完整 C25 构建/刷写报告和脚本位于 reports/candidate25 与 tools。当前直接待查是 Zygote 退出首因，不是 C25 是否启动诊断服务。
