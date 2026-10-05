# THYME-OS4 项目当前状态

更新时间：2026-10-05 15:10 HKT（M01-R2 单次首启未推进；Standalone 取证完成；等待下一阶段审核）

## 最终目标

将 Xiaomi 18 Pro Max（madrid）HyperOS 4 / Android 17 官方 OS4.0.19.0.XEOCNXM 移植到 Xiaomi 10S（thyme / Snapdragon 870 / SM8250-AC）。

- Known-Good 参照：社区 madrid OS4.0.15 → thyme 包。
- Legacy C1–C47 保留为 thyme Android 17 compatibility research database，不删除、不重做；C43/C47 hack 仅为诊断或 fallback 参考。
- M00 已完成；M01 用 Known-Good 建立实机基线；在 Known-Good 真正进入 Android 前不构建 M02/Legacy-C48。

## 阶段状态

| 阶段 | 状态 |
| --- | --- |
| M00 Madrid Intake | 完成；Known-Good donor 确认为 madrid OS4.0.15，最终 donor 为 madrid OS4.0.19 |
| M01-R1 | 五分区安全子集首启未成功；无可归属到该次启动的 kernel/pstore log；未复现原包完整刷机矩阵 |
| M01-R2 | 仅补刷 Known-Good top-level vbmeta_a，写入成功；一次授权启动会话后回到 Fastboot，ADB 未出现；Standalone RAM salvage 完成 |
| M02 / Legacy-C48 | 未构建 |

## M01-R2 现场事实

- 写入前设备门禁通过：thyme、A 槽、unlocked、retry=7；Known-Good vbmeta 与本地回滚资产 size/SHA256 匹配冻结记录。
- R2 唯一分区变化是 top-level vbmeta_a；没有刷 firmware、其他 OS 分区、userdata/metadata，也没有 relock。
- 启动命令被接受；主机观察到 Fastboot USB 离开约 33 秒后重新枚举；ADB 全程未出现。失败后 A 槽 retry=5（减少 2），unbootable=no、successful=no。没有再次启动 ROM。
- 物理屏幕画面未由主机记录，无法独立确认 Logo/黑屏的准确时序或失败 boot stage。
- 用户确认回到 Fastboot 后，使用 Standalone RAM boot 完成 THYME_DIAG 全目录导出；6 个文件、16,936,141 bytes，源/副本尺寸与 SHA256 复核通过，copy errors=0；清单留在私有工作区。
- pstore 挂载成功但记录为 0；无 M01-R2 console-ramoops、pmsg-ramoops 或其他 Known-Good kernel log。4.19.325-perf banner/dmesg 属于 Standalone。oops.raw 与历史 R1/C47 文件相同。
- 因此 Known-Good kernel 是否执行、init/first-stage、super、dm/AVB、dtbo、panic/watchdog、SELinux/init、vendor_boot/ramdisk 与 firmware dependency 均无法判定。
- R2 未显示 Android 启动推进，top-level vbmeta 是唯一/主要阻塞的假说降级但未完全排除。R1 旧记录按重试时间推断“second-stage 前失败”仍未获日志验证。

详细报告：[M01-R2 受控实验报告](../reports/m01_known_good_runtime/M01_R2_REPORT.md)；[R1 失败现场报告](../reports/m01_known_good_runtime/M01_FAILURE_SALVAGE_REPORT.md)。

## 下一阶段审核

返回 Known-Good 原始刷机矩阵做差异评估，优先研究：

1. firmware dependency；
2. boot/vendor_boot/ramdisk 配对；
3. dtbo；
4. clean-data requirement。

本轮不重复启动、不扩大刷写、不构建 Candidate。后续设备操作需下一阶段明确审核。

## 安全边界

- 不 relock；不写 persist、modemst、fsg、EFS/NV、校准或身份分区。
- 不擦 userdata/metadata；没有日志依据前不刷 firmware。
- 不公开 ROM、super、boot、raw pstore/oops 或其他专有二进制。
- 若后续进入 Android 并出现 ADB，先保持系统运行并采集 runtime evidence。
