# THYME-OS4 Candidate 30 首次启动与取证报告

时间：2026-09-30（HKT）
状态：C30 正式启动一次；Unified First-Response Standalone 只读取证完成。未刷写新 Candidate、未第二次启动 C30、未恢复 PixelOS。

## 结论摘要

- 用户报告 C30 启动期间始终显示静止小米第一屏，没有 HyperOS 启动画面、设置向导、SystemUI 或桌面。
- C30 console-ramoops 在启动约 32.922 秒记录 PID 1（init）经 write_sysrq_trigger 主动触发 kernel panic。记录为 “sysrq: Trigger a crash” 和 “Kernel panic - not syncing: sysrq triggered crash”。这是 init 发起的显式崩溃路径，不是已证明的自发硬件故障。
- 具体哪个 init fatal 条件触发该动作，现有证据没有闭环。pmsg 记录 netd 多次 SIGABRT，但没有有序诊断数据证明 netd、Zygote 重启与 PID 1 panic 的因果关系。
- pmsg 记录 /data F2FS 检查和挂载成功、fscrypt 初始化及 keystore2 注册。这证明系统越过早期存储阶段，但不证明 system_server 已启动。
- C30 helper 创建了 write canary 文件，但最终为 0 字节；fdatasync、append、init 生命周期 marker、ordered events 和 logcat 结果均未取得。C30 持久诊断通道没有回答 Zygote/system_server 顺序。
- 观察器在启动前 ARMED；只执行一次 fastboot reboot。ADB 未上线。Fastboot 于启动命令后约 10 分 17 秒重新出现，用户报告在此期间屏幕一直是静止小米 Logo；之后一次 RAM 临时启动进入 Standalone UMS。
- Unified First-Response Standalone 先保存 pstore，再只读导出 raw metadata/misc，最后导出 THYME_DIAG 全卷。13 个文件及 2 个目录均完成源/副本大小与 SHA-256 校验，无枚举或复制失败。
- 当前主机实际看到 G: THYME_DIAG FAT32 诊断盘，fastboot devices 无设备。当前状态是 Standalone UMS，不是已确认的 Bootloader Fastboot。

## 实验时间线与屏幕观察

| 事件 | 时间（UTC） | 结果 |
|---|---:|---|
| 观察器 ARMED | 2026-09-30 03:52:30.520 | Bootloader USB 可见，ADB absent，Fastboot 可见 |
| 唯一 C30 启动命令 | 2026-09-30 03:54:45.3978599 | fastboot reboot 返回 exit 0 |
| Fastboot 再次出现 | 2026-09-30 04:05:02.493 | 启动命令后约 10 分 17 秒；用户报告期间始终为静止小米 Logo |
| Standalone UMS 出现 | 2026-09-30 04:07:00.824 | 主机识别 THYME_DIAG USB 诊断卷 |
| 观察器窗口结束 | 2026-09-30 04:12:24.356 | 观察器总窗口 20 分钟 |

启动前状态：唯一设备、product=thyme、slot=a、unlocked=yes、is-userspace=no；A 为 unbootable=no / successful=no / retry=4，B 为 no / no / retry=7。进入 Fastboot 取证时 A retry=3、unbootable=no、successful=no；B 未变化。没有执行 set_active。

用户观察的是静止的小米第一屏。BootAnimation tag 日志不能证明动画帧已呈现到面板；本次没有物理 display present 证据。

## C30 pstore 与启动阶段证据

Unified Standalone 只读挂载 pstore 并保存两条记录：

| 文件 | 字节数 | SHA-256 |
|---|---:|---|
| console-ramoops-0 | 292,646 | 9b10867ce85eef8ff439f6d013ba7c49f19a36cd452cbe622f0fb71f9a0c04e7 |
| pmsg-ramoops-0 | 90,225 | f23f288ea72b31c89e3a702f087e9aebf761ff4430933a3aafb61cc0109557a6 |

console 关键记录：

- 32.921975 秒：sysrq: Trigger a crash
- 32.921991 秒：Kernel panic - not syncing: sysrq triggered crash
- CPU 2、PID 1、Comm=init
- 调用路径包含 panic、sysrq_handle_term、__handle_sysrq、write_sysrq_trigger、proc_reg_write 和内核 write 路径。
- cmdline 包含 androidboot.init_fatal_panic=true、androidboot.init_fatal_reboot_target=recovery 和 panic=0。这些配置不能单独说明触发 init fatal 的先因。

pmsg 记录 /data F2FS fsck 与挂载成功、fscrypt key 初始化和 keystore2 服务注册；也记录多次 netd SIGABRT，回溯进入 libnetd_updatable.so 初始化路径。没有 C30 canary/event 输出，没有可用的有序 Zygote 或 system_server 事件。

analysis_work/pmsg_ascii_strings.txt 是从二进制 pmsg 提取的可打印 ASCII 片段，可能丢失二进制 framing、字段或非 ASCII 内容；它不是 pmsg 原件的替代品。分析以原始 pmsg 为准。

## C30 canary 与 metadata 主机副本检查

本机保留的 16 MiB metadata.raw，SHA-256 为 [本地保留；公开版本隐藏 raw metadata SHA-256]。仅在独立 host working copy 上执行 ext4 journal recovery/debugfs；设备 raw 原件没有改写。

恢复后的 /thyme_os4_diag 中发现：

- C30_CANARY_WRITE_6728b915-48bc-4b45-88b2-b8451ccc5e26.txt：inode 319，size 0，blocks 0，uid/gid 2000，mode 0660，SELinux xattr 为 u:object_r:c25_diag_data_file:s0。
- 父目录的 SELinux type 同为 c25_diag_data_file。
- C30_CANARY_FDATASYNC、C30_CANARY_APPEND、init helper running/stopped marker 与 ordered event 文件均未恢复。
- merged policy 静态内容包含 c30_diag 对目标目录/文件 type 的必要权限及 type transition；现有证据不支持继续扩大 SELinux allow。
- 0 字节说明第一份 canary 没有留下 payload。证据不能区分 write 返回失败、写入未能在 panic 前持久化，或 helper 在首次有效写入前被终止；没有 errno、C30Diag 日志或 init marker 可进一步定界。不能确认 logger 是否执行到 logcat。
- metadata 工作副本的 e2fsck 修复不能用于推断 raw 分区被修改。raw 文件保持原样。

misc.raw 也仅只读导出：4,194,304 bytes，SHA-256 为 [本地保留；公开版本隐藏 raw misc SHA-256]；没有写入 misc/BCB。两个 raw 分区副本仅保存在本地，不公开。

## 当前能回答与仍未知

| 问题 | 当前结论 |
|---|---|
| C30 是否启动到正常 Android 用户空间 | 是；/data、fscrypt、keystore2 及多个服务有 pmsg 记录 |
| 静止 Logo 的最强原因证据 | init 在约 32.922 秒主动触发 sysrq panic；触发 init fatal 的上游条件未知 |
| netd 是否失败 | 是；pmsg 中有重复 SIGABRT |
| netd 是否导致 Zygote 重启或 init panic | 未证明 |
| Zygote 是否稳定、system_server 是否出现 | 证据不足；C30 ordered logger 未留下数据 |
| BootAnimation 是否真正显示 | 未证明；用户看到静止小米第一屏，BootAnimation tag 不是物理呈现证据 |
| ADB / boot completed / SystemUI / HOME | ADB 未上线；没有可靠 boot completed、SystemUI、SetupWizard 或 Launcher 记录 |
| C30 canary 是否解决留证问题 | 否；只看到第一文件创建，payload 未留存 |

## 设备与操作边界

C30 正式启动命令仅执行一次。之后一次 fastboot boot 临时启动已核验的 Unified First-Response Standalone。没有 Candidate 刷写、第二次 C30 启动、set_active、userdata/metadata 清除、misc/BCB 写入、PixelOS 恢复或 Bootloader 状态修改。

最后一次主机实时查询：G: THYME_DIAG（FAT32）存在，Fastboot 未枚举到设备。A retry=3 是 Standalone 前的最近 Fastboot 查询值；Standalone UMS 下没有新的 boot-control 实时读数。

## 本地证据路径

- 观察器：work/reports/candidate30_first_boot_20260930/observations/run_20260930_115223/
- 全卷备份：work/reports/candidate30_first_boot_20260930/standalone/run_20260930_120848/THYME_DIAG/
- 文件校验：同级 file_verification.csv、copy_verification_summary.json
- metadata 分析副本：work/reports/candidate30_first_boot_20260930/analysis_work/metadata_workcopy.raw
- 可搜索 pmsg 片段：work/reports/candidate30_first_boot_20260930/analysis_work/pmsg_ascii_strings.txt

## 下一步

不启动或重刷 C30，不清数据，不修改 A/B 状态。下一轮先定点追查 PID 1 在约 32.9 秒触发 sysrq 前的 init fatal 条件；同时修复 C30 diagnostics 的首条持久写留证路径，不能只依赖 helper 报告自己的写错误。取得可靠事件顺序后，再决定是否需要 C31 或最小启动策略修改。
