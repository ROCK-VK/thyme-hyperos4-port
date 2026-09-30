# THYME-OS4 项目当前状态

更新时间：2026-09-30

## 项目目标与当前阶段
将 Xiaomi 15（dada）的 HyperOS 4 / Android 17 移植到 Xiaomi Mi 10S（thyme）。当前阶段是用可靠诊断留证确认 Zygote、netd 与 system_server 的启动顺序。

## Candidate 与设备状态
- C30 已将 `super` 与 `vbmeta_system_a` 刷入 A 槽；其他引导分区未改。刷写后仍是 Bootloader Fastboot，尚未启动 C30。
- 刷后只读状态：product=thyme，A 槽，unlocked=yes，is-userspace=no；A `unbootable=no/successful=no/retry=4`，B `no/no/7`。刷写前后完全一致。
- 本轮没有 reboot、set_active、数据擦除、Standalone 启动或其他分区操作。等待用户单独授权首次启动。

## C29 写入审计结论
- C29 events/status 文件 inode 已创建但恢复后为 0 bytes；实际目录和文件 SELinux type 为 `c25_diag_data_file`。merged platform policy 有 shell→该 type transition 及必要的 write/append 权限，neverallow 检查通过。
- C26 同目录/同 type 曾有非空输出。当前证据不能区分 C29 首次 write 失败、fdatasync 未持久化或 helper 在首条 payload 前结束；没有依据扩大 shell 权限。
- inode 明细见 [`C29_WRITE_ROOT_CAUSE_AND_C30_DECISION.md`](C29_WRITE_ROOT_CAUSE_AND_C30_DECISION.md)。

## C30 诊断版本
- C30 使用 `c30_diag` 专用域，先运行 write/fdatasync/append 三项 canary；仅全部成功后才启动 ordered events 与最长 60 秒、无轮转 logcat。init 另写生命周期 markers。
- neverallow、EROFS readback、fsck、AVB/vbmeta_system 与 LP 检查通过；C30 runtime canary/logger、服务顺序和 system_server 仍未实机验证。
- `super`：7,703,591,896 bytes，SHA-256 `071A86171450B5832E2951E63145D0B5AB55AB622BDDEFB249781B819B1CC83C`。
- `vbmeta_system_a`：131,072 bytes，SHA-256 `D116F268C015382D5B7F0162959563530D1CFAFC368ED7C1D5DF0514743E5C75`。
- 详细门禁及刷写结果见 [`C30_FINAL_STATIC_GATE_AND_FLASH_REPORT.md`](C30_FINAL_STATIC_GATE_AND_FLASH_REPORT.md)。受限脚本位于 `tools/flash_candidate30_diag_write_canary.ps1`，带 `-Execute` 才写入且限定两分区。

## 首次故障取证
Unified First-Response Standalone run2 已主机侧构建、静态检查，尚未 RAM boot。故障后的首次 Standalone 应优先保存 pstore，再 raw-read metadata/misc，最后完整导出 THYME_DIAG 并核验。

## 下一步
等待用户明确授权首次启动 C30。启动前启动观察器并确认 ARMED；C30 故障后第一次 RAM boot 使用 Unified First-Response Standalone。C/D/E 低于 50 GiB 才暂停新建构/大型提取；Docker 始终排除。