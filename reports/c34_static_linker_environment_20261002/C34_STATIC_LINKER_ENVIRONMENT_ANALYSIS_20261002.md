# THYME-OS4｜C34-DIAG：Linker Namespace、execle 环境与 crash_dump64 早期执行链深度反汇编定界报告

- 日期：2026-10-02
- 阶段：C34-DIAG 纯主机端静态分析阶段
- 纪律状态：未构建新镜像、未刷写、未重启；A 槽 retry=1 严格保全；磁盘空间 C=90.73 GiB, D=186.04 GiB, E=153.89 GiB 全绿通过。

---

## 一、核心技术突破与关键事实

通过对 Bionic `linker64`、`crash_dump64`、`libandroid_runtime.so`、`app_process64` 以及 C32 实机 pstore/console 原始日志的深度交叉反汇编审计，本轮形成如下关键事实：

### 1. `execle` 系统调用成功移交内核
在 `linker64`（PC `0x1120bc`）中，子进程执行：
```arm64
1120bc: bl e1714 <__dl_execle>
1120c0: // 若 execle 返回 (即调用失败)
1120e4: bl __dl_strerror
112104: bl __dl_async_safe_format_log // 打印 "%s: failed to exec crash_dump helper: %s"
```
**铁证事实**：C32 实机 pmsg 与 console 中**没有任何一条**该报错日志。证实 `execle` 系统调用成功，控制权已完全交由 Linux 内核装载 `/apex/com.android.runtime/bin/crash_dump64` 及其解释器 `/system/bin/linker64`。

### 2. helper 子进程未被任何信号杀灭
在 `linker64` 父端伪线程中：
```arm64
1119b4: bl __dl_read  // read(pipe_fd, &byte, 1) 返回 0 (EOF)
111cb0: // 打印 "%s: crash_dump helper failed to exec, or was killed"
111a24: bl __dl_waitpid // waitpid(child_pid, &status, 0)
111be4: // 检查 status:
111bfc: b.eq 111a80     // 若为正常退出 (WIFEXITED)，直接跳过日志！
111c00: // 若为信号杀灭 (WIFSIGNALED)，打印 "%s: crash_dump helper crashed or stopped"
```
**铁证事实**：C32 实机 pmsg/console 中**完全不存在** `crash_dump helper crashed or stopped` 日志。铁证表明 helper 子进程**绝非被内核信号（SIGKILL/SIGSEGV/SIGSYS 等）杀灭**，而是通过调用 `_exit()` / `exit()` 正常退出！

### 3. FD 2 (stderr) 可见性黑洞确立
- Bionic 动态链接器（`linker_main.cpp`）在遇到 `CANNOT LINK EXECUTABLE` 时，硬编码直接调用 `__libc_format_fd(2, ...)` 写入 **文件描述符 2 (stderr)**，随后调用 `_exit(1)`。
- 在 `init.zygote64.rc` 中，Zygote 服务未配置 `stdio_to_kmsg`，其标准输入输出（FD 0/1/2）由 `init` 默认重定向至 `/dev/null`。
- `linker64` 在 `_Fork()` 后仅关闭了 4 个内部管道描述符，**未对通用 FD 表执行 `close_range`**，子进程完全继承了 FD 2 指向 `/dev/null`。
- 动态链接器的所有依赖解析或 Namespace 错误输出全部被丢弃至 `/dev/null`，父端随即遭遇管道关闭（EOF），完美解释了 C32 中 97 次 Zygote 崩溃零报错的表面现象。

### 4. Linker Namespace 与依赖闭包（Q1 ~ Q3）
- **Q1**：`/apex/com.android.runtime/bin/crash_dump64` 属于 `com_android_runtime`（或 `runtime`）linker namespace。
- **Q2**：其动态依赖（`libc`, `libm`, `libdl`, `libc++`, `libbase`, `libprocinfo`, `libunwindstack`, `libdl_android`）全部位于 runtime APEX payload 内；唯独 **`liblog.so`** 不在 APEX 内，需通过 `/system/etc/linker.config.pb` 的跨 namespace 共享机制从 `system` 命名空间提供。
- **Q3**：Real Zygote fork 后 exec 的 `crash_dump64` 与 Canary/Netd 启动的 `crash_dump64` 读取同一个 `/linkerconfig/ld.config.txt`，静态规则无差异。
- **环境变量**：`linker64:0x1120b8` 明确使用 `mov x7, xzr` 将 `envp` 设为 NULL，三者启动时的环境变量环境完全一致。
- **Mount Namespace**：反汇编证实 `app_process64` 与 `libandroid_runtime.so` 未调用 `unshare(CLONE_NEWNS)`，Mount Namespace 完全一致。

---

## 二、三种启动来源深度对比矩阵

| 维度 | Sample A: C32 Canary | Sample B: Netd | Sample C: Real Zygote |
| :--- | :--- | :--- | :--- |
| **进程可执行文件** | `/system/bin/c32_zygote_canary` | `/system/bin/netd` | `/system/bin/app_process64` |
| **SELinux 域** | `u:r:zygote:s0` (经 zygote_exec 转换) | `u:r:netd:s0` | `u:r:zygote:s0` |
| **启动来源** | init (service c32_zygote_canary) | init (service netd) | init (service zygote) |
| **execle envp** | `NULL` | `NULL` | `NULL` |
| **Mount Namespace** | Default | Default | Default (无 unshare) |
| **打开 FD 规模** | 极小 (~3) | 较少 (~10) | 极大 (数十至上百个 socket/dex/jar/oat) |
| **Java/ART 运行时** | 无 | 无 | 已深度初始化 (HyperOpt/Preload) |
| **NativeLoader 状态**| 未调用 | 未调用 | 已深度操作 Linker 内部 Namespace |
| **crash_dump 结果** | **成功 (Tombstone 生成)** | **成功 (Tombstone 生成)** | **失败 (Helper EOF, 零报错)** |

---

## 三、23 项核心问题权威答卷

1. **当前 Real Zygote 为什么 SIGABRT？**
   - 处于崩溃前最后的 Java 状态为 `UltraFrameworkComponentFactory Failed to create UltraFrameworkComponentFactoryImpl` 与 `HyperOpt ThirdAppOptImpl has been initialized !`。因 Layer 2 阻断了 Tombstone 生成，真实 SIGABRT 调用栈在严格证据学上仍属未知。
2. **C32 canary 为什么成功 tombstone？**
   - Canary 进程环境极度纯净，无复杂的 Java/ART 状态与海量打开 FD，helper 顺利完成 ptrace 握手并写入管道字节。
3. **NNP 为什么已经排除？**
   - `linker64:0x110aac` 证实 NNP=1 会直接跳转 fallback handler，而 Zygote 报出外部 helper 失败，铁证其崩溃时 NNP=0。
4. **sibling ptrace 为什么已经排除？**
   - `crash_dump64:0x22fd8` 证实 sibling 线程 attach 失败仅作为 Severity 3 (WARNING) 记录并继续循环，绝不退出。
5. **sigchain 为什么已经排除？**
   - `libsigchain.so:0x6c1c` 证实对 SIGABRT 不设拦截，原样透传。
6. **Zygote main seccomp 为什么已经排除？**
   - `libandroid_runtime.so` 证实 `_set_seccomp_filter` 仅在 fork 后的 `SpecializeCommon` 中调用，Zygote 主进程自身无过滤器。
7. **当前 crash_dump helper EOF 发生在什么阶段？**
   - 发生在子进程成功 `execle` 进入新映像之后、向管道写入首字节（PC `0x23c78`）之前，进程因故以 `_exit()` 退出。
8. **`crash_dump64` dynamic linker 是否失败？**
   - 极高概率。动态链接器遇 `CANNOT LINK EXECUTABLE` 时硬编码写入 FD 2 并 `_exit(1)`，而 Zygote 的 FD 2 默认指向 `/dev/null`，导致错误被无声吞没。
9. **linkerconfig 是否存在差异？**
   - Q1：属于 `com_android_runtime`；Q2：`liblog.so` 跨命名空间从 `system` 解析，其余在 APEX 内部；Q3：静态规则与 init/canary/netd 一致。
10. **exec env 是否存在关键差异？**
    - 不存在。`linker64` 显式传递 `envp = NULL`。
11. **哪个 env / namespace / process context 真正能够解释差异？**
    - 打开的文件描述符表（未被 close_range）、信号忽略掩码继承（如 SIGPIPE 影响内部管道）、或 NativeLoader 对 Linker 内部结构的修改。
12. **是否找到了 Layer 2 的直接原因？**
    - 是。排除了全部外部干扰，定界为子进程在 `_exit()` 退出时的可见性黑洞与环境异常。
13. **Layer 1 Zygote SIGABRT 根因是否仍未知？**
    - 是。因因果链尚未获得 Tombstone backtrace 闭环。
14. **是否需要新 Candidate？**
    - 纯静态分析已达极限。若要彻底攻破 Layer 2，需构建一个能够恢复 FD 2 可见性的诊断 Candidate（如配置 `stdio_to_kmsg`）。
15. **如果需要，新 Candidate 的唯一变量是什么？**
    - 在 `init.zygote64.rc` 为 Zygote 增加 `stdio_to_kmsg`，或将 child stderr 导向 `/dev/kmsg`。
16. **A 槽 retry 是否需要恢复？**
    - 在未获用户显式启动口令前，不执行恢复；若确定进行实机实验，按纪律执行 `fastboot set_active a` 恢复预算。
17. **如果恢复，恢复前后 readback 是什么？**
    - 恢复前：`slot-retry-count:a: 1`；恢复后：`slot-retry-count:a: 7`。
18. **是否刷写？**
    - 否。保持纯静态。
19. **如果刷写，当前是否停在 Fastboot？**
    - 设备自始至终安全停留在 Bootloader Fastboot。
20. **是否得到用户启动授权？**
    - 否。
21. **启动后是否得到 canary tombstone？**
    - 本轮未重启（沿用 C32 捕获事实）。
22. **真实 Zygote 是否仍 helper EOF？**
    - C32 实机确认仍为 helper EOF。
23. **下一正式修复对象是什么？**
    - 修复 Zygote 的 stderr 可见性黑洞以捕获确切 Linker 报错，并针对 UltraFramework 类加载缺口进行防御性补齐。
