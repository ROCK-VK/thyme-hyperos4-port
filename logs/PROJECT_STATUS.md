# THYME-OS4 项目当前状态

更新时间：2026-10-05 14:43 HKT（M01-R1 失败现场已打捞；无有效 M01 kernel log；M01-R2 等待设备返回 Fastboot）

## 最终目标

将 Xiaomi 18 Pro Max（madrid）HyperOS 4 / Android 17 官方 OS4.0.19.0.XEOCNXM 移植到 Xiaomi 10S（thyme / Snapdragon 870 / SM8250-AC）。

- Known-Good 参照：社区 madrid OS4.0.15 → thyme 包。
- Legacy C1–C47 保留为 thyme Android 17 compatibility research database；不删除、不重做。C43/C47 userspace patch 仅作 fallback/诊断参考，不默认带入 madrid 线。
- M00 Madrid Intake 已完成。M01-R1 失败不否定 Known-Good 原包，因为 R1 只测试五分区安全子集，没有复现原包完整刷机矩阵。

## 阶段状态

| 阶段 | 状态 |
| --- | --- |
| M00 Madrid Intake | 完成；成功包 donor 静态确认为 madrid OS4.0.15，最终目标为 madrid OS4.0.19 |
| M01-R1 受控刷写 | 五项写入均返回 OKAY：vbmeta_system_a、boot_a、vendor_boot_a、dtbo_a、super |
| M01-R1 首启 | 失败于 Level 0；Mi Logo 与黑屏交替后回到 Fastboot；ADB 未出现 |
| M01-R1 RAM 现场打捞 | 完成；THYME_DIAG 全目录校验归档，但 pstore 记录数为 0，没有 M01 kernel log |
| M01-R2 | 仅补刷 Known-Good top-level vbmeta_a 的方案已准备；尚未刷写、尚未启动 |
| M02 / Legacy-C48 | 未构建 |

## M01-R1 现场事实

- R1 未刷 top-level vbmeta_a；未刷底层 firmware；未清 userdata/metadata；未 relock。
- 主机观察器记录设备离开 Fastboot 后再次回到 Fastboot；ADB 从未出现。
- A 槽 retry 从 7 降到 0、unbootable 从 no 变 yes；随后 set_active a 将 retry 恢复为 7、unbootable 恢复为 no。
- 每轮约 20 秒与早期失败相容，但这不足以判定具体失败点。
- RAM 归档完整保存在私有工作区。pstore 挂载成功但没有 console-ramoops 或 pmsg-ramoops；无其他 M01 kernel log。
- dmesg_diag_boot.txt 是 Standalone 自身的 4.19.325-perf 日志，不是 Known-Good 4.19.325-cxk 日志。
- oops.raw 与 C47 旧归档散列相同，是历史残留。原始 oops/pstore/设备日志未公开上传。
- Known-Good kernel 是否开始执行、init/first-stage、super mount、dm/AVB、dtbo、panic/watchdog、SELinux/init、vendor_boot/ramdisk、firmware dependency 均无本次证据可判断。

详细报告：reports/m01_known_good_runtime/M01_FAILURE_SALVAGE_REPORT.md。

## 根因判断

M01-R1 根因未确定。top-level vbmeta 中旧 hash descriptor 是否阻止新 boot/vendor_boot/dtbo 镜像，是优先级较高的 C/D 级单变量假说，但没有真机日志闭环，不是已确认根因。其他候选仍包括 Known-Good kernel、boot ramdisk/vendor_boot 配对、dtbo、固件环境和 super/metadata 挂载。

## M01-R2 预检

- 目标：Known-Good 包 top-level vbmeta，4,096 bytes，SHA256 D2E1979739EC67076A90B0FC625DAE84A1AA2ED72D05D2B55D52539E3462B442；静态结构 Algorithm NONE、Flags 2、无 descriptors。
- 本地回滚镜像：131,072 bytes，SHA256 6D46FA9E36D2FFC9BF45F5365691A85AED488622F0254C864EFF3DD42A23FE6D。文件与散列已复核；Fastboot 无法读取设备分区原始字节。
- R2 目前没有刷写。取证后 Fastboot 与 ADB 均未枚举；设备需要先返回 Bootloader Fastboot，并重新确认身份、slot、unlocked、is-userspace、retry 与 unbootable。
- 实时门禁通过后只刷 vbmeta_a；不重刷 boot、vendor_boot、dtbo、super、vbmeta_system，不刷 firmware，不清 userdata/metadata。
- 刷后恢复并复核 A 槽 retry budget，停在 Fastboot。用户明确说“开始启动 M01-R2”前不得启动。
- 若启动，最多允许一轮失败；首次明显黑屏或自动重启即进入 Fastboot 并立即 Standalone 取证。

## 永久边界与下一步

- 不 relock；不写 persist、modemst、fsg、EFS、NV、calibration 或 identity。
- 不把 madrid firmware 写入 thyme；无日志依据前不刷 firmware。
- 不擦 userdata/metadata。
- 若 M01-R2 出现 ADB，保持系统运行并先采集 runtime evidence。
- 当前下一步：现场返回 Bootloader Fastboot，重新执行只读门禁；再进行 M01-R2 单分区刷写并停在 Fastboot。
