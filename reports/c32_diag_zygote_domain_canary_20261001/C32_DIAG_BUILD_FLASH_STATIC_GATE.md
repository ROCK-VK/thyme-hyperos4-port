# C32-DIAG 构建与静态门禁报告

## 目标与边界

C32 只用一个最小 native AArch64 进程，在现有 `zygote_exec` → `zygote` transition 下主动 SIGABRT，区分普通 zygote-domain native 进程的 crash dump 能力与真实 Zygote 的 ART/seccomp/namespace 等专属上下文。它不是正式修复。成功不证明真实 Zygote 的完整 dump 路径正常；失败也不单独证明 SELinux 是根因。

不直接 patch Xiaomi runtime APEX 的 linker64：C31 已有 ELF 中 handler 线索，但没有匹配其实际 build revision 的 Bionic/debuggerd 源码、Soong 树及可验证的 APEX payload/container 双签工作流。

## 静态可行性

- C31 已有 `zygote_exec` file type、`init -> zygote` type transition 和 init 执行权限：{'zygote_exec_context_exists': True, 'init_exec_transition_exists': True, 'new_selinux_allow_rules': False, 'service_seclabel_override': False, 'tombstoned_start_rc': 'system/etc/init/tombstoned.rc', 'tombstoned_start_in_main_init': True, 'tombstoned_status_context': 'init_service_status_prop', 'init_svc_debug_pid_context': 'init_svc_debug_prop prefix', 'runtime_domain_confirmation': 'successful tombstone SELinux label; no zygote /proc/self/attr/current read permission was found in the compiled C31 platform policy', 'C31_baseline_candidate': 'Candidate 31-DIAG primary Zygote critical escalation causal capture'}
- 没有增加 SELinux allow/CIL/property-context。C32 只在 `plat_file_contexts` 为新 canary 指向现有 `zygote_exec`，并在 EROFS mkfs file_contexts 输入增加同一最小文件映射。服务不写 `seclabel`，由 init 根据 entrypoint 文件类型执行现有 transition。
- C31 没有 zygote 对 `/proc/self/attr/current` 的明确读取权限，因此 canary 不尝试读取，以免为报告 domain 人为引入 AVC。真实标签由 crash tombstone 的 SELinux label 运行时字段确认；若没有 tombstone，则不能声称动态确认了实际 domain。

## 单次触发与进程生命周期

- tombstoned 的 service 定义存在；主 init 在 post-fs-data 先执行 `start tombstoned`。C31 启动序列随后触发 zygote-start，再到 boot。
- 触发采用 `on boot && property:init.svc.tombstoned=running`，只在 boot 事件的一次检查中执行；如果 tombstoned 当时没运行就不启动 canary，也不会在它稍后变化时重复启动。
- canary service 为 `disabled + oneshot`，没有 critical、onrestart、seclabel 或 restart。init 从 init.svc_debug_pid/state 事件写 `/dev/kmsg` lifecycle markers；C31 的 C30 logger和pstore路径保留用于持久日志。

## Canary ELF

- 输入 source SHA-256：`21020705F0D774772583333501FAF027A09554AEC359191308F90932AB7B19E3`；输出 ELF `7264` bytes，SHA-256 `EB9C3E903B32FEA514C299921E16A8E4D9E86833A0772E6EA9A3D82999F948CB`。
- AArch64 PIE，interpreter `/system/bin/linker64`，依赖 `libc.so, libdl.so, liblog.so`，NDK target API 30。进程尝试将 comm 设为 `main`，记录 PID 和预期 domain transition，设置固定 abort message `THYME_C32_CANARY_ABORT`，随后执行一次 `abort()`。
- 本地只完成目标 ELF 静态检查、system EROFS/AVB/LP 构建验证；没有在 ARM64 设备或模拟器实际运行 canary。

## C31→C32 变化

- 精确 system tree diff：`{'removed': [], 'added': ['system/bin/c32_zygote_canary'], 'modified': ['system/etc/init/hw/init.rc', 'system/etc/selinux/plat_file_contexts']}`。
- 没有改 runtime APEX/linker64、debuggerd、crash_dump、tombstoned、zygote service/critical、secondary callback、netd、ART、Framework、GPU/HWC/Vulkan、kernel、fstab、加密或 userdata/metadata。
- C32 system EROFS/fsck、最终文件 readback、ELF 字节一致性、system AVB verify、配套 vbmeta_system descriptor、LP repack/lpdump 和镜像 manifest 均由 BUILD_MANIFEST 记录。

## 最终静态门禁与实机刷写

- 成功构建来自 run3。`super.img` 为 7,703,595,992 bytes，SHA-256 `690658F64A7AA6DE254358DF9728C3085A5FB24D23BD5E94158F18A395A7B06B`；`vbmeta_system.img` 为 131,072 bytes，SHA-256 `FEEBAF0C5087CA4233B8BD5DA2F424C175840AEBB0ACEFE51D51E35743E65C01`。
- C31 runtime APEX 实际 `libc.so` 导出 `abort` 与 `android_set_abort_message`；C31 `liblog.so` 导出 `__android_log_write`。ELF 依赖为 `libc.so`、`libdl.so`、`liblog.so`。这是静态符号验证，不是 Android 设备执行验证。
- system EROFS/fsck、canary ELF/readback 字节一致性、system AVB footer verify、配套 `vbmeta_system` system descriptor、LP 重建/readback 与 C31 非 system 逻辑分区输入 hash 一致性通过。CIL/property contexts 与 C31 相同；未引入 SELinux allow。
- 受限脚本只向唯一 `thyme` 设备写入 `super` 和 `vbmeta_system_a`，两条 flash 命令均返回 0/`OKAY`。刷前后均为 A 槽、unlocked、非 userspace Fastboot；A `unbootable=no / successful=no / retry=2`，B `no/no/retry=7`，状态未改变。
- 设备仍停在 Bootloader Fastboot。没有执行 reboot、`set_active`、擦除或 Standalone 启动。Fastboot 写入成功不等于已进行设备分区 raw readback。
- 前两次主机构建在脚本门禁处失败，错误已修正；其 partial build output 保留在 run1/run2，没有写设备。有效镜像与报告来自 run3。

## 实机状态

C32 尚未启动，因此 canary 是否运行、是否处于 `u:r:zygote:s0`、是否产生固定 abort message/tombstone、crash_dump 与 tombstoned 是否成功，全部仍未知。须从后续 tombstone 的 SELinux label 确认运行时 domain；没有 tombstone 时不能声称已建立目标 domain。下一步等待用户明确说“开始启动 C32”。

## 构建器后续维护

构建与刷写完成后，修正了构建器的 `--preflight-only` 门禁：已有 run3 输出目录只阻止重新构建，不再阻止临时编译预检。该工具逻辑修正不改变 C32 源码树或已生成镜像；修正后 Ubuntu WSL 预检通过。最终镜像仍来自前述 run3，未重建或覆盖。

## 结果解释

Result A 需在设备运行后取得 canary PID、SIGABRT、固定 abort message、zygote SELinux label、backtrace/tombstone、crash_dump 与 tombstoned 成功、helper 无异常和相关 AVC 缺失。Result B 需 canary 确认位于 zygote domain 且仍复现 helper EOF；随后仍需定点区分域、exec、linker、helper、tombstoned 与实际上下文。Result C 为无法建立目标 domain，此时该实验无区分力。当前尚无运行结果。
