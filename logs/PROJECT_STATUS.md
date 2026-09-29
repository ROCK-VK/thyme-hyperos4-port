# THYME-OS4 当前状态

目标：将 Xiaomi 15（dada）的 HyperOS 4 / Android 17 用户空间移植到 Xiaomi Mi 10S（thyme）；当前优先进入 HyperOS 启动画面、设置向导或桌面。

## C27 最新结果（2026-09-29）
C27 已构建、刷入 super 与 vbmeta_system_a，并执行了一次受控首启。用户观察到 Logo、黑屏、Logo 短暂再现后进入 PixelOS Recovery。主机曾枚举到 ADB unauthorized，无法取得 Android shell/logcat。

C27 的持久 metadata 中存在 candidate=C27 action=post-fs-data 标记，强烈支持正常 Android init 到达 post-fs-data。两个 logcat status 文件和 Zygote event/tail 文件都为 0 bytes，没有 C27 logcat capture。故 C27 的 netd→Zygote callback 改动效果、system_server 状态和随后进入 Recovery 的直接原因仍未知。

Recovery console 只有一个可见 Recovery 启动实例。First-stage mount skipped (recovery mode) 和 Recovery 自己写 boot-recovery BCB 均发生在 Recovery 启动后，不能解释最初进入 Recovery。无 pmsg。

## 设备
最近 Fastboot 只读核验：product=thyme、current-slot=a、Bootloader unlocked、非 userspace Fastboot。A retry=6/unbootable=no/successful=no；B retry=7/unbootable=no/successful=no。设备保持 Bootloader Fastboot。

## 下一步
先修复/验证 C27 诊断 helper 创建输出文件后没有写入数据的问题，再决定下一次实验。本轮不构建 C28，不重启、不改分区、不清 userdata/metadata。详细结果见 [C27 首启与 Recovery 取证报告](../reports/C27_FIRST_BOOT_AND_RECOVERY_REPORT.md) 与 [C27 原始诊断证据目录](../evidence/candidate27/first-boot-20260929/README.md)。

此前已验证的 C9 Property Contexts、C11 EROFS 元数据、C14 BPF 与 C17 ION 权限修复继续保留。公开仓库不分发完整 ROM 或分区镜像；诊断文本副本已脱敏。
