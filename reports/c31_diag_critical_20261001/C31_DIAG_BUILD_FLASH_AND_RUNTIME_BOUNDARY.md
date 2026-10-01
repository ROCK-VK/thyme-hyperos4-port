# C31-DIAG：primary Zygote critical escalation 因果诊断

日期：2026-10-01（HKT）
状态：已构建并刷入；仍停留 Bootloader Fastboot，尚未启动。
目的：只验证 C30 的 `main SIGABRT` 是否属于 init 管理的 Zygote，以及 primary Zygote 的 `critical` fatal escalation 是否触发 PID1 panic。

## C30 已知证据边界

- C30 pmsg 记录了五个 `main` 进程 SIGABRT，估算 uptime 为 16.095、18.014、22.855、27.842、32.879 秒；这些 PID 当时没有映射到 init 管理的 service。
- 最后一个 SIGABRT 约早于 PID1 在 32.921975 秒写 `sysrq-trigger` 43 ms。console 没有保存可确认的 `critical process 'zygote' exited 4 times` fatal 行，C30 的 ordered events/logger 文件也没有有效内容。
- C30 primary service 名为 `zygote`，配置仍为 `critical window=${zygote.critical_window.minute:-off} target=zygote-fatal`；本次实验前记录的展开值为 10 分钟。
- 因而 C30 只能支持“Zygote critical escalation 是强候选”，不能证明 `main` PID 就是 primary Zygote，也不能证明它造成了 PID1 panic。C30 AVC、UltraFramework fallback 和 netd SIGABRT 均未被本次改动处理。

## 当前 init 行为核验

- C30 实际 system tree 中 `/system/bin/init` SHA-256：`9BB24EAD728C13C50A5C734E6B3F951C83C7A81D86E2F973B1A1BD4FA9CAB020`。该二进制包含 `init.svc_debug.no_fatal.`、`init.svc_debug_pid.`、`critical process`、`exited with status` 和 `killed by signal` 字符串；这是二进制级静态证据，不能替代设备运行时验证。
- C30 service 定义中的实际 primary 名称为 `zygote`；`init.rc` 在早期导入对应 Zygote service 定义。C31 将 no-fatal 属性放在 primary `init.rc` 的 `early-init`，早于 `zygote-start`。
- Android 17 init 文档规定：critical service 在 fatal 窗口内退出超过四次，或在 boot complete 前退出超过四次，会走 fatal reboot target；文档提供 `init.svc_debug.no_fatal.<service-name>=true` 作为测试时跳过 fatal 的开关。该开关用于抑制 escalation，不会删除 service 的 `critical` 配置。[Android 17 init README](https://android.googlesource.com/platform/system/core/+/android17-release/init/README.md)
- 上游 init 的 service reap 路径在该属性为 true 时跳过设置 fatal target / `LOG(FATAL)` 的分支，之后仍进入 service restarting、执行原有 onrestart 并发布 restarting 状态。[AOSP init service.cpp](https://android.googlesource.com/platform/system/core/+/refs/heads/main/init/service.cpp)
- C30 策略已有 init 写 property、读取 service/PID property、写 `/dev/kmsg` 的权限；`secilc` 输入策略与 file/property contexts 均未改。C31 不增加 SELinux allow 或 property context。

## C30 → C31-DIAG 唯一源树差异

只修改 `system/etc/init/hw/init.rc`，没有新增或删除 system 文件。

1. 在 `early-init` 设置 `init.svc_debug.no_fatal.zygote=true`，并立即把属性值写入 `/dev/kmsg`，用于证明 gate action 到达且属性已设。
2. 在原有 `zygote-start` action 之后写一条 primary/secondary Zygote 与 netd 的状态/PID 初始快照。
3. 监听 primary Zygote、secondary Zygote、netd 状态，以及 `sys.boot_completed`、`sys.powerctl` 的属性变化；每次由 init 内建 `write` 写一条 `THYME_C31DIAG` 到 `/dev/kmsg`。kernel printk 时间戳提供本次 boot 时间轴。
4. 保留 init 原生 child reap 的 service/PID/exit-signal 日志作为退出状态来源；C31 marker 提供 init 的 service 名称、运行 PID 和 restarting 状态，以便与 pstore 中的 `main` PID/SIGABRT 对齐。C30 pstore 未留住足以完成该映射的 init 行，所以本次加入了这些低频 marker。

明确没有改：netd、Zygote/secondary service 定义及其 onrestart、critical 配置、SELinux/property contexts、framework、ART、GPU/Vulkan/HWC、内核、fstab、加密、userdata/metadata。没有删除 critical，没有重加 netd→Zygote callback，也没有改变 secondary→primary callback。

## 构建与静态门禁

- C30→C31-DIAG 文件树 diff：removed `[]`、added `[]`、modified 仅 `system/etc/init/hw/init.rc`。
- `python -m py_compile` 通过；构建器检测 C30 active init 中的 no-fatal/debug-PID 字符串，并核对原始 C30 init.rc SHA 与最终 EROFS readback。
- 对已编译 C30 platform policy 运行 `sesearch`：现有 init property set、service status/PID read、`kmsg_device` write 权限均存在；没有新策略规则。平台 CIL 和 property contexts readback SHA 与 C30 相同。
- system EROFS 重建、`fsck.erofs`、关键路径 EROFS readback 和 `avbtool verify_image` 通过。新系统数据区 root digest 为 `9e92218a437c4f30a606805748ed3160276b0f06de9657c0469643a3714cae1a`；system AVB descriptor 仅更新 system 数据，product/system_ext descriptor 保持原值。
- LP repack / `lpdump` 通过；重建输入中所有非 system logical partition SHA 与 C30 manifest 一致。boot、vendor_boot、dtbo、vbmeta 均从 C30 原样继承。
- 受限刷写脚本 PowerShell parser 与本地 Dry-Run 均通过；Dry-Run 只校验镜像，不查询或写设备。

## 镜像

| 文件 | 大小 | SHA-256 |
|---|---:|---|
| `system_c31_diag.img`（固定 system_a 分区镜像） | 1,092,616,192 B | `B06136D7652DB3BFDC742D36BB83A15832BB75E09018E39FAB57BCB0F4416D60` |
| `super.img` | 7,703,591,896 B | `B03611977936715F3DE10B93ECBDF7E55DF9BCC7E435D74EB26859B3BD33E29E` |
| `vbmeta_system.img`（写入目标 `vbmeta_system_a`） | 131,072 B | `79BE47B31F027FCA8A98FC8B81EEF5779058843BAEDF95B0FDADFA6A474DEE9E` |

## 受限刷写与当前设备状态

- Fastboot 唯一设备：序列号未写入本报告（原始 transcript 保存在本机）。刷写前后均为 `product=thyme`、`current-slot=a`、`unlocked=yes`、`is-userspace=no`。
- 仅刷入 `super` 和 `vbmeta_system_a`，两条 Fastboot 写入均返回成功。
- A 槽刷写前/后均为 `unbootable=no`、`successful=no`、`retry=3`。B 槽前/后均为 `unbootable=no`、`successful=no`、`retry=7`。
- 没有执行 `reboot`、`set_active`、erase、format 或 userdata/metadata 操作。当前仍处 Bootloader Fastboot。
- 设备运行结果尚未验证；`no_fatal.zygote` 是否在运行时生效、`main` PID 对应哪个 service、PID1 是否仍 panic 均待一次单独授权的 C31-DIAG 首启实验。

## 结果判定与下一步

本轮尚未证明或排除 Zygote critical escalation。若后续确认 gate marker 写入且 no-fatal 生效，同时 Zygote 仍重启而 PID1 不再以同路径 panic，则支持“critical escalation 是 panic 层原因”，但不代表 Zygote 的 SIGABRT 根因已修复。若 gate marker 缺失或 panic 仍出现，则按 pstore/native init reap 日志区分 gate 未生效与其他 fatal 路径。

设备现在保持 Fastboot，C31-DIAG 尚未启动；正式启动必须等待用户另行明确说“开始启动”。
