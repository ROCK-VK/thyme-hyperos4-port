# C27 首次启动与 Recovery 取证报告

日期：2026-09-29
Candidate：C27 netd→Zygote restart callback isolation
结论等级：启动路径有局部证据；自动进入 Recovery 的直接原因仍未知。

## 1. 本轮实际启动与主机观察

观察器先 ARMED，随后仅执行一次 fastboot reboot，命令返回码 0。启动前设备为 thyme、A 槽、Bootloader 解锁、非 userspace Fastboot，A retry=7、unbootable=no、successful=no。主机时间线随后记录 Fastboot 消失；约 78 秒时 ADB 枚举为 unauthorized，不能读取 shell 或 logcat。用户现场看到小米 Logo、黑屏、Logo 短暂再现后进入 PixelOS Recovery。

## 2. 首次 Standalone：pstore 与全卷备份

目录：work/reports/20260929_C27_NETD_ZYGOTE_CYCLE_BREAK/standalone_salvage/run_20260929_162753/

THYME_DIAG 中全部 7 个可访问文件均复制完成，源/副本大小及 SHA-256 一致，0 个复制错误。唯一 pstore 文件 console-ramoops-0 为 199,722 bytes，SHA-256：

FFA909CC628CB285357B7ED25437A20199AD17CF4C3278D00DD840C665C2EB06

该 console 只有一个可见 Linux 启动实例，且属于 Recovery：init 在约 1.789 秒报告 recovery mode 并跳过 first-stage mount；Recovery 在约 3.109 秒读取 boot-recovery 并写入 BCB。该写入发生在 Recovery 已运行后，不能证明 C27 启动前的 BCB 状态，也不能解释最初为何进入 Recovery。此 console 没有清数据指令、panic 或明确 C27 普通 Android fatal。没有 pmsg。

dmesg_diag_boot.txt 是 Standalone 自身日志；oops.raw 的内核构建标识来自 2024 年旧 vendor 内核，不属于本轮 C27。两者均未作为 C27 启动日志。

## 3. 第二 Standalone：metadata 只读导出

目录：work/reports/20260929_C27_NETD_ZYGOTE_CYCLE_BREAK/standalone_salvage/metadata_export/run_20260929_163125/

使用既有 C25 metadata 导出镜像。验证记录显示 /metadata/thyme_os4_diag 实际以 ext4,ro,relatime,norecovery 挂载；14 个 metadata 内容文件均有源/副本大小及 SHA-256 一致记录。导出器进程返回非零，仅因通用脚本要求顶层 dmesg_diag_boot.txt，而此 metadata-only 镜像不会生成该文件；这不是 metadata 文件复制不匹配。只读导出另含 misc.raw，本地保留，未发布；该次读取发生在 Recovery 之后，不能还原启动前 BCB。

C27 文件证据：

- C27_INIT_TRIGGER.txt 内容为 candidate=C27 action=post-fs-data，33 bytes，SHA-256 A437C34E643BA1AD5E38CF7AD051421070E660499A3A446B3F13C0A8D63AB128。
- 两个 C27_logcat_status 文件均为 0 bytes。
- C27_zygote_events 与 C27_zygote_tails 均为 0 bytes。
- 没有 C27 logcat capture 文件。

post-fs-data marker 是 C27 init action 触发的强证据，支持这次启动至少到达了正常 Android 的 post-fs-data 路径。零字节诊断文件说明输出没有留下任何有效样本；不能据此判断诊断服务是被提前终止、写入失败，还是数据未持久化，也不能判断 netd 是否重启、Zygote 是否稳定或 system_server 是否 fork。

## 4. 当前工程判断

C27 的实验问题仍未回答：移除 netd 的两条 Zygote onrestart 回调是否让 Zygote 存活。事件链最符合“C27 正常启动路径至少走到 post-fs-data，之后发生重启/转入 Recovery”，但第一次启动的 console/pmsg 未保留，无法确认中间错误或是否经历了第二个启动实例。Recovery 自身的 BCB 操作不能当作最初 Recovery 原因。

因此不宣布 C27 修复成功或失败，也不据此构建 C28。下一次工程修改应先解决诊断 helper 文件创建后保持零字节的问题，再设计一次可解释的启动实验。

## 5. 当前设备与操作边界

主机已重新枚举唯一 Fastboot 设备 [REDACTED_DEVICE_SERIAL]，只读结果：

- product=thyme，current-slot=a，unlocked=yes，is-userspace=no；
- A：unbootable=no，successful=no，retry=6；
- B：unbootable=no，successful=no，retry=7。

自 C27 首启以来只进行了 RAM Standalone 和只读取证；没有重新刷写、清除 userdata/metadata、切槽、set_active、写 misc/BCB 或恢复 PixelOS。设备当前保持 Bootloader Fastboot。

## 6. 证据位置与公开副本

本地原始取证保留在本报告开头列出的两个独立 run 目录。将发布的 C27 文本证据放在公开仓库 evidence/candidate27/first-boot-20260929/；文本日志公开副本对设备序列号、CPUID 和主机名作脱敏，misc.raw、oops.raw 不公开。每个公开文件的来源、原始/公开副本 SHA-256 记录于该目录的 manifest。
