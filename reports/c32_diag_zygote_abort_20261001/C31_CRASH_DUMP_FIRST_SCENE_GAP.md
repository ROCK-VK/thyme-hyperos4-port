# C31 Zygote SIGABRT 第一现场与 crash_dump 留证缺口

更新时间：2026-10-01 18:16 HKT
判定：Result C；Zygote SIGABRT 已确认，abort reason 未知；本轮未构建或刷写 C32。

## 范围与边界

本轮只对 C31 已保存的 pstore、Standalone 主机副本、最终 C31 system tree、init 配置和合并 SELinux CIL 做定点离线核验。没有查询或操作手机，没有重启、刷写、set_active、擦除、metadata 写入或 PixelOS 恢复。没有修改 Candidate。

操作前检查的 C/D/E 可用空间分别约为 90.68、191.81、162.42 GiB，均高于项目 50 GiB 门槛；没有清理磁盘。没有访问或更改 Docker 资产。

## C31 第一条 main SIGABRT 时间线

来源是本机保存的 C31 Unified First-Response Standalone 副本；原始 pstore、raw metadata/misc 和设备记录没有公开。

| 顺序 | 记录 | 证据 |
|---|---|---|
| 1 | uptime 15.404966 秒 | console 的唯一 `THYME_C31DIAG event=zygote_start` 记录 primary Zygote PID 1059、secondary PID 1060、netd PID 1044。 |
| 2 | 21:56:21.627 | pmsg 中 PID 1059 记录 `UltraFrameworkComponentFactoryImpl` ClassNotFound。 |
| 3 | 21:56:21.943 | 同 PID 继续记录 `ThirdAppOptImpl has been initialized`。 |
| 4 | 21:56:22.230 | PID 1059 收到 `SIGABRT`；这是第一条 `main` SIGABRT，与初始 primary Zygote PID 直接匹配。 |
| 5 | 21:56:22.263 | 同 PID 随后记录 `crash_dump helper failed to exec, or was killed`，比 SIGABRT 晚约 33 ms。 |

ClassNotFound 与 SIGABRT 约相隔 603 ms；进程在两者之间继续输出初始化记录。没有 abort message、Java/native backtrace 或直接调用栈证明该异常导致 SIGABRT。

## SIGABRT 与进程数量

- pmsg 中共有 103 条 `main` SIGABRT，PID 均不同；首 PID 1059，末 PID 14027。这不是同一个 PID 重复发信号。
- 103 条 `netd` SIGABRT 也对应不同 PID（1044 至 14041）；另有 102 条 fingerprint HAL SIGSEGV（PID 1895 至 14068）。
- 只有首个 `main` PID 1059 能由 init marker 直接映射到 primary Zygote。缺少后续 init reap/service PID/state 记录，不能把 103 个 `main` PID 等同于 103 次 init Zygote 重启，也不能重建所有 secondary Zygote 与 netd 的触发顺序。
- 首个 netd crash 有完整 native DEBUG backtrace；说明同一 C31 runtime 中至少有一个 native crash 成功走过 tombstone 取证链。它不能证明 Zygote 使用该链时的进程上下文相同。

## crash_dump / debuggerd / tombstoned 路径核验

### 运行时资产的静态存在性

- C31 `com.android.runtime.apex` payload 中存在 `bin/crash_dump64`：ELF64/AArch64 PIE，567,904 字节，动态解释器为 `/system/bin/linker64`。
- 该 ELF 声明依赖 `libbase.so`、`liblog.so`、`libprocinfo.so`、`libunwindstack.so`、`libdl_android.so`、`libc++.so`、`libc.so`、`libm.so`、`libdl.so`。C31 system tree 中对应 system 库存在；`/system/bin/linker64`、`libc.so`、`libm.so` 与 `libdl*.so` 指向 runtime APEX。
- 这证明目标文件和静态依赖路径存在；没有设备运行时 linker namespace/dlopen 记录，因此不证明本次实际 exec 或动态解析成功。

### Init 与 SELinux

- 最终 C31 `tombstoned.rc` 定义 tombstoned 服务及 crash/intercept/java-trace sockets；second-stage init 配置在数据阶段启动 tombstoned。没有找到独立 init 常驻 `debuggerd` 服务声明。Android 的 fatal-signal 路径由 Bionic signal handler 启动 `crash_dump`，再由 crash_dump 联系 tombstoned；缺少 debuggerd 常驻服务本身不能解释失败。
- C31 合并 `plat_sepolicy.cil` 包含 `domain → crash_dump_exec` execute 规则、`domain + crash_dump_exec → crash_dump` type transition，以及禁止 `execute_no_trans` 的 neverallow。`crash_dump` 到 tombstoned crash socket、tombstoned service 和 tombstone 文件的相应规则存在。
- `crash_dump` 的 ptrace 规则目标属性由全部 domain 减去明确排除项组成，`zygote` 不在排除项内。静态策略没有显示 Zygote 无法进入 crash_dump 域或 crash_dump 无权 ptrace Zygote。
- 对 C31 console/pmsg 的定点搜索没有发现指向 crash_dump、tombstoned 或 debuggerd 的 SELinux AVC，也没有 SIGSYS/exec errno 记录。没有依据新增 SELinux allow。

## 103 条通用 helper 错误究竟证明什么

C31 对每一条 `main` SIGABRT 都保存了：

`Crash due to signal: crash_dump helper failed to exec, or was killed`

没有保存以下更具体分支：

- `failed to exec crash_dump helper: <errno>`；
- `crash_dump helper crashed or stopped`；
- `crash_dump helper reported failure`；
- IPC pipe read errno；
- waitpid errno / child status。

AOSP debuggerd signal-handler 实现将 pipe read 返回 EOF (`rc == 0`) 映射到这条通用消息。EOF 说明 helper 没有向父进程发送成功握手字节；它不能区分 `exec` 失败、helper 启动后提前退出或被杀。该源代码说明通用消息的语义，不证明当前 Xiaomi 二进制与上游逐字节相同。[AOSP debuggerd signal handler](https://android.googlesource.com/platform/system/core/%2B/refs/heads/main/debuggerd/handler/debuggerd_handler.cpp)

结合 crash_dump64、依赖路径、tombstoned 配置、静态 SELinux transition，以及 netd 的成功 backtrace，可以排除“系统里完全没有 crash_dump/tombstoned”这一粗略解释；仍不能确定 Zygote 专属调用上下文中的 exec、linker、ptrace 或 helper 生命周期哪个环节失败。C31 证据因此确认了**诊断链的握手缺口**，但没有确认具体失败原因。[AOSP crash_dump](https://android.googlesource.com/platform/system/core/%2B/master/debuggerd/crash_dump.cpp)

## no_fatal 与 PID1 panic 的边界

- C30 在约 uptime 32.922 秒出现 PID1 sysrq panic；C31 则保存到 uptime 527.837 秒，没有对应 sysrq/PID1 panic，同时出现 103 个不同 `main` PID 的 SIGABRT。
- 这一差分强烈支持 C31 的 `init.svc_debug.no_fatal.zygote=true` 诊断变量抑制了 critical escalation，从而把 Zygote SIGABRT 与快速 PID1 panic 分开。
- C31 预期的 `critical_gate` / property readback marker 没有保存，故没有直接确认运行时属性值，也没有捕获 init 的 reap/critical 计数/fatal target。严格结论仍是“强支持但未完全闭环”，不是 Zygote 修复成功。

## C32 决策与下一项单一实验

现有证据无法提供真实 abort reason。只追加普通 kmsg marker 不会弥补 helper EOF 缺少的 errno/exit 信息；直接改写 runtime APEX 中的 Bionic/crash_dump 会触及签名与可信启动链，现阶段没有安全、已验证的构建路径。因此本轮不构建或刷写一个无法得到 abort reason 的 C32。

下一项最有区分力的实验是一个**仅一次、非 critical 的 crash-dump canary**：在 tombstoned 已报告 running 后，由 init 启动一个 root、`zygote` SELinux domain、`oneshot` 的小型进程，以固定 abort message（例如 `THYME_C32_CANARY_ABORT`）主动崩溃一次。init 同时用独立内建 marker 记录 canary PID/start/stop，以及 `no_fatal.zygote` 设置后的读取值；候选 pstore 必须在 Standalone 其他操作前保存。

- 若 canary 也出现相同 pipe EOF：支持同一 SELinux/domain 启动路径的 helper 问题；再按该现场获取 exec/exit 证据。
- 若 canary 能生成带固定 abort message 的 tombstone：证明普通 `zygote` domain 的 crash_dump/tombstoned 路径可用；原 Zygote 失败更可能依赖其运行时状态，但仍需另一项能观测真实 Zygote helper exit 的诊断，不得据此归因 UltraFramework。

这个 canary 不复制真实 Zygote 的 ART 初始化、seccomp/namespace 与信号处理状态；通过只排除一部分全局/域级故障，不能当作真实 SIGABRT 的根因证据。实现前还需静态确认 init 对自定义 `seclabel` 服务的转换与启动阶段可行，并将 canary 设置为唯一一次、非 critical，避免循环。

## 本轮结论

1. Zygote SIGABRT 已证实；首个 PID 1059 与 primary Zygote marker 匹配。
2. 103 条 main SIGABRT 是 103 个 PID；不能据此声称 103 次 init service restart。
3. C31 没有保存任何 main abort message/backtrace；每次只保存到 helper handshake EOF 的通用提示。
4. crash_dump64、依赖路径、tombstoned service/socket 与必要静态 SELinux 规则存在；netd 的成功 backtrace 证明全局路径并非完全失效。真正的 Zygote-specific helper failure 仍未知。
5. no_fatal 对抑制 PID1 panic 有强差分支持，但运行时属性 readback/critical 分支证据缺失。
6. 本轮没有修改、构建、刷写或启动 C32；设备/槽位没有在本轮查询。最后保存的 C31 后状态为 A retry=2、unbootable=no；用户之后报告手动返回 Bootloader Fastboot。
7. 本轮为离线静态分析，不是 Candidate 实机验证。
