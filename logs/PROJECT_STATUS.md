# THYME-OS4 项目当前状态

更新时间：2026-09-30

## 项目目标
将 Xiaomi 15（dada）的 HyperOS 4 / Android 17 移植至 Xiaomi Mi 10S（thyme）。当前首要目标是查明 C30 的 PID 1 fatal 条件和可靠取得 Zygote/system_server 有序证据。

## 当前 Candidate 与设备
- C30 的 super、vbmeta_system_a 已刷入 A 槽并正式启动一次。用户全程报告看到静止小米第一屏；没有观察到 HyperOS 动画、设置向导或桌面。
- C30 pstore 在启动约 32.922 秒记录 PID 1 init 经 write_sysrq_trigger 主动触发 kernel panic。触发 init fatal 的上游原因尚未确定。
- pmsg 证明 /data F2FS 挂载、fscrypt 和 keystore2 推进；重复 netd SIGABRT 确实存在，但与 Zygote/init panic 的因果未证明。
- C30 helper 只留下第一份 0-byte canary；ordered event 和 persistent logcat 没有结果。空文件不能区分 write 失败、panic 前未持久化或 helper 提前结束。
- A 槽启动前 retry=4；用户回到 Fastboot后、Standalone 前最近读数 retry=3，unbootable=no/successful=no。Standalone UMS 全卷取证完成后，最新只读 Fastboot 查询确认设备现处 Bootloader Fastboot：product=thyme、slot=a、unlocked=yes、is-userspace=no；A unbootable=no/successful=no/retry=3，B no/no/retry7。没有任何写入。
- 未刷写新 Candidate、未第二次启动 C30、未清除 userdata/metadata、未写 misc/BCB、未恢复 PixelOS。

## 证据和报告
- [C30 首次启动与取证报告](../reports/C30_FIRST_BOOT_AND_PSTORE_REPORT.md)
- [C30 首次启动主机及 Standalone 原始证据](../evidence/candidate30/first-boot-20260930/run_20260930_115223/)
- 本地 metadata.raw 与 misc.raw 均只读导出，完整原件保存在本地且未公开。

## 历史有效修复
C9 Property Contexts、C11 system_ext EROFS 元数据、C14 BPF loader 兼容、C17 graphics allocator ion_device open/read 权限均有实机阶段性证据；不能将主机静态验证写成最终开机成功。C27/C28/C29/C30 的 PID 1 与 Zygote 首因仍以各自最新 Candidate 报告为准。

## 下一步
设备保持 Bootloader Fastboot。离线定点追查 init 在 sysrq panic 前的 fatal 条件，同时修复 canary 首次持久写留证。当前不启动/重刷 C30、不构建 C31，直到获得足以解释或改进的具体证据。新 Candidate 正式启动前仍需用户现场确认。

## 安全和空间边界
不回锁 Bootloader；未经授权不修改 persist 硬件分区、modemst、EFS/NV、射频校准或设备身份分区。最近 C/D/E Free Space 分别为 92.73/198.09/231.49 GiB；没有触发清理，Docker 永远排除。