# THYME-OS4 项目当前状态

更新时间：2026-10-05 16:06 HKT（M01-R3 clean-data 首启进入 Android framework/UI；runtime capture 完成）

## 最终目标

将 Xiaomi 18 Pro Max（madrid）HyperOS 4 / Android 17 官方 OS4.0.19.0.XEOCNXM 移植到 Xiaomi 10S（thyme / Snapdragon 870 / SM8250-AC）。社区 Known-Good 基线为 madrid OS4.0.15 → thyme。

## 阶段状态

| 阶段 | 当前事实 |
| --- | --- |
| M00 Madrid Intake | 完成；Known-Good donor 确认为 madrid OS4.0.15，最终目标为官方 madrid OS4.0.19 |
| M01-R1 | 安全子集首启未见 ADB；本轮有效 kernel/pstore log 未取得 |
| M01-R2 | 仅补写 Known-Good top-level vbmeta 后仍未见 ADB；Standalone salvage 无本轮 kernel log |
| M01-R3 | 仅擦 userdata、metadata 后，未重刷 OS stack 的首启达到 Android framework/UI；ADB 与 runtime capture 完成 |
| M02 / Legacy-C48 | 未构建 |

## M01-R3 已验证事实

- Fastboot `erase userdata`、`erase metadata` 均 exit 0；没有 format、fastboot -w、FRP、firmware、B 槽或永久危险分区操作。
- R1/R2 的 Known-Good A 槽 stack 未重刷：boot、vendor_boot、dtbo、super、vbmeta、vbmeta_system。
- 一次授权启动后，ADB 于 T+238 秒成为 `device`；`sys.boot_completed=1`；900 秒 observer 结束时 ADB 仍在线。用户确认启动成功并打开 USB debugging。达到 Android framework/UI boot（Level 2 或更高）；物理 UI 子阶段没有屏幕录像佐证。
- 实际内核确认是 Known-Good `4.19.325-cxk`。R1/R2 pstore 为空不能据此推断其 kernel 未运行。
- Tethering APEX active/mounted；INetd/Tethering services 存在；netd running、updatable init 成功；BPF enabled 且主要 maps OK。没有活动 upstream/forwarding，热点数据路径未测。
- production `user` build 拒绝 shell 读取 `/proc/cmdline` 和 `/proc/<netd-pid>/maps`；精确 netd `.so` 映射未确认。
- 单次快照显示 `traced` restarting / `sys.init.updatable_crashing=1`，后续 review；非本次启动阻塞。

清除 userdata+metadata 与 R1/R2 未见 ADB 到 R3 Android framework/UI 成功强相关；clean-data 作为主要阻塞候选显著增强，但因两分区同时清除，具体因果贡献尚未隔离。详细报告见 [M01-R3_REPORT.md](../reports/m01_known_good_runtime/M01_R3_REPORT.md)。

## 当前阶段与下一步

M01-R3 clean-data Known-Good framework boot 已完成。保持现有 Android 系统运行；本轮不再 reboot、不进 Standalone、不刷写 firmware 或 OS，不构建 Candidate/Legacy-C48。下一步为审核 Known-Good runtime baseline，再规划对官方 madrid OS4.0.19 的移植。

原始 runtime capture 只保存在私有工作区；公开仓库仅同步脱敏报告，不包含 raw log、ADB dump、设备序列号或 ROM/image。

## 安全边界

- 不 relock；不写 persist、modemst、fsg/EFS、NV、RF calibration、identity 或 FRP。
- 不因 R3 成功而直接扩大 firmware 刷写；需先建立设备归属、rollback/anti-rollback 与恢复证据。
- userdata/metadata 已擦除；普通 OS rollback 不能恢复其中数据。
- 不公开 ROM、boot/super images、proprietary firmware 或 raw device logs。
