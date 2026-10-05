# THYME-OS4 项目当前状态

更新时间：2026-10-05 22:07 HKT（MADRID-M02 Candidate r3 已 staged，正式首启未执行）

## 最终目标

将 Xiaomi 18 Pro Max（madrid）HyperOS 4 / Android 17 官方 OS4.0.19.0.XEOCNXM 移植到 Xiaomi 10S（thyme / Snapdragon 870 / SM8250-AC）。社区 Known-Good 基线为 madrid OS4.0.15 → thyme。

## 阶段状态

| 阶段 | 当前事实 |
| --- | --- |
| M00 Madrid Intake | 完成；Known-Good donor 确认为 madrid OS4.0.15，最终目标为官方 madrid OS4.0.19 |
| M01-R1 | 安全子集首启未见 ADB；本轮有效 kernel/pstore log 未取得 |
| M01-R2 | 仅补写 Known-Good top-level vbmeta 后仍未见 ADB；Standalone salvage 无本轮 kernel log |
| M01-R3 | 仅擦 userdata、metadata 后，未重刷 OS stack 的首启达到 Android framework/UI；ADB 与 runtime capture 完成 |
| MADRID-M02 r3 | 离线构建及静态门禁通过；A 槽/shared 分区写入与 data clean 完成；当前停在 Bootloader Fastboot，等待唯一首启确认 |

## MADRID-M02 r3 当前状态

- Exact Official madrid OS4.0.15.0.XEOCNXM 已与实机验证的 Known-Good port 4.0.15、Official 4.0.19 完成三方差异分析；C1–C47 保持研究数据库，Legacy-C48/netd NOP 不在当前主线。
- Candidate 使用 Known-Good boot/vendor_boot/dtbo/vbmeta/vbmeta_system 和 thyme vendor/odm/mi_ext 适配，叠加 Official 4.0.19 `system`/`system_ext` changed paths 与 allowlisted build properties；不包含 Madrid firmware、DLKM、B 槽或保护分区。
- 12-image inventory/hash gate、EROFS/ext4 检查、三套 EROFS tree round-trip、property allowlist、LP metadata checksum 与 A/B extent gates 均通过。Candidate super raw 展开大小为 9,126,805,504 bytes；candidate static validation 不等于 Android runtime 验证。
- 六条镜像 flash、`erase userdata`、`erase metadata`、`set_active a` 均 exit 0。擦除命令响应曾提示对应 filesystem 可 format，但 `erase` 返回 `OKAY`；没有执行 format。
- Post-check：product `thyme`、slot A、unlocked、Bootloader Fastboot、A 槽 not-unbootable、retry budget 7、Fastboot 在线；slot-successful 当前为 `no`。没有正式 reboot。
- 唯一待用户动作：明确发送 **“开始启动 MADRID-M02”** 后才进行本轮第一次正式启动。Candidate 的运行阶段尚未验证。
- M02 candidate、staging、super 预算及三方 delta 报告均见 [`reports/m02_adaptation_delta/`](../reports/m02_adaptation_delta/)。

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

M01-R3 clean-data Known-Good framework boot 已完成并继续作为恢复基线。M02 已完成 staging；当前设备处于 Bootloader Fastboot，禁止在确认前启动 Candidate。Legacy-C48 不在当前路线。

原始 runtime capture 只保存在私有工作区；公开仓库仅同步脱敏报告，不包含 raw log、ADB dump、设备序列号或 ROM/image。

## 安全边界

- 不 relock；不写 persist、modemst、fsg/EFS、NV、RF calibration、identity 或 FRP。
- 不因 R3 成功而直接扩大 firmware 刷写；需先建立设备归属、rollback/anti-rollback 与恢复证据。
- userdata/metadata 已擦除；普通 OS rollback 不能恢复其中数据。
- 不公开 ROM、boot/super images、proprietary firmware 或 raw device logs。
