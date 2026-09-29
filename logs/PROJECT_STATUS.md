# THYME-OS4 项目当前状态

## 项目目标
将 Xiaomi 15（dada）的 HyperOS 4 / Android 17 移植到 Xiaomi Mi 10S（thyme），当前重点是突破第一屏并进入 HyperOS 后续界面。最新刷入版本为 C28；未构建 C29。

## 最新 C28 结果
- C28 启动前 A 槽状态为 unbootable=no / successful=no / retry=6；启动后 A/B 状态尚未由主机读取。
- console-ramoops 仅见一个 Linux 4.19.325 实例。约 33.464 秒 PID 1 init 写入 /proc/sysrq-trigger，随后发生 kernel panic。命令行含 init_fatal_panic=true 和 init_fatal_reboot_target=recovery；触发 fatal 的信号与来源未知，未证实正常请求 Recovery。
- pmsg 记录 5 次 netd SIGABRT；PID 1063 main 的身份无法确定。
- 授权的只读 metadata 导出与设备端 SHA-256 一致。ext4 journal 只在逐字节校验过的主机工作副本上恢复，从中找到 12 个 C28 文件：9 个有内容、3 个零字节。
- Init marker 记录 netd 曾 restarting/running，zygote 曾 running/restarting，secondary zygote、SurfaceFlinger、bootanim、C28 watcher 曾 running，C28 logcat 服务记录为 stopped。marker 无时间戳，不能证明 netd restart 导致 zygote restart。
- logcat status、zygote events/tails 文件均为空；没有有效 C28 logcat。system_server、SystemUI/HOME、boot complete 和物理显示 present 未证实。用户报告 C28 约 8 分钟仍停在带 powered by Android 的静态 Xiaomi 第一屏，ADB 未上线。

## 当前设备状态
用户报告已返回 Bootloader Fastboot，但最近主机只读查询为 fastboot devices=0，仍枚举 THYME_DIAG UMS 卷；Bootloader Fastboot 和启动后的 A/B 状态尚未由主机确认。没有执行新的设备命令、写入或擦除。

## 下一步
请先通过实体按键退出 THYME_DIAG UMS。主机识别唯一 Fastboot 设备后，只读核对设备身份与 A/B 状态。之后定点检查其他 Zygote restart 来源及 init fatal signal 来源；当前不构建 C29、不重启、不清除数据。

## 边界
Bootloader 保持解锁；不修改硬件身份/校准、persist、modemst、EFS/NV 或 misc/BCB；不清 userdata/metadata。新 Candidate 启动前等待用户现场确认。公开增量位于 evidence/candidate28/first-boot-20260929/metadata-journal-recovery/，仅含 C28 marker、清单和来源说明；原始 metadata/misc、ROM 和分区镜像不公开。
