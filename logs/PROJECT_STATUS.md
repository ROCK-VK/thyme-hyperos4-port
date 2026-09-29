# THYME-OS4 项目当前状态

## 项目目标与当前阶段
将 Xiaomi 15（dada）的 HyperOS 4 / Android 17 移植到 Xiaomi Mi 10S（thyme）。近期目标是确认并越过 Android 启动第一屏，获得 HyperOS 后续启动界面。当前已刷入 Candidate 29（C29）；它是 PID 1 / Zygote 顺序诊断版，尚未启动。

## 当前设备与刷入状态
- 主机最近只读确认唯一设备：[设备序列号已脱敏]，Bootloader Fastboot。
- product=thyme；current-slot=a；unlocked=yes；is-userspace=no。
- A：unbootable=no、successful=no、retry=5。
- B：unbootable=no、successful=no、retry=7。
- C29 仅写入 super 与 vbmeta_system_a；刷前、写入时、刷后设备状态一致。
- C29 尚未正式启动；观察器尚未 ARMED。新 Candidate 首启须等用户现场确认。
- 本轮没有 reboot、set_active、userdata/metadata 擦除、misc/BCB 写入、PixelOS 恢复或 Bootloader 回锁。

## C28 已验证事实
- C28 唯一可见 console 启动实例在约 33.464 秒记录 PID 1 init 写 /proc/sysrq-trigger，随后 kernel panic；cmdline 有 androidboot.init_fatal_panic=true 和 androidboot.init_fatal_reboot_target=recovery。
- 触发 init fatal handler 的 signal、此前 init LOG(FATAL)、init userspace backtrace 和具体触发原因均未知。
- pmsg 有 5 个 SIGABRT 进程名 main 的记录，相关 SELinux AVC 位于 zygote 域；PID/进程与 primary/secondary 服务映射不明。
- 主机恢复 journal 后的 metadata marker 证明 netd 与 primary zygote 均曾 running/restarting，secondary zygote 曾 running；marker 无时间戳，不能排序或计算重启次数。PID 1063 身份未知。
- C28 primary Zygote init 配置带有 critical window 属性展开；实际 vendor 镜像 build.prop 静态值为 10，但运行时属性展开及 critical escalation 是否触发未实测。
- secondary Zygote 配置有 onrestart restart zygote，但 C28 证据不能证明它实际触发。C27 删除的 netd→Zygote callbacks 仍保持删除；netd 重启不是已证实的 Zygote 重启原因。
- C28 panic 后是否发生自动第二次 boot：未知；现有主机/pstore证据不足以证明或排除。

## C29 诊断方案和构建
- 仅替换 C28 诊断 RC/helper：有序 CLOCK_BOOTTIME + boot_id 事件记录、每 10ms 服务属性采样、system_server PID 首见采样、init 独立 marker 和最多 60秒/8MiB 单文件 logcat，并记录子进程启动/退出状态。
- 未更改 primary critical、secondary onrestart、netd、SELinux CIL、GPU/HWC、Framework、内核、fstab 或加密路径；这不是系统修复版。
- 构建报告：work/stage_c29_pid1_zygote_diag_20260929_run6/C29_PID1_ZYGOTE_DIAGNOSTIC_BUILD_REPORT.md。
- C29 super：7,703,587,800 bytes，SHA-256 A67994F75146E87EB74F772A2BEAF7547BFCC4B31C80C94003239FE6E47BB09D。
- vbmeta_system.img：131,072 bytes，SHA-256 A03AFBEDF1A60DDCBC3D0A1F9A391782876F15323F397F108CB8637CEA142A40。
- EROFS/readback、helper ELF、AVB hashtree/vbmeta descriptor、LP layout 主机检查通过；不等于实机诊断功能已验证。
- 刷写报告及 C28→C29 诊断决策报告在 work/reports/20260929_C29_PID1_ZYGOTE_FATAL_DIAGNOSTIC/。

## C29 下一步
1. 保持 Fastboot。无须再刷或切槽。
2. 启动前创建 C29 标签的全新观察目录并启动只读观察器，确认 ARMED。
3. 等用户明确现场确认后，只执行一次正式启动。
4. 若启动失败，先完整备份 Standalone 诊断卷及可授权的只读证据，再分析 C29 有序事件、logcat、init marker、pmsg/console。
5. 未获得 C29 时序证据前，不关闭 Zygote critical、不切断 secondary callback、不恢复 netd callback。

## 当前工程边界
- PixelOS A0′ 未在本轮恢复；当前系统分区为 C29。
- 不清除 userdata/metadata，不修改 misc/BCB，不回锁 Bootloader。
- persist 硬件分区、modemst、EFS/NV、射频校准及设备身份数据均禁止修改。
- C/D/E 空间门槛为任一低于 50 GiB 暂停新重型构建/提取；本轮门禁值 C=75.28、D=206.20、E=248.82 GiB，未清理；Docker 未触碰。
