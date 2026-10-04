# THYME-OS4｜C33-DIAG 静态深化：Real Zygote 多线程 / ptrace attach / sigchain / seccomp 差异深度审计报告

- 日期：2026-10-02
- 阶段：C32 首启后 → C33-DIAG 静态深化排查阶段
- 目标：从“C32 Canary 成功留下 Tombstone，而 Real Zygote 产生 crash_dump helper EOF”的已确证差异出发，反汇编核实多线程 ptrace、libsigchain、seccomp 及 helper 握手链，定位真实分水岭。
- 纪律状态：纯主机端静态分析；未构建新镜像、未刷写、未重启，A 槽 retry=1 严格保全。

---

## 一、核心事实源与基线对照

在 C32 实机首启（A 槽单次启动）的 Standalone 取证中，形成了不可动摇的对照事实：

1. **Canary 对照组 (PID 1453)**：
   - ELF：`/system/bin/c32_zygote_canary`，单线程，native PIE。
   - 行为：主动调用 `android_set_abort_message("THYME_C32_CANARY_ABORT")` 并 `abort()`。
   - 结果：`crash_dump64` (PID 1474) 成功拉起，成功完成握手，并在 pmsg 中输出完整的 3 帧 backtrace tombstone。
2. **Netd 对照组 (PID 11422)**：
   - ELF：`/system/bin/netd`。
   - 行为：因 Android 17 / kernel 4.19 `NetBpfLoad` 不兼容触发 SIGABRT。
   - 结果：`crash_dump64` (PID 11453) 成功拉起并完成 dump，输出 4 帧 backtrace tombstone。
3. **Real Zygote 实验组 (PID 1068 / 1069 及后续 97 个主 PID)**：
   - ELF：`/system/bin/app_process64`，主线程触发 SIGABRT。
   - 结果：全部伴随 `Crash due to signal: crash_dump helper failed to exec, or was killed`。
   - 无任何真实 Zygote abort message，无 backtrace，无 tombstone。

---

## 二、NNP 假设排除与控制流闭环

反汇编目标：`/path/to/thyme-os4-build/c31_runtime_inspect_20261001/rootfs/payload/bin/linker64`

### 1. `debuggerd_signal_handler` 控制流分支铁证
- **指令地址 `0x110aac`**：
  ```arm64
  110aac: mov  w0, #0x27       // #39 = PR_GET_NO_NEW_PRIVS
  110ac0: bl   5ac80 <__dl_prctl>
  110ad0: cmp  w24, #0x1
  110ad4: b.eq 110b0c          // 若 NNP == 1，直接跳转 0x110b0c
  ```
- **分支 1（NNP == 1）**：跳转 `0x110b0c`，调用 `__dl_debuggerd_fallback_handler`。该路径为进程内自解栈，完全绕过外部 helper 的 fork、exec 及管道通信。
- **分支 2（NNP == 0）**：落入 `0x110adc`，加锁 `crash_mutex`，随后进入 `clone()` 伪线程 `debuggerd_dispatch_pseudothread`，由伪线程 `_Fork()` 出子进程去 `execle("crash_dump64")`，父端在 `0x1119b4` 执行 `read(pipe_fd, &byte, 1)` 等待握手。
- **报错触发点 `0x111cb0`**：
  ```arm64
  111ca4: cmp  x4, #0x1        // x4 为 read 返回值
  111cb0: // 若 x4 == 0 (EOF)，立即格式化并输出:
          // "%s: crash_dump helper failed to exec, or was killed" (偏移 0xeb4f)
  ```

### 2. 结论
Real Zygote 在 pmsg 中打印了该报错，铁证其必定走的是**分支 2（NNP == 0）**。
若 NNP=1，早在 `0x110ad4` 即切入 fallback，绝不可能执行外部 helper 并看到 EOF。**“NNP 导致 helper 失败”的假设已被 100% 证伪并正式排除。**

---

## 三、`crash_dump64` 多线程 ptrace 路径审计（核心问题 Q1 ~ Q5）

反汇编目标：`/path/to/thyme-os4-build/c31_runtime_inspect_20261001/rootfs/payload/bin/crash_dump64`

### Q1：当前 Xiaomi `crash_dump64` 是否枚举所有 TID？
**是**。在 `main` 函数源码第 724 行（PC `0x228d8` / `0x25454`），调用 `readdir` 遍历 `/proc/<pid>/task` 目录获取目标进程的所有线程 ID。若打开目录失败，报错 `failed to get process threads:`。

### Q2：是否逐个 attach sibling thread？
**是**。在源码第 741 / 815 行（PC `0x22fc0` ~ `0x22ff8`），遍历 TID 列表，调用 `ptrace_seize_thread`（PC `0x25f80`，内部执行 `ptrace(PTRACE_SEIZE, tid)`）。

### Q3：如果某个 sibling thread attach 失败，会退出或导致整个 dump 失败吗？
**绝对不会！这是本次审计的关键突破。**
汇编逻辑铁证（PC `0x22fd8` ~ `0x239c4`）：
```arm64
22fd8: ldr   w9, [x26, #24]    // w9 = crashing target tid (主崩溃线程 TID)
22fe0: cmp   w8, w9           // w8 = 当前 attach 失败的 tid
22fe4: mov   w8, #0x6         // 6 = FATAL (致命)
22fe8: mov   w9, #0x3         // 3 = WARNING (警告)
22fec: csel  w25, w8, w9, eq  // 若为 main tid 则 FATAL；若为 sibling tid 则仅为 WARNING!
22ff4: bl    ShouldLog
...
239c4: b     22ffc            // 记录警告后，直接跳转 22ffc，继续循环遍历下一个 sibling 线程！
```
- **核心结论**：如果某个 sibling thread attach 失败，`crash_dump64` 仅将其视为非致命警告（Severity 3），**直接跳过并继续处理其余线程**！
- `crash_dump64` 绝不会因为 sibling 线程 attach 失败而提前退出或非零退出，更不会导致父端看到 EOF。

### Q4：对 `PTRACE_SEIZE` / `PTRACE_ATTACH` 失败是否有明确日志？
**是**。在 `0x26148` 调用 `strerror(errno)`，输出 `failed to attach to thread %d: %s`；若 `errno == EPERM` 且被其他进程追踪，则输出 `failed to attach to thread %d, already traced by %d (%s)`。

### Q5：C32 的 `crash_dump helper failed to exec, or was killed` 是否由 sibling 线程 attach 失败导致？
**否，绝对不是。**
1. 静态代码证明：sibling 失败仅记 WARNING 并继续运行，随后正常执行第 893 行的伪线程握手；
2. 运行时日志证明：C32 的 pmsg 中**没有任何一条**来自 `crash_dump64` 的 attach 失败日志，甚至连第 639 行的 `crash_dump start` 都未曾打印。
3. **事实真相**：`crash_dump64` 根本未曾执行到线程遍历阶段。

---

## 四、真实 Zygote 线程模型核验

结合 C32 捕获的原始 `pmsg-ramoops-0` 与 `console-ramoops-0`：
1. **已确认存在的事实**：
   - 崩溃线程确认为 `tid 1068 (main), pid 1068 (main)`；
   - 信号为 `Fatal signal 6 (SIGABRT), code -1 (SI_QUEUE)`；
   - 在主线程崩溃前，Java 层已抛出：
     `java.lang.ClassNotFoundException: android.os.ufw.UltraFrameworkComponentFactoryImpl`
     `at android.os.ufw.UltraFrameworkComponentFactory.getInstance(UltraFrameworkComponentFactory.java:79)`；
2. **多线程存在性边界**：
   - 在 ART 虚拟机启动流程中，`Runtime::Start()` 会拉起 `Signal Catcher`；
   - 但无论 Zygote 在崩溃时是否已经衍生出辅助线程，**第三节的反汇编已证明 sibling 线程的状态与 crash_dump 的存活完全解耦**。

---

## 五、PTRACE 权限与 DUMPABLE 逻辑审计

1. **`linker64` 是否设置 dumpable？**
   - 全反汇编审计证明：`linker64` 的 `debuggerd_signal_handler` **不调用 `prctl(PR_SET_DUMPABLE, 1)`**。
2. **内核级 PTRACE 约束**：
   - Linux 内核 `__ptrace_may_access()` 规定：若目标进程不可 dump，ptrace 进程必须拥有 `CAP_SYS_PTRACE` 能力。
   - `linker64` 在 fork 外部 helper 之后、调用 `execle` 之前，显式通过 `0x111fb4` 循环调用 `prctl(PR_CAP_AMBIENT, PR_CAP_AMBIENT_RAISE, cap)` 赋予子进程 `CAP_SYS_PTRACE`。
3. **SELinux 策略核查**：
   - 在 `plat_sepolicy.cil` 中：
     `(allow crash_dump base_typeattr_381 (process (sigchld sigkill sigstop signal ptrace)))`
     其中 `base_typeattr_381` 包含 `zygote`。
   - `crash_dump` 对 `zygote` 具有完备的 `ptrace` 权限，实机日志无任何针对 `crash_dump` 的 AVC 拒绝。

---

## 六、`libsigchain.so` 深度审计

目标文件：`/apex/com.android.art/lib64/libsigchain.so`（从 `com.android.art.capex` 解包还原）
1. **加载关系**：`app_process64` 的 `DT_NEEDED` 直接依赖 `libsigchain.so`。
2. **SIGABRT 处理机制**：
   - `libsigchain.so` 导出了重载的 `sigaction` / `signal`；
   - 但在 `art::SignalChain::Handler(int signo, siginfo* info, void* ucontext)`（PC `0x6c1c`）中，ART 仅对 SIGSEGV、SIGBUS、SIGILL、SIGFPE 等隐式检查信号挂载 special handler；
   - **对 SIGABRT (信号 6)，ART 不设拦截**，而是直接原样传递给下层注册的 `user_handler_`（即 Bionic `linker64` 的 `debuggerd_signal_handler`）；
   - 传递的 `siginfo` 与 `ucontext` 未被篡改。
3. **结论**：`libsigchain` 并非信号丢失或上下文破坏的源头。

---

## 七、Zygote 主进程 Seccomp 过滤器核实

目标文件：`/system/lib64/libandroid_runtime.so`
1. **过滤函数调用点**：
   - `libandroid_runtime.so` 中的 `_set_seccomp_filter` 仅在 `register_com_android_internal_os_Zygote` 初始化的 JNI 方法中定义；
   - 实际设置过滤器的入口是 `SpecializeCommon`（在 Zygote fork 出 app 或 system_server 子进程时调用）；
2. **结论（重大纠偏）**：
   - **Real Zygote 主进程自身在 fork 之前没有任何 Seccomp 过滤器！**
   - 降级此前关于“Zygote 主进程 Seccomp 拦截 syscall”的推测为已排除。

---

## 八、综合诊断结论与分水岭定位

通过对汇编代码、符号表与日志的交叉比对，形成如下严密证据链：

1. **排除项汇总**：
   - 排除 NNP（汇编证明 NNP=0）；
   - 排除 Sibling 线程 ptrace 失败导致退出（汇编证明其为 non-fatal WARNING）；
   - 排除 libsigchain 吞信号（原样递交 debuggerd_signal_handler）；
   - 排除 Zygote 主进程 Seccomp 拦截（主进程无 filter）；
   - 排除 SELinux 拒绝 crash_dump ptrace zygote（CIL 明确 allow）。
2. **真实失败阶段（里程碑 A）**：
   - 失败发生在 `linker64` 内部创建 helper 的极早阶段：
     即 `_Fork()` 产生的子进程在执行 `execle("/apex/com.android.runtime/bin/crash_dump64")` 的瞬间或动态链接器加载阶段，**子进程直接崩溃、被内核杀灭或执行失败**，未能写入任何一个字节到父端管道，导致父端在 `read()` 时立刻遭遇 EOF！
3. **为什么 Canary 与 Netd 成功，而 Zygote 失败？**
   - Canary 与 Netd 均未启动完整的 Java 框架层与复杂的 linker namespace；
   - Zygote 主进程在初始化过程中，切换了复杂的 linker namespace（APEX runtime/art/default 隔离）或处于特定的进程环境，导致其 fork 出的子进程在执行来自 `/apex/com.android.runtime/` 的 `crash_dump64` 时，动态链接器无法解析或遭遇环境异常。

---

## 九、下一步唯一必要实验建议

当前静态分析已经成功将范围从“盲目猜测多线程/权限”收敛到了**“Zygote 进程环境下外部 crash_dump helper 的拉起链”**。

在不消耗 A 槽仅剩 retry=1 的前提下，目前最科学的决策：
1. **不构建纯 NNP Canary**（已证明无直接对应关系）；
2. **首选方案（纯静态深化）**：
   重点审查 `app_process64` 在启动 Java 虚拟机前后对环境变量（`LD_LIBRARY_PATH`）、Linker Namespace 以及文件描述符的变更，查明子进程 `execle` 的具体障碍；同时深入分析 `UltraFrameworkComponentFactoryImpl` 的类加载路径，评估能否直接从 Java 层规避该 ClassNotFoundException。
3. **备选方案（受限 Canary 实验）**：
   若后续必须通过实机验证，仅允许设计一个**继承真实 Zygote domain 与 namespace 属性的多线程 Canary**，且必须在获得用户明确授权后方可构建与测试。
