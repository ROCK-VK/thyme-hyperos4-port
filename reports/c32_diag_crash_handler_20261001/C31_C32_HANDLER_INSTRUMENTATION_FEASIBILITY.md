# C31→C32 debuggerd/crash_dump 直接仪表化可行性

更新时间：2026-10-01 20:19 HKT
判定：**Result C**。已核对 C31 实际处理 SIGABRT 的编译产物；现有工作区缺少可证明匹配该产物的 Bionic/debuggerd 源码与可复现的 runtime APEX 构建、签名流程。没有生成、刷写或启动 C32。

## 结论摘要

C31 的第一条 `main SIGABRT` 确认为 primary Zygote PID 1059。pmsg 在信号后约 33 ms 只留下 crash_dump helper 握手 EOF 的通用记录；没有 abort message/backtrace、fork/exec errno、helper PID/退出状态、tombstoned 请求结果。实际 `linker64` 中包含 debuggerd signal-handler 符号和该通用消息，但这只能确认代码路径在产物中，不能从 ELF 推导本次执行落入哪个分支。

直接加诊断需要重建 C31 使用的 runtime APEX：handler 是静态链接进 runtime APEX 的 `linker64`，不是可单独替换的普通系统库。本地没有 C31 对应的完整平台源码/Soong 构建树、源码 revision 证明或经过验证的 runtime APEX 双重重签流程。拿当前 AOSP 上游重新编译再替换，不能保证与 Xiaomi 的 C31 ABI、编译配置及分支完全对应；直接二进制补丁也没有可复现的语义/签名验证流程。对早期动态 linker 冒险打补丁不构成可靠诊断。因此本轮不构建“看似直接、实际无法验证”的 C32。

下一项唯一建议的隔离实验是：在 C31 的 `no_fatal.zygote` 基线上，静态验证后增加**一次性、非 critical、明确运行于 `zygote` SELinux domain 的固定 SIGABRT canary**，并由 init 独立写 start/PID/stop marker；仅在 tombstoned 已运行后触发。它不是普通 shell 测试，也不冒充 primary Zygote 首因；只用于判断相同 Bionic handler、crash_dump 与 zygote domain 的通用路径是否能握手并生成 tombstone。若 canary 成功，仍需查真实 Zygote 特有的 ART/seccomp/namespace/进程状态；若失败，再决定如何取得可匹配源码并做 handler 级直接仪表化。

## C31 启动现场：Zygote 崩溃与 PID1 escalation 分开

- init marker 在 uptime 15.404966 秒记录 primary Zygote PID 1059、secondary PID 1060、netd PID 1044。
- 首个 `main SIGABRT` PID 1059，与 primary marker 相同。其前约 603 ms 曾记录 `UltraFrameworkComponentFactoryImpl` ClassNotFound；同 PID 随后仍有初始化日志。没有 abort message/backtrace，不足以把该异常判为 SIGABRT 根因。
- 约 8 分 59 秒的启动取证窗口内有 103 条不同 PID 的 `main SIGABRT`。缺少其余 PID 对应的 init reap/service PID/state 记录，不能将 103 个 PID 说成 103 次 primary Zygote service 重启，也不能判定其为普通 fork 生命周期。
- 同一窗口另有 103 个不同 PID 的 netd SIGABRT 和 102 个 fingerprint HAL SIGSEGV。没有一对一映射证据；目前按三个分别观察到的 crash 序列处理，fingerprint 仍是独立候选，不能用数量推导因果。
- C30 在 uptime 约 32.922 秒留下 PID1 sysrq panic；C31 保存至 uptime 527.837 秒，没有该 panic，同时有大量 main SIGABRT。该差分**强烈支持** C31 的 `init.svc_debug.no_fatal.zygote=true` 将 Zygote SIGABRT 与 PID1 critical escalation 分开，但 C31 没有 runtime property readback 或 critical 分支实际读取 marker，故仍不是直接闭环。

首个 primary PID 局部时间线（来自前次已完成的 pmsg/console 定点复核）：

| 时间 | PID/来源 | 事件 |
|---|---|---|
| uptime 15.404966 s | init marker | primary Zygote 1059、secondary 1060、netd 1044 |
| 21:56:21.627 | PID 1059 | `UltraFrameworkComponentFactoryImpl` ClassNotFound |
| 21:56:21.943 | PID 1059 | 后续初始化记录 `ThirdAppOptImpl has been initialized` |
| 21:56:22.230 | PID 1059 | 首个 `main SIGABRT` |
| 21:56:22.263 | PID 1059 | 通用 crash_dump helper EOF 文案，晚约 33 ms |

缺少 abort message/backtrace；PID 1059 在 ClassNotFound 后仍继续初始化，因此该类缺失不能由这段时间线单独判为 SIGABRT 根因。此处的主要结论是 helper 的 generic EOF 留证，不是 abort 首因。

## 实际编译产物与源码对应性

检查对象是 C31 system tree 的 `/system/bin/linker64` 实际目标文件及其 runtime APEX。C31 `system/bin/linker64` 是指向 `/apex/com.android.runtime/bin/linker64` 的链接。

| 项目 | C31 实际值 |
|---|---|
| `com.android.runtime.apex` | 12,996,608 bytes；SHA-256 `45A073DD1ED7F8447C99E3360D989489AAA3A3573BF2913C284BC9C83D36E595` |
| C30 runtime APEX | SHA-256 相同；本实验未对其重建 |
| payload `linker64` | ELF64 AArch64 shared object，未剥离符号 |
| `linker64` SHA-256 | `00E5DC0E9716F6E7C6D70E04FA7A721941C02E912932EB5C08753676DA0ADB50` |
| ELF Build ID | `d8fc879ba0f57538f2e66cd324ffa7a3` |
| handler 符号 | 本地隐藏符号 `__dl__ZL24debuggerd_signal_handleriP7siginfoPv.llvm.4997513501078024436`，地址 `0x11069c`、大小 2684 bytes |
| 产物字符串 | 含 `crash_dump helper failed to exec, or was killed`、exec errno、pipe read error、waitpid error、helper crashed/stopped 等 handler 诊断分支文本 |

本地项目提供了 thyme kernel source 与 Candidate system-tree 构建脚本，但在检查过的项目及 C31 build root 中没有对应 `debuggerd_handler.cpp`、Bionic/debuggerd Soong 源树或该 APEX 的可复现构建目标。AOSP `ApexBuildInfo` schema列出 apexer 命令、文件配置、原始 manifest 与 SDK 参数等字段，没有 source revision 字段；因此该元数据不能为 C31 exact source commit 提供证明。[AOSP ApexBuildInfo schema](https://android.googlesource.com/platform/system/apex/%2B/df4f5e904d8c552501984e6ec9780d04e0449a88/proto/apex_build_info.proto) 报告只确认**实际 ELF 中有 handler 符号与分支字符串**，不声称已证明 Xiaomi 二进制逐行来自某个 AOSP revision。

## Handler 阶段：本地日志能证明什么

本地 C31 日志每次保留的都是：

`Crash due to signal: crash_dump helper failed to exec, or was killed`

在 Android 17 AOSP 参考实现里，fatal handler fork 子进程并 `execle()` crash_dump；父进程读握手管道。读到 0 字节会输出这条通用消息；读错误、exec 失败等其他分支有不同信息。之后会 `waitpid()`，但常见实现只打印 waitpid 错误或 helper stopped/signaled，不输出普通 `WIFEXITED` 的退出码。因此 EOF 本身只说明父进程没有收到成功握手字节；不能区分 exec 失败、helper 启动后退出或被终止。上游源码用于说明这种机制，不代表 C31 Xiaomi 二进制源代码完全相同。[AOSP debuggerd handler](https://android.googlesource.com/platform/system/core/%2B/refs/heads/main/debuggerd/handler/debuggerd_handler.cpp)

| 请求字段 | C31 证据 | 判定 |
|---|---|---|
| SIGABRT / primary PID | 首个 `main` PID 1059，匹配 init marker | 已确认 |
| abort message / backtrace | pmsg 无 | 未取得；SIGABRT 首因未知 |
| handler fork PID/返回/errno | 未记录 | 未知 |
| `execle()` errno | 无 exec-failure errno 文本 | 未知；不能由 EOF 猜 errno |
| pipe read `rc` / marker | 通用消息与 AOSP rc=0 分支一致 | 支持 EOF；C31 分支本身没有直接数值记录 |
| crash_dump PID / signal / raw wait status | 未记录 | 未知；不能声称 helper 被 SIGKILL |
| crash_dump 是否进入、ptrace 是否开始 | 无针对 Zygote 的记录 | 未知 |
| tombstoned 是否收到 Zygote 请求 | 无请求结果；无对应 AVC | 未知 |
| SELinux | 静态 transition/access 规则存在；目标日志未见 crash_dump/tombstoned AVC | 没有直接 SELinux 阻塞证据，不加 allow |

同一次 C31 运行中，netd 有 native tombstone，说明 dump 链并非全局不可用；它不证明 Zygote 上下文能成功使用相同链。缺少 Zygote 的 helper PID/status 和 tombstoned 事件，不能把失败点推进到任何单一阶段。

## 原计划中的 C31→C32 精确差异

若匹配源码和可复现构建链可用，C32-DIAG 应只在 C31 基线上增加真实 handler 留证：

1. handler 记录 crashing PID/TID、fork 返回值/errno 和 crash_dump child PID；
2. child 在 `execle()` 失败时通过**独立、固定大小、尽量只用 async-signal-safe syscall 的诊断通道**报告 errno，不改原有握手 pipe；
3. parent 记录原握手 read 返回值及 marker、waitpid 返回/raw status 与 exited/signaled/stopped 分类；
4. 只有能证明 `crash_dump64` 已进入但握手仍无结果时，才对其 tombstoned connect/request/output-fd/ptrace 阶段增加小量 marker；
5. 保留 C31 的 `no_fatal.zygote` 与 init 诊断 marker。kernel、SELinux、netd、Zygote critical/onrestart、ART、framework、图形和设备数据行为全部保持不变；不删除任何现有内容。

这些是目标差异，不是本轮已完成改动。handler 位于 Bionic signal-handler 路径，新增日志必须避开 stdio、malloc、pthread 等不适用的操作；应先以匹配源码构建和验证，再考虑镜像集成。

## 为什么本轮不做 handler 级 C32

1. 目标 handler 被静态链接进 runtime APEX 的 `linker64`。AOSP Android 17 当前源码也将 handler core 编入 dynamic linker，但这一结构相似性不能代替 C31 exact source provenance。[AOSP debuggerd Android.bp](https://android.googlesource.com/platform/system/core/%2B/refs/heads/main/debuggerd/Android.bp)
2. 已检出的 C31 工程没有匹配的 Android platform/Bionic 源码、Soong 输出或 source revision 元数据。直接以公开上游分支构建会引入未验证的代码版本差异。
3. 改 APEX 至少涉及 payload AVB 签名和容器 APK 签名；Android 文档要求这两层分别签名，payload 公钥标识也必须能在设备验证链中匹配。[AOSP APEX format/signing](https://source.android.com/docs/core/ota/apex) 当前项目没有已验证的 C31 runtime APEX 改包、双重签名、集成及启动检查流程。检查 build root 未发现相应 APEX 私钥/签名资产；这不表示已全面搜查或证明主机任何位置都不存在私钥。
4. 直接改写早期启动所需的 dynamic linker 二进制，既绕过源码构建，又会改变 signal-handler 行为；目前没有可靠的差分证明或安全验证链。

所以“技术上从零重建可能可研究”不等于“本轮可可靠生成并验证 C32”。没有 C32 patch、build、flash 或 reboot。

## 下一项单一隔离实验

直接 handler 仪表化当前不具备可靠构建条件后，下一步只建议一个非修复诊断：

1. 静态确认 C31 init 对显式 `zygote` domain `seclabel` service 的 transition、可执行文件 type、SELinux 规则和触发顺序。
2. 建立一个 init 启动、`oneshot`、非 `critical` 的小型 native canary；等待 `init.svc.tombstoned=running` 后仅触发一次固定 SIGABRT。它使用 C31 自带的 Bionic handler、runtime APEX、crash_dump64 和 zygote domain。
3. init 在 `/dev/kmsg` 独立记录 canary start/PID/stop；canary 不负责把自身错误写入 userdata/metadata。故障后第一次 Unified First-Response Standalone 先保存 pstore，再保存 metadata/misc/THYME_DIAG。
4. 成功产生固定 abort-message tombstone：一般 zygote-domain dump 路径可用，原始 Zygote 的 ART/seccomp/namespace/进程状态成为差异焦点。仍然不能据此推断 `UltraFrameworkComponentFactoryImpl`。
5. 同样只有 EOF：问题更可能位于通用 zygote-domain handler/helper 路径，但仍不能得到真实 Zygote abort 首因；此后要先取得精确 runtime 源码/可复现 APEX 构建链，再做直接仪表化。

此 canary 不是普通 shell crash 测试，也不复现真实 Zygote 上下文。它是目前唯一建议的下一项隔离实验；本轮未实现或运行它。C31 的 `no_fatal.zygote` 保留为既有诊断变量，不与 canary 结果混写成行为修复。

## Candidate 决策、安全与未完成项

- 结果：Result C。C31 的第一条 SIGABRT 首现场已映射到 primary Zygote；实际 handler ELF 已识别；直接 handler 仪表化在当前源码/构建/签名资产下无法可靠完成。
- C32：未生成；没有 `C31→C32` system diff、镜像、manifest 或 flash dry-run。
- 正式修复：无。当前真正的 Android 阻塞仍是 primary Zygote SIGABRT 的首因未知；之后的 crash_dump 握手失败只阻断取证，不足以解释 SIGABRT 本身。
- PID1：C31 不再出现 C30 的 panic 强烈支持 `no_fatal.zygote` 隔离 critical escalation，但运行时 property/branch readback 缺失。它回答的是“Zygote crash 后是否拖到 PID1 panic”，不回答“Zygote 为什么崩”。
- 设备：本轮未查询或操作设备。最新可用历史状态仍是 A retry=2/unbootable=no、B retry=7/unbootable=no；不得视作当前实时状态。没有 Candidate reboot、刷写、`set_active`、擦除、metadata 写入或 PixelOS 恢复。
- 磁盘：本轮检查 C/D/E 约 90.66/191.83/161.25 GiB 可用，均高于 50 GiB 门槛；未清理，Docker 未触碰。
- 原始证据：本机 C31 Unified First-Response Standalone 副本未修改；本报告公开版本不含 pstore/raw metadata/misc、ROM/APEX 二进制、私钥、设备序列号或原始主机 transcript。

## 验证范围

这是对本地 C31 ELF/APEX、system-tree 链接、前次保存的 pmsg/console、Candidate 构建脚本和可用源树的静态核验；没有修改 Candidate 代码、构建产物或设备。未做 runtime 仪表化、刷写或启动验证。Android AOSP 链接只支撑上游机制/签名要求，不能替代对 Xiaomi C31 exact source 的证明。
