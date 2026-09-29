# THYME-OS4 项目当前状态

更新时间：2026-09-30

## 项目目标与阶段
将 Xiaomi 15（dada）的 HyperOS 4 / Android 17 移植到 Xiaomi Mi 10S（thyme）。当前重点是让诊断留证可靠，并确定 PID 1、Zygote 与 system_server 的真实启动顺序。

## Candidate 与设备状态
- 设备上最后确认的 Candidate 是 C29；本轮没有刷写或启动新 Candidate。
- C29 正式启动后用户看到 Xiaomi 第一屏，ADB 未上线；A 槽最近可靠记录 retry=4、unbootable=no、successful=no。本轮没有查询设备，因此当前设备模式未确认，可能仍为 THYME_DIAG UMS。
- 本轮未执行 reboot、set_active、刷写、擦除或持久分区修改。

## C29 零字节留证结果
- C29 event 与 logcat status inode 已创建，但恢复后的 size/blocks 为 0/0。
- 诊断目录、文件和 init markers 的真实 SELinux type 为 `c25_diag_data_file`；C29 平台策略包含 shell 所需文件 write/append、目录 add_name 权限及 type transition，host neverallow 检查通过。
- C26 同目录、同 type 的 events/logcat 曾非空，因此没有证据支持“该 type 一直不可写”。C29 首次 write 失败、fdatasync 未持久化、或 helper 在 payload 前退出仍无法区分；不扩大 shell 权限。
- inode 详情和限制见 [`C29 写入审计与 C30 决策`](../reports/candidate30/C29_WRITE_ROOT_CAUSE_AND_C30_DECISION.md)。

## 诊断与构建资产
- Unified First-Response Standalone run2 已主机侧构建，尚未设备 RAM 启动。顺序为只读 pstore 复制及 SHA → 唯一 sysfs 身份验证的 raw metadata → misc → 独立 Standalone dmesg → 全量 manifest/SHA → RAM UMS；metadata 不挂载、不 replay journal。
- C30 已完成主机侧构建，未刷写/启动。采用 `c30_diag` 专用 SELinux domain、三项独立 write/fdatasync/append canary、init built-in lifecycle markers；canary 通过后才启动有序事件与 60 秒无轮转 logcat。system_server PID 从 logcat 启动事件/`SystemServer` tag 提取，不扫描通用 `/proc`。
- 第一次静态 CIL 检查拦截了通用 `/proc` 读取；移除后 `secilc`/neverallow、AArch64 helper、EROFS、fsck、AVB/vbmeta_system 和 LP 关系验证通过。
- C30 实际 canary、logger 持久写、zygote/netd 时间顺序、system_server PID 与 critical escalation 尚未实机验证。没有证据要求关闭 Zygote critical 或修改 secondary callback。
- 本轮报告及源码在 `reports/candidate30/` 和 `tools/`。仓库不分发完整 ROM、Candidate 镜像或原始 metadata/misc 备份。

## 下一步
后续若获准进入设备阶段，先确认退出 UMS 并只读核对 Fastboot、设备身份与槽位。测试 C30 前需相应的刷写/启动授权；故障后第一次 RAM boot 使用 Unified First-Response Standalone，优先保存 pstore，再导出 metadata/misc，完成全量主机校验后分析。

C/D/E 空间门槛为 50 GiB；Docker 始终排除。
