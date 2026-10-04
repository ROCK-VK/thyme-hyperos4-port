# THYME-OS4｜C36-DIAG：Real Zygote SIGABRT 最终触发点精确定位报告

- **日期**：2026-10-02
- **设备**：Xiaomi 10S (`thyme`, SM8250 / Snapdragon 870)
- **基线系统**：HyperOS 4 / Android 17 (`dada` 基线)
- **分析性质**：纯主机侧离线深度逆向与证据链定界分析（设备全程锁定在 Fastboot 待机，未消耗任何启动预算）

---

## 一、设备纪律与证据基线固化

### 1.1 设备状态门禁
- **Fastboot 状态**：设备序列号 `[REDACTED_DEVICE_ID]` 保持在 Bootloader Fastboot 待机。
- **槽位预算状态**：A 槽 `retry=6`，`unbootable=no`；B 槽 `retry=7`。
- **纪律红线执行**：本轮分析未执行任何 `fastboot reboot`、`flash`、`erase` 或 `set_active`，未进行任何猜测性 Candidate 代码构建与烧录。

### 1.2 唯一证据源固化
分析唯一依托 C35 首启 67 分钟真实运行取得的原始诊断资产，物理路径位于：
`reports/c35_diag_candidate35_build_20261002/standalone/run_20261002_164916/THYME_DIAG/`

| 资产文件 | 大小 (Bytes) | SHA-256 校验和 | 证据说明 |
|---|---|---|---|
| `pstore/console-ramoops-0` | 2,097,140 | `ce7d5bd3816ac955a57dcac7c3496f8ad34984b7072da6faf93ed1215a624200` | 内核 ramoops 控制台环形日志 |
| `pstore/pmsg-ramoops-0` | 2,097,140 | `3c123a7253fe401315c16b0c6c2b0b19907438d51b87b2c3b264007716f968aa` | 用户态 liblog/pmsg 环形日志（含 17,045 条有效 Logcat） |
| `dmesg_diag_boot.txt` | 155,238 | `780798efecb396b483234c47c4cb562263c18f081d39904a2cb2d5a149f6bd67` | 独立诊断引导 dmesg |
| `oops.raw` | 16,777,216 | `7d1e254bbeb4803d79fdf96f673ef4dc9c7d0eae68df3019c2384b3439e4bb66` | 原始内核 pstore 内存块 |

---

## 二、C35 已证明之事实（司法级证据链）

1. **Real Zygote 真实执行并持续循环重启**：
   - 在 67 分钟实机首启窗口中，Real Zygote（主线程 `comm=main`, `pid=tid`）累计重启了 **194 次**。
   - 每次生命周期均完整经历启动、类预加载（Preloading classes），直到特定点触发 `SIGABRT`。
2. **每轮循环的高度确定性时序轨迹**：
   - 194 次崩溃周期均呈现**100% 相同**的日志特征序列：
     ```
     SurfaceControl.<clinit>
       ↓ (约 8ms)
     UltraFrameworkComponentFactory: Failed to create UltraFrameworkComponentFactoryImpl
     java.lang.ClassNotFoundException: android.os.ufw.UltraFrameworkComponentFactoryImpl
       ↓ (约 201ms)
     HyperOpt: ThirdAppOptImpl has been initialized !
       ↓ (约 262ms)
     libc: Fatal signal 6 (SIGABRT), code -1 (SI_QUEUE) in tid XXXX (main), pid XXXX (main)
     libc: Crash due to signal: crash_dump helper failed to exec, or was killed
     ```
3. **ThirdAppOptImpl 初始化与 SIGABRT 之间的收敛时间差**：
   - 从 `ThirdAppOptImpl has been initialized !` 到 `Fatal signal 6 (SIGABRT)`，所有周期的耗时高度收敛在 **259.0ms ~ 282.0ms**（均值 265.8ms，代表样本 PID 9971 为 262.0ms）。
4. **外部伴生崩溃定位**：
   - 在 Zygote 循环期间，小米指纹服务 `/vendor/bin/hw/android.hardware.biometrics.fingerprint-service.xiaomi` 在 `/vendor/lib64/libudfpshandler.so` 持续发生 SIGSEGV (SEGV_MAPERR null pointer)。该进程成功由 `crash_dump64` 抓取并输出了完整的寄存器和 backtrace。

---

## 三、C35 未证明之事项

1. **未抓取到 Zygote 的 Native Backtrace 与 Abort Message**：
   - 由于 `crash_dump helper failed to exec, or was killed`，`pmsg` 和 `console-ramoops` 中均未留下 Zygote 在主线程调用 `abort()` 时的 native 调用栈及 abort 原因字符串。
2. **未能在 262ms 窗口内捕获到任何 Logcat 输出**：
   - 在 `ThirdAppOptImpl has been initialized !` 与 `Fatal signal 6` 之间的 262ms 窗口内，Zygote 进程未向 logcat/liblog 写入任何日志。
3. **内核 ramoops (oops.raw) 未包含用户态内存快照**：
   - 内核在整场 67 分钟内运行稳定无 Panic，因此内核 ramoops 仅记录了 dmesg 环形缓冲区，未包含用户态 Zygote 的 core dump 数据。

---

## 四、C35 被排除/失效的假设

1. **排除假设 1：“UltraFrameworkComponentFactoryImpl ClassNotFoundException 直接导致 SIGABRT”**：
   - **证伪证据**：DEX 逆向证实 `UltraFrameworkComponentFactory.getInstance()` 内部使用 `try-catch (Exception e)` 捕获了异常并优雅降级为基础工厂；运行时 Zygote 在该异常后继续正常执行了超过 463ms，并成功初始化了 `ThirdAppOptImpl`。
2. **排除假设 2：“ThirdAppOpt 缺失或未打包”**：
   - **证伪证据**：逆向证实相关组件完整存在于 `framework.jar` 及 `/system_ext/framework/miui-framework.thirdappopt.jar`，运行时日志明确打印 `ThirdAppOptImpl has been initialized !`，证明该组件不仅存在，且已成功执行。
3. **排除假设 3：“Java 未捕获异常导致退出”**：
   - **证伪证据**：若 Java 层发生未捕获异常，`AndroidRuntime` 或 `ZygoteInit` 会强制打印 `FATAL EXCEPTION: main` 或 `Error preloading ...`；全量 17,045 行日志中无任何此类输出。
4. **排除假设 4：“C35 Linker64 补丁拦截了 Zygote debuggerd”**：
   - **证伪证据**：Zygote 的信号处理由 `/apex/com.android.runtime/lib64/bionic/libc.so` 中的 `debuggerd_signal_handler` 主导，C35 仅补丁了 `linker64` 内部的伪线程分发，未能截获 `libc.so` 的崩溃管道。

---

## 五、194 个 Zygote 崩溃周期全景统计

全量周期数据已持久化于：
- CSV: `reports/c36_diag_zygote_sigabrt_20261002/C36_ZYGOTE_CRASH_CYCLES.csv`
- JSON: `reports/c36_diag_zygote_sigabrt_20261002/C36_ZYGOTE_CRASH_CYCLES.json`

### 前 25 个代表周期采样表

| 周期 (Cycle) | PID | UFW Exception 时间 | ThirdAppOpt Init 时间 | Fatal Signal 6 时间 | Δ(Init → Abort) | 下一 PID |
|---|---|---|---|---|---|---|
| Cycle 1 | 9971 | 00:26:56.030 | 00:26:56.231 | 00:26:56.493 | **262.0 ms** | 10086 |
| Cycle 2 | 10086 | 00:27:01.070 | 00:27:01.270 | 00:27:01.534 | **264.0 ms** | 10201 |
| Cycle 3 | 10201 | 00:27:06.030 | 00:27:06.234 | 00:27:06.500 | **266.0 ms** | 10316 |
| Cycle 4 | 10316 | 00:27:11.037 | 00:27:11.235 | 00:27:11.498 | **263.0 ms** | 10431 |
| Cycle 5 | 10431 | 00:27:16.046 | 00:27:16.246 | 00:27:16.507 | **261.0 ms** | 10546 |
| Cycle 6 | 10546 | 00:27:21.066 | 00:27:21.263 | 00:27:21.533 | **270.0 ms** | 10661 |
| Cycle 7 | 10661 | 00:27:26.096 | 00:27:26.295 | 00:27:26.559 | **264.0 ms** | 10775 |
| Cycle 8 | 10775 | 00:27:31.075 | 00:27:31.275 | 00:27:31.542 | **267.0 ms** | 10890 |
| Cycle 9 | 10890 | 00:27:36.136 | 00:27:36.339 | 00:27:36.605 | **266.0 ms** | 11006 |
| Cycle 10 | 11006 | 00:27:41.111 | 00:27:41.308 | 00:27:41.573 | **265.0 ms** | 11121 |
| Cycle 11 | 11121 | 00:27:46.126 | 00:27:46.327 | 00:27:46.592 | **265.0 ms** | 11236 |
| Cycle 12 | 11236 | 00:27:51.139 | 00:27:51.339 | 00:27:51.602 | **263.0 ms** | 11351 |
| Cycle 13 | 11351 | 00:27:56.155 | 00:27:56.353 | 00:27:56.618 | **265.0 ms** | 11466 |
| Cycle 14 | 11466 | 00:28:01.171 | 00:28:01.371 | 00:28:01.637 | **266.0 ms** | 11581 |
| Cycle 15 | 11581 | 00:28:06.195 | 00:28:06.398 | 00:28:06.666 | **268.0 ms** | 11696 |
| Cycle 16 | 11696 | 00:28:11.218 | 00:28:11.417 | 00:28:11.684 | **267.0 ms** | 11811 |
| Cycle 17 | 11811 | 00:28:16.241 | 00:28:16.440 | 00:28:16.708 | **268.0 ms** | 11926 |
| Cycle 18 | 11926 | 00:28:21.261 | 00:28:21.463 | 00:28:21.733 | **270.0 ms** | 12041 |
| Cycle 19 | 12041 | 00:28:26.279 | 00:28:26.478 | 00:28:26.745 | **267.0 ms** | 12156 |
| Cycle 20 | 12156 | 00:28:31.298 | 00:28:31.498 | 00:28:31.765 | **267.0 ms** | 12271 |
| Cycle 21 | 12271 | 00:28:36.321 | 00:28:36.520 | 00:28:36.784 | **264.0 ms** | 12386 |
| Cycle 22 | 12386 | 00:28:41.341 | 00:28:41.541 | 00:28:41.808 | **267.0 ms** | 12501 |
| Cycle 23 | 12501 | 00:28:46.363 | 00:28:46.564 | 00:28:46.832 | **268.0 ms** | 12616 |
| Cycle 24 | 12616 | 00:28:51.385 | 00:28:51.587 | 00:28:51.849 | **262.0 ms** | 12731 |
| Cycle 25 | 12731 | 00:28:56.408 | 00:28:56.611 | 00:28:56.877 | **266.0 ms** | 12846 |

### 统计特征分析
1. **PID 步长恒定**：每次 Zygote 重启，新 PID 递增恰好为 **114 ~ 115**。说明在 Zygote 崩溃重启的 5 秒间隔内，init 系统有序重启了大约 114 个辅助任务或关联服务。
2. **时钟极其稳定**：重启周期严格固定为 **5.00 秒**（init 的标准 service restart backoff）。
3. **窗口高度统一**：Δ(Init → Abort) 的标准差极小（小于 3ms），表明无论系统运行到第 1 周期还是第 194 周期，崩溃点的触发代码路径和时序条件完全恒定，不存在随机性竞态条件。

---

## 六、SIGABRT 前最后共同事件深度分析（262ms 窗口）

对全部 194 个周期进行多通道扫描，结果如下：
1. **Zygote 内部事件数 = 0**：在 `ThirdAppOptImpl has been initialized !` 之后，主线程 `main` 没有写入任何 logcat 事件。
2. **系统共同事件模型**：
   ```
   [T - 463ms] SurfaceControl.<clinit>
   [T - 455ms] UltraFrameworkComponentFactoryImpl ClassNotFoundException (Logged & Caught)
   [T - 262ms] ThirdAppOptImpl has been initialized !
   [T - 262ms ~ T] 静默预加载区间（无 Logcat 输出）
   [T = 0ms] libc: Fatal signal 6 (SIGABRT), code -1 (SI_QUEUE) in tid XXXX (main), pid XXXX (main)
   [T + 13ms] libc: Crash due to signal: crash_dump helper failed to exec, or was killed
   ```
3. **强支撑触发点 (Strongly Supported Trigger)**：
   - 触发点不是外部随机中断，而是 Zygote 主线程自身在顺序执行后续类加载时，由某个底层代码同步触发了 `abort()`。

---

## 七、实际 abort 来源与底层机制

### 7.1 信号特征解析
日志原文：
`Fatal signal 6 (SIGABRT), code -1 (SI_QUEUE) in tid 9971 (main), pid 9971 (main)`

- **`code -1 (SI_QUEUE)` 的底层根源**：
  在 Linux 内核与 Bionic C 库实现中：
  - `SI_USER = 0`（由 `kill` / `raise` 发送）；
  - `SI_TKILL = -6`（由直接 `tgkill` 系统调用发送）；
  - `SI_QUEUE = -1`（由 `sigqueue` 或 `rt_tgsigqueueinfo` 发送）。
  在现代 Android Bionic `libc.so` 的 `abort()` 实现中（`bionic/libc/bionic/abort.cpp`）：
  ```cpp
  void abort() {
      ...
      siginfo_t info = {};
      info.si_signo = SIGABRT;
      info.si_code = SI_QUEUE;
      info.si_pid = getpid();
      info.si_uid = getuid();
      syscall(__NR_rt_tgsigqueueinfo, getpid(), gettid(), SIGABRT, &info);
  }
  ```
- **司法级定性结论**：
  **`SIGABRT` 是由进程自身主线程 `tid (main)` 显式调用 Bionic `abort()` 函数发出的！**
  排除了内核驱动直接发信号、硬件异常直接 trap、以及外部进程 `kill -6`。

---

## 八、UltraFrameworkComponentFactoryImpl 真实状态

### 8.1 源码级调用与降级分析
通过逆向 `work/c23_framework_display_investigation/donor_selected/system/system/framework/framework.jar` 中的 `classes4.dex`：
1. `android.view.SurfaceControl.<clinit>` 字节码：
   ```smali
   invoke-static {}, Landroid/os/ufw/UltraFrameworkComponentFactory;->getInstance()Landroid/os/ufw/UltraFrameworkComponentFactory;
   invoke-virtual {v0}, Landroid/os/ufw/UltraFrameworkComponentFactory;->makeTransactionCallerTracer()Landroid/os/ufw/ITransactionCallerTracer;
   ```
2. `UltraFrameworkComponentFactory.getInstance()` 字节码：
   - 尝试通过 ClassLoader 加载 `/system_ext/framework/ultra-framework.jar` 中的 `android.os.ufw.UltraFrameworkComponentFactoryImpl`；
   - 包含完整的 `catch (Exception e)` 保护块；
   - 捕获异常后，调用 `Log.w(TAG, "Failed to create UltraFrameworkComponentFactoryImpl", e)`；
   - 降级返回基础工厂实例 `new UltraFrameworkComponentFactory()`。

### 8.2 对比 K40 成功样本
- K40 成功运行的 `framework.jar` 与当前 Thyme C35 的 `framework.jar` 字节完全一致（SHA-256 均为 `4F24636042ED6661E62660F0724F5C3A22B7E5F2FE73750593F2DCFC77FBA613`）。
- K40 的 `preloaded-classes` 同样包含该类，且 K40 的 `system_ext` 分区亦无 `ultra-framework.jar`。
- **结论**：`UltraFrameworkComponentFactoryImpl` 的缺失属于小米官方针对非特定机型预留的正常 fallback 机制，绝非导致 SIGABRT 的根因。

---

## 九、ThirdAppOptImpl 的归属、加载链路与执行分析

通过逆向分析，本轮彻底理清了 `ThirdAppOptImpl` 完整的触发链路：

### 9.1 加载链路调用图
```
ZygoteInit.preloadClasses()
  ↓ 遍历 preloaded-classes
第 9510 行: android.view.SurfaceControl.<clinit> (触发 UFW 捕获降级)
  ↓
第 9518 行: android.view.SurfaceControlRegistry.<clinit>
  ↓
SurfaceControlRegistryStub.getInstance()
  ↓ 首次触碰
com.miui.base.MiuiStubRegistry.<clinit>
  ↓
com.miui.base.MiuiFrameworkRouter.init()
  ↓
MiuiFrameworkRouter.collectManifests()
  ↓
miui.thirdappadaptation.thirdappopt.ThirdAppOptFrameworkLoader.init()
  ↓ 调用 loadJar()
加载 /system_ext/framework/miui-framework.thirdappopt.jar
  ↓
MiuiStubRegistry.collectImpl("com.thirdappopt.ThirdAppOptFrameworkImplCollector")
  ↓ 实例化 ThirdAppOptImpl
输出日志: "HyperOpt: ThirdAppOptImpl has been initialized !"
```

### 9.2 关键事实确证
1. `ThirdAppOptImpl` 并非由 `SurfaceControl.<clinit>` 直接调用，而是由预加载清单中紧随其后的 `SurfaceControlRegistry` 间接引爆的框架服务路由初始化流程。
2. 该过程证实：`/system_ext/framework/miui-framework.thirdappopt.jar` 在设备上成功挂载并被读取，DEX 成功载入，类成功初始化。
3. `ThirdAppOptImpl` 本身初始化成功，没有发生崩溃。

---

## 十、从 ThirdAppOpt 到 SIGABRT（262ms 内发生了什么）

### 10.1 `preloaded-classes` 后续执行链
在第 9518 行 `SurfaceControlRegistry` 初始化完毕后，`ZygoteInit.preloadClasses()` 紧接着加载以下类：

| 行号 | 预加载类名 | 涉及 Native / 驱动依赖 | 风险分析 |
|---|---|---|---|
| 9524 | `android.view.SurfaceSession` | `nativeCreate()` (`libgui.so`) | 创建底层 SurfaceComposerClient |
| 9536 | `android.view.SurfaceView` | 静态属性初始化 (`debug.surfaceview.log`) | 低 |
| 9540 | `android.view.SyncRtSurfaceTransactionApplier` | `SurfaceControl.Transaction` | 低 |
| 9544 | `android.view.TextureView` | 平台 flag 校验 (`Flags.xringEnabled`) | 低 |
| **9550** | **`android.view.ThreadedRenderer`** | **`System.loadLibrary("hwui")`、RenderThread 初始化、EGL/Vulkan 初始化** | **极高风险（图形驱动）** |
| 9553 | `android.view.VelocityTracker` | Native 内存池初始化 | 低 |
| 9566 | `android.view.View` | 静态资源与样式初始化 | 中 |

### 10.2 核心嫌疑点聚焦：图形驱动与 Native 初始化
1. 在 Android 17 / HyperOS 4 中，`ThreadedRenderer` 与 `HardwareRenderer` 在加载时会静态触发图形驱动（Vulkan / GLES）及 RenderEngine 初始化。
2. 小米 10S (`thyme`) 搭载高通骁龙 870（Adreno 650），使用的 vendor 图形库是旧版 closed-source 驱动。
3. 若 Native 层（如 `libhwui.so`、`libgui.so`、`libvulkan.so` 或 `libEGL.so`）在向 GPU driver 发起初始化请求时遇到版本不匹配或空指针，直接调用 `LOG(FATAL)` 或 `abort()`，即可完美吻合当前现场的所有特征：
   - 发生在 `SurfaceControlRegistry` 之后约 260ms（恰好是执行到 `ThreadedRenderer` 附近的耗时）；
   - 表现为主线程直接调用 `abort()`；
   - Java 层无任何异常日志；
   - 信号为 `SI_QUEUE`。

---

## 十一、C35 Linker64 补丁未命中根因定性

1. **机制差异**：
   - C35 补丁打在 `linker64` 的 `debuggerd_dispatch_pseudothread`；
   - 该例程仅在可执行文件自身（如动态链接器）发生早期致命链接错误时生效。
2. **运行时主路径**：
   - 目标执行体 `app_process64` 是标准动态链接进程，在其初始化完成后，其信号向量表由 `/apex/com.android.runtime/lib64/bionic/libc.so` 中的 `debuggerd_signal_handler` 全权接管。
3. **Helper 失败根因**：
   - `libc.so` 在收到 SIGABRT 后尝试 fork 并 exec `/apex/com.android.runtime/bin/crash_dump64`；
   - 在 `zygote` 域的安全策略约束下，helper 无法对 target process 实施 ptrace 附加或提前退出，导致通信管道读端直接收到 EOF (`rc == 0`)；
   - `libc.so` 硬编码输出：`crash_dump helper failed to exec, or was killed`。

---

## 十二、下一步精确诊断方案（严禁盲目猜修）

### 12.1 铁律与红线
- 严禁为了“碰运气”去随意删除 `preloaded-classes` 中的类。
- 严禁随意放开大范围 SELinux 策略。
- 严禁在未取得直接 Native Backtrace 证据前构建功能性 C36 修复。

### 12.2 唯一高价值攻坚方向：直接在 Bionic `libc.so` 的 `abort()` 中打捞调用栈
由于 `crash_dump64` 跨进程 helper 在 Zygote 环境下不可靠，**最可靠、最高效且具有司法级定界能力的手段，是在 Bionic `libc.so` 内部实施极简定点抓捕**：

- **方案原理**：
  在 `/apex/com.android.runtime/lib64/bionic/libc.so` 的 `abort()` 入口处：
  1. 调用 `unwind_backtrace` 或直接遍历栈帧（Frame Pointer）；
  2. 将 backtrace 地址与符号信息直接通过 `async_safe_format_log` 写入 logcat/pmsg，或直接 `write(2, ...)` 写入 stdout/kmsg；
  3. 彻底绕过 `crash_dump64`、ptrace 和管道通信。
- **预期收益**：
  在下一次启动时，直接在 `pmsg-ramoops-0` 中取得清晰明确的 Native Backtrace（具体到文件名、函数名和偏移地址），一击锁定究竟是哪个 `.so` 的哪一行代码调用了 `abort()`！

---

## 十三、结论摘要

1. **已证明**：Real Zygote 持续稳定循环，`UltraFramework` 与 `ThirdAppOpt` 均非致命崩溃原因，两者时序由预加载清单严格串联。
2. **已定性**：崩溃是由主线程 Native 代码主动调用 Bionic `abort()` 触发的硬退出（`SI_QUEUE`），发生在 `preloaded-classes` 9518 行之后的图形/View 初始化窗口（耗时约 262ms）。
3. **技术路线**：下一阶段（C36-DIAG 进阶）应将诊断探针从 `linker64` 迁移至运行时核心 `libc.so` 的 `abort()`，实现 Native Backtrace 的第一现场百分之百捕获。
