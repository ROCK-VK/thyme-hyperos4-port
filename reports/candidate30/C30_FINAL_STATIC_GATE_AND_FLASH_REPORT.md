# THYME-OS4 C30 最终静态门禁与受限刷写报告

时间：2026-09-30 11:19 HKT

## 结果

C30 通过最终静态门禁，已仅刷写 `super` 和 `vbmeta_system_a`。刷写后设备仍为 Bootloader Fastboot；没有 reboot、Standalone 启动、`set_active`、擦除、PixelOS 恢复或其他分区操作。C30 尚未启动，等待用户下一条明确的首次启动授权。

## 镜像与 C29→C30 差异

- `super.img`：7,703,591,896 bytes；SHA-256 `071A86171450B5832E2951E63145D0B5AB55AB622BDDEFB249781B819B1CC83C`。
- `vbmeta_system.img` → `vbmeta_system_a`：131,072 bytes；SHA-256 `D116F268C015382D5B7F0162959563530D1CFAFC368ED7C1D5DF0514743E5C75`。
- 独立 `Get-FileHash` 与 C30 `BUILD_MANIFEST.json` 相符；受限刷写脚本再次核验相同结果。
- Manifest 的 `unexpected_changes` 为空。C29→C30 的差异限于替换诊断 helper/RC、`init.rc` 导入，以及相关 SELinux/file/property contexts。netd→Zygote 两条 callback 继续保持删除；primary Zygote critical、secondary callback、netd 内核版本检查、ART/runtime、GPU/EGL/Vulkan/HWC、Framework/SystemUI/BootAnimation、内核/fstab/加密没有变化。

## SELinux、canary 与 logger 静态门禁

- `c30_diag`、`c30_diag_exec`、init→helper domain transition 和 file context 均存在；C30 新增权限只针对诊断数据 type、所需属性、boot ID、logcat 可执行文件与 logd socket。无新增通用 `/proc` 读取或 broad coredomain grant；不依赖 shell domain 的新增宽泛权限。
- secilc policy version 35、neverallow enabled，退出码 0。此前过宽 `/proc` 读取确实被 neverallow 拦截，已移除；当前只保留读取 boot ID 所需的 `proc_random` 权限。
- helper 顺序为独立 `C30_CANARY_WRITE` → `C30_CANARY_FDATASYNC` → `C30_CANARY_APPEND`；失败时返回，不启动 watcher/logcat。每个 canary 有单独文件、错误码并通过 Android log 报告结果；init 独立写 post-fs-data/running/stopped markers。
- 通过 canary 后才创建 ordered events 和 logcat。logger 不使用 `-r/-n`，最多运行 60 秒、单文件上限 8 MiB并保留至少 2 MiB metadata 空间。`C30_LOGCAT_START` 经同步写入后才 fork/exec；记录 child PID、exec errno、stderr、waitpid、退出码/信号和 stop reason。
- 以上均为主机侧静态验证，canary/logger 尚无设备运行结果。

## Unified First-Response Standalone

run2 保持未改、未 RAM boot：201,326,592 bytes，SHA-256 `ab454793fbe595408b71a905ba176fe4a35e5c4c380439e5114e647a8ceb1dba`；随包 manifest 记录 kernel/ramdisk SHA，final ramdisk 检查已确认 pstore first、raw metadata、misc、独立 `standalone_dmesg.txt` 和 THYME_DIAG manifest 流程。它留待 C30 失败后的首次取证。

## Fastboot 预检、刷写和读回

唯一目标设备为 `thyme`，Bootloader Fastboot（`is-userspace=no`），A 槽、已解锁。

| 状态 | A：unbootable / successful / retry | B：unbootable / successful / retry |
|---|---|---|
| 刷写前 | no / no / 4 | no / no / 7 |
| 刷写后 | no / no / 4 | no / no / 7 |

依次写入：

1. `super`：10 个 sparse chunks 完成，Fastboot exit 0，`Finished. Total time: 204.512s`。
2. `vbmeta_system_a`：写入 OKAY，Fastboot exit 0，`Finished. Total time: 12.501s`。

Fastboot 对 sparse super 打印 `skip copying super image avb footer due to sparse image` 警告；随后 10/10 chunks、整体 `Finished` 且 exit 0。刷后唯一设备仍在线，product/slot/unlocked/userspace 与预检一致，A/B 启动状态全部未变。

完整 Fastboot transcript 仅保存在本机，因含设备标识未公开。

## 刷写工具说明

仓库原先没有 C30 专用刷写脚本，C29 脚本硬编码旧 manifest，不能用于 C30。本轮新增 `tools/flash_candidate30_diag_write_canary.ps1`：固定校验 C30 manifest 和精确差异集，只允许顺序写 `super`、`vbmeta_system_a`；执行前后检查 A/B 全部槽位变量；默认 dry-run；没有 reboot、set_active、erase 或其他写入代码。PowerShell parser 与 dry-run 通过后，使用该脚本完成本次受限刷写。

## 未验证与下一步

C30 的 runtime canaries、ordered events、logcat、Zygote/netd 顺序、system_server PID 和 critical escalation仍待真机验证。A 槽 retry=4。设备保持 Bootloader Fastboot；本轮不启动 C30，等待用户单独明确授权首次启动。