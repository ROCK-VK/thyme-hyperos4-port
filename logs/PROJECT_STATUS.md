# THYME-OS4 项目当前状态

## 目标与当前阶段
将 Xiaomi 15（dada）的 HyperOS 4 / Android 17 移植到 Xiaomi Mi 10S（thyme）。当前优先突破开机第一屏并进入 HyperOS 动画、设置向导或桌面。Candidate 28 是 C27 的诊断增强版；本轮已构建并刷写，但尚未启动。

## 当前设备与烧录版本
- 最新只读核验：唯一设备 [设备序列号已脱敏]，product=thyme，current-slot=a，unlocked=yes，is-userspace=no。
- A 槽：unbootable=no、successful=no、retry=6。
- 当前设备保持 Bootloader Fastboot。
- C28 已刷入 super 与 vbmeta_system_a；boot、vendor_boot、dtbo、vbmeta 及其他分区继承原值。
- C28 尚未首次启动；实际运行版本因此尚未确认。

## 最近启动证据
- C26 真实 logcat 证明 netd 因 Android 25Q2+ 拒绝 Linux 4.19 而 SIGABRT；PID 1 随后停止两个 Zygote。C27 保留这一问题，但移除了 netd 到 Zygote 的 onrestart 回调，修复效果尚无有效用户空间日志验证。
- C27 到达 post-fs-data 的 metadata marker 已保存。用户观察到 Logo→黑屏→Logo→PixelOS Recovery；Recovery 后续 pstore 不能解释 Recovery 起因。
- C27 的 logcat、zygote event/tail 输出都是零字节，Zygote 与 system_server 状态未知。A 槽启动预算从 7 降到 6，unbootable=no。
- 对最终 C27 init 配置的定点扫描仅找到两条显式 rebootrecovery --bad_nv action，条件分别涉及 persist.vendor.radio.write.cache 与 persist.radio.write.cache。C27 没有保存触发值或 sys.powerctl；根因未确认。

## C28 变更与资产
- C28 仅替换 C27 诊断 helper/RC，并在 post-fs-data、netd/Zygote/bootanim/SurfaceFlinger 状态变化、boot complete、sys.powerctl、shutdown 和两个既有 --bad_nv recovery action 前增加 init 内建 marker。
- 修复 logger 早期留证窗口：状态文件打开后立即 START+fsync；持久保存 helper/child PID；exec errno、wait 状态、退出码、信号、stderr、stop reason。单文件 logcat，最长约 8 分钟、最多 24 MiB；不使用轮转。
- 继续保留 C27 删除的 netd onrestart restart zygote/zygote_secondary 回调；没有改 netd 内核版本检查，也未改 ART、Zygote、GPU/HWC、Framework、SELinux CIL、fstab、加密、内核或硬件栈。
- 构建目录：work/stage_c28_recovery_zygote_diag_20260929_run4/
- 镜像目录：work/stage_c28_recovery_zygote_diag_20260929_run4/images/
- 构建清单与报告：images/BUILD_MANIFEST.json、work/stage_c28_recovery_zygote_diag_20260929_run4/C28_RECOVERY_ZYGOTE_DIAGNOSTIC_BUILD_REPORT.md
- 构建/刷写交接报告：work/reports/20260929_C28_RECOVERY_ZYGOTE_DIAGNOSTIC/C28_FLASH_AND_HANDOFF_REPORT.md
- 受限刷写脚本：tools/flash_candidate28_recovery_diag.ps1
- 只允许的 C28 刷写目标：super、vbmeta_system_a。

## 验证级别
- C28 主机侧构建、EROFS/AVB/vbmeta/LP 和 helper 静态核验通过。
- C28 super 与 vbmeta_system_a 已实际写入，Fastboot 返回成功，写入后状态重新核验通过。
- C28 init marker、helper 启动、logd 读取/输出留存、Zygote/system_server 状态和 Recovery 起因均未实机验证。
- C27 netd→Zygote 修改效果及 C27 Recovery 根因仍未知。

## 下一步
等待用户在手机旁明确确认可以首次启动 C28。启动时观察器先 ARMED，再只执行一次 Fastboot reboot。若失败并由用户回到 Fastboot，先完整复制和校验 THYME_DIAG/C28 metadata，再分析；不得在取证前恢复系统。

## 固定边界
Bootloader 必须保持解锁。禁止回锁；不得擅自修改 persist 硬件分区、modemst、EFS/NV、射频校准、设备身份或 misc/BCB；不得无依据清 userdata/metadata。C28 本轮未执行擦除、set_active、切槽或 reboot。
Standalone 只读取证及已限定的普通 Candidate 分区刷写沿用既有授权；每个新 Candidate 正式启动仍需用户在场确认。Docker 相关资产绝不触碰。
磁盘规则：C/D/E 任一盘低于 50 GiB 时才暂停重型构建/大型提取并治理项目占用；Docker 及无法确认属于项目的 WSL 资产排除。本轮最近余量约 C 77.76、D 206.15、E 250.92 GiB，未触发清理。
