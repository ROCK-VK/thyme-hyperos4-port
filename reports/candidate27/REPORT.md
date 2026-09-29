# THYME-OS4：C26 Zygote 首因与 C27 试验决策

日期：2026-09-29（HKT）
状态：C26 离线因果链已收敛；C27 已构建并通过主机检查，但未刷写、未启动。

## 结论

C26 首次 Zygote 的短暂运行后停止，不再只是“原因未知”：持久 logcat 证明 init 对 Zygote 和 secondary Zygote 的进程组发送了 SIGKILL；实际 C26 `netd.rc` 又包含 `netd` 重启时重启两套 Zygote 的 `onrestart` 回调。时间顺序与该回调路径吻合。最有证据支持的解释是：`netd` 因 Android 25Q2+ 检查拒绝 Linux 4.19 而 SIGABRT，init 重启 `netd` 时执行回调，继而杀掉两套 Zygote。

日志没有保留 Zygote 的 waitpid 状态或最终退出码，因此“init 发出 SIGKILL”是直接观测事实，“该 SIGKILL 完成了第一次 Zygote 的退出”由紧邻的服务状态转换和 init 配置强力支持，但内核层最终退出状态仍未知。C27 删除的正是这两条反向回调；它保留 netd 的兼容性检查及崩溃行为，目标是让 Zygote/SystemServer 不再随 netd 重启而被终止。网络功能仍可能不可用。

## C26 首次启动时间线

日志有两套时钟：logcat 前缀为 monotonic；诊断 helper 字段为 `CLOCK_BOOTTIME`，两者在该窗口约差 1.064 秒。下面分别标明，避免把两个数值当成同一个 uptime。

| logcat monotonic | helper BOOTTIME / 事件 |
|---|---|
| 14.362 s | 15.426 s：Zygote PID 1060 状态变为 running；`/proc` 显示 `/system/bin/app_process64 ... --zygote --start-system-server`。 |
| 14.368 s | 15.430 s：secondary Zygote PID 1061 状态变为 running；`/proc` 显示 `app_process32 ... --zygote_secondary`。 |
| 14.408 s | netd PID 1046 开始运行。 |
| 14.409 s | `libnetd_updatable_init: Failed: 25Q2+ platform with kernel version < 5.4.0 is unsupported`，随后 netd 收到 SIGABRT。 |
| 14.489–14.494 s | crash_dump/tombstoned 为 netd 写出 `tombstone_00`；tombstone 标注 `ZygotePid: -1`，崩溃进程明确是 `/system/bin/netd`，不是 Zygote。 |
| 14.503–14.509 s | PID 1 的 libc 记录向 `-1060` 和 `-1061` 发送 signal 9；负 PID 表示进程组。日志对同一目标有重复发送记录。 |
| 14.510 s | helper BOOTTIME 15.573 s：`init.svc.zygote running -> stopping`。 |
| 14.514 s | helper BOOTTIME 15.578 s：`init.svc.zygote_secondary running -> stopping`。 |
| 14.515 s | helper BOOTTIME 15.579 s：`init.svc.netd running -> restarting`。 |
| 16.762 / 16.811 s | 两个 Zygote 服务进入 restarting；随后开始重复循环。 |

PID 1 的 signal 9 记录明确表明它发出了进程组终止请求；C26 没有保存 Zygote 的 SIGCHLD/waitpid 原始退出状态。结论不是“Zygote 自身 SIGABRT/SIGSEGV”，而是“存在紧邻 netd 重启的 init SIGKILL 请求，并与 `netd.rc` 回调匹配”。

## fatal、访问拒绝与 tombstone 归属

- 确认的 native fatal/tombstone 属于 netd，调用栈位于 `libnetd_updatable.so` 与 `/system/bin/netd`。
- 没有找到可归属 Zygote 的 tombstone、Java `FATAL EXCEPTION`、ART/linker fatal、seccomp、OOM 或内核 Oops/panic 证据。
- 窗口内确有 SELinux AVC：linkerconfig/aconfigd 等读取 vendor property 被拒；C26 helper 在 shell 域读取 `init.svc_debug_pid.zygote*` 也被拒。它们没有显示 Zygote 执行被拒或被 SELinux 杀死，不能当作 Zygote 首退原因。
- netd tombstone 的 `ZygotePid: -1` 不表示 Zygote 崩溃，也不能把 netd tombstone 归到 Zygote。

## C26 logcat 约 52 秒停止

C26 logger 在 BOOTTIME 约 15.297 s 启动，最后一条保存记录约 50.959 s，`init.svc.c26_logcat` 于约 52.027 s 变为 stopped。服务为 oneshot，调用带 `-r`/`-n` 的轮转式 logcat；同一输出目录存在 shell 域 `{ remove_name }` AVC。轮转需要管理旧输出，故 SELinux 拒绝目录删除是最符合现有证据的解释，但没有捕获 logcat 子进程退出码/标准错误，不能写成已证明的直接退出原因。

C27 改成 helper 监管的单一日志文件，不轮转、不删除旧文件；以 pipe 持续排空 logcat，即使达到字节上限也继续读取直至子进程退出，避免写满 pipe 导致状态采集死锁。状态文件记录子进程退出码、信号、stderr、耗时、输出字节、容量上限和停止原因。限时 8 分钟；输出容量取 metadata 当前可用空间减 12 MiB、最高 24 MiB，预留 C25 sampler、C27 event/tail 与额外空间。该容量字段现已修正为与 C27 helper 实际编译常量一致。

## K40 OS4.0.0.8 定点对照

- 指定的 Redmi K40 成功包与 C26 的 `netd`、`netd.rc` 完全相同；`com.android.tethering.capex` 也逐字节相同。因此替换这些文件没有依据。
- K40 包内 boot 镜像可提取到 `Linux version 4.19.325-cip135-st19-aptusitu-perf-ga8adb96703d6` 字符串。这只是包内 kernel 字符串，不是 K40 成功运行时的 `uname` 证据。
- 两边同属 SDK 37/vendor API 30。K40 `netbpfload.rc` 使用默认 bpfloader 加载/等待路径；C26 继承此前针对 4.19 的 BPF bypass。此差异直接涉及 BPF 启动路径，但尚不能解释 K40 是否运行同一内核，也不能证明它绕过了 netd 的 25Q2 检查。
- 现有 K40 资料没有可核验的运行时 netd 日志或 uname。K40 成功启动与包内 4.19 字符串、相同 tethering APEX、相同 netd callback 之间仍有未解差异；不猜测填补。C27 修复依据来自本机 C26 的时间线与实际 init 配置，不声称复用了 K40 的 netd 修复。

Android init 的 `Service::Reap()` 在服务退出后执行 `onrestart` 命令，再将状态通知为 restarting；可对照 [AOSP init/service.cpp](https://android.googlesource.com/platform/system/core/+/c52b3c08fa5ea3680ffcd68c2a1d0542d09f0509/init/service.cpp)。本机 netd 配置与这条机制相符。

## C27 改动与主机验证

以 C26 已刷版本为基线，只作与已见故障链直接对应的改动：

1. 从 system `netd.rc` 移除 `onrestart restart zygote` 和 `onrestart restart zygote_secondary`。保留 netd 的 25Q2/Linux 4.19 检查和 netd 自身重启；不改 kernel、ART、SELinux、图形、fstab、加密或硬件栈。
2. 替换 C26 轮转 logger 为上述单文件、有界、受监管 logger；保留 Zygote/netd 状态 watcher 和 C25 sampler，不读取此前被 AVC 拒绝的 debug PID 属性。

构建目录：`work/stage_c27_netd_zygote_cycle_break_20260929_run1/images/`。构建脚本生成 EROFS readback、AVB、LP/Super 和输入哈希检查；helper 为 AArch64 PIE，编译 `-Wall -Wextra -Werror` 通过；刷写脚本语法检查通过。受限脚本 Dry-Run 已通过，只计划顺序刷写 `super`、`vbmeta_system_a`，无清数据、切槽、misc/BCB、回锁或重启操作。

| 分区目标 | 镜像大小 | SHA-256 |
|---|---:|---|
| `super` | 7,703,595,992 bytes | `2B7A2F055B55AFB0B52B3DEAE9B7963F7923F075D406449F0C5034B5E7236598` |
| `vbmeta_system_a` | 131,072 bytes | `19B1ECD7128874989792C1B3F5173E6F4A8D2E0AC08734D35338AFAD674FA881` |

C27 仍是待验证实验，不表示 Zygote/SystemServer 已修复，也不保证网络服务工作。若后续刷写成功，首次启动前必须单独处理 A 槽启动预算；不得自动执行 `set_active a`。

## 设备和下一步

- C26 最近一次可信只读槽位记录：A `unbootable=no / successful=no / retry=1`，B retry=7；本轮未执行任何 A/B 元数据操作。当前主机 `fastboot devices -l` 无设备输出，故不能确认现在仍处 Bootloader Fastboot，也不能刷入 C27。
- 最后确认已刷版本为 C26；C27 尚未刷写/启动，设备当前分区状态未能重新确认。
- 下一步：恢复唯一 thyme Bootloader Fastboot 的主机枚举后，再以只读查询确认 product、A 槽、unlocked、is-userspace 和当前 retry；只有状态通过后才执行限定 C27 写入。刷写完成保持 Fastboot。C27 首启前单独申请 A 槽预算恢复授权，且另等用户现场启动确认。
- 本轮没有启动手机、运行 Standalone、执行 `fastboot set_active a`、擦除 userdata/metadata、修改 misc/BCB、恢复 PixelOS 或触碰 Docker。
