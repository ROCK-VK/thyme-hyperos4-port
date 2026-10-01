# C30 netd / Zygote / init fatal 因果闭环补充

日期：2026-10-01（HKT）
范围：主机侧针对性证据复核；不查询或操作设备，不启动 C30，不刷写、切槽、擦除、恢复 PixelOS 或构建 C31。

## 结论

- **已确认的故障：** Android 17 / Connectivity 25Q2 `netd` 在 thyme Linux 4.19.325 上因内核版本门槛而 SIGABRT。C26 中还直接观测到 netd 的 init `onrestart` 回调在约 94 ms 后杀死 primary 与 secondary Zygote。
- **C27 之后这条直接边已移除：** C30 最终 `netd.rc` 没有 `onrestart restart zygote` 或 `restart zygote_secondary`。因此 C30 的 netd 崩溃不能再通过这两条 netd 回调直接解释 Zygote 重启。
- **新发现的强候选：** C30 pmsg 中出现五个独立 `main` 进程 SIGABRT；按 C30 AVC #43 的 console uptime 与 pmsg 时间锚对齐，估算发生于约 16.095、18.014、22.855、27.842、32.879 秒。最后一次距离 PID1 在 32.921975 秒触发 sysrq panic 约 43 ms。C30 primary `zygote` 服务仍是 `critical window=10 target=zygote-fatal`。这与 Android init 对未完成启动的 critical service 多次退出后触发 fatal 的条件吻合，**但不能证明这五个 `main` PID 就是 init 所监控的 primary Zygote 实例，也没有保存 critical fatal 原文**。
- **决策：** 现有证据不足以做启动行为修复或 SELinux allow；C31 system change set 仍为空，本轮不构建 C31。最有信息量的下一实验应是诊断型 Candidate：在不改 netd/Zygote/AVC 业务逻辑的前提下，由 init 直接把 primary/secondary/netd 服务状态和 PID 转换写入 pstore 可见的 kmsg，并只对 primary Zygote 启用 `init.svc_debug.no_fatal.zygote=true`，以区分“critical escalation 导致 PID1 panic”与“其他 fatal 路径”。首次启动仍需用户单独确认。

## C30 事件时间线

`pmsg` 给出墙钟样式时间，console 给出启动 uptime。`main`/netd 的 uptime 估值使用 console audit #43（15.951674 s）与相邻 pmsg 时间锚定，误差约数毫秒；audit #46–48 同时保留其 console 原始 uptime。跨 clock 对齐只用于事件顺序，不是 init service PID 映射。

| pmsg 时间 | 估计 uptime | PID / comm | 事件 | 可证明范围 |
|---|---:|---|---|---|
| 19:56:08.082 | 约 15.031 s | 1043 / netd | SIGABRT | netd 实例收到 SIGABRT；不证明它触发 Zygote 退出 |
| 19:56:08.916–09.003 | 15.864623–15.951674 s | PID 未记录 / `main` | AVC #40–43；source domain 为 zygote | 四类 property-area read 被 enforcing SELinux 拒绝；AVC 没有 PID 或 property key |
| 19:56:09.146 | 约 16.095 s | 1051 / main | SIGABRT；crash_dump helper 未能 exec 或被杀 | 进程终止信号已记录；没有 executable identity、abort message 或 tombstone |
| 19:56:09.223 | 16.180116–16.180184 s（console） | PID 未记录 / `main` | 三次 vendor_default_prop AVC | pmsg wall-clock 相对首个 SIGABRT 晚约 77 ms；console uptime 相对首个估值约晚 85 ms。两个时钟均显示它们发生在 abort 之后，不能归给 PID 1051 |
| 19:56:10.299 / 11.065 | 约 17.248 / 18.014 s | 1770 netd / 1754 main | 各一次 SIGABRT | netd 与 main 崩溃重复；两者服务关系未由本轮 marker 定序 |
| 19:56:15.326 / 15.906 | 约 22.275 / 22.855 s | 2456 netd / 2453 main | 各一次 SIGABRT | 同上 |
| 19:56:20.338 / 20.893 | 约 27.287 / 27.842 s | 2638 netd / 2636 main | 各一次 SIGABRT | 同上 |
| 19:56:25.331 / 25.930 | 约 32.280 / 32.879 s | 2758 netd / 2756 main | 各一次 SIGABRT | 最后一个 main SIGABRT 约早于 init sysrq panic 43 ms；时间接近不是因果证明 |
| 32.921975 s | 32.921975 s | PID 1 / init | 写 `sysrq-trigger`，内核记录 `Trigger a crash` 并 panic | PID1 主动走 sysrq panic 路径；未保存触发它的 init fatal 条件 |

在 C30 console 与 pmsg 搜索范围内，没有发现可确认的 `critical process 'zygote' exited 4 times`、`zygote-fatal` 或对应 init fatal 文本。C30 pmsg 的 `main` 只是记录的进程/线程名，不能单凭名称将 PID 1051、1754、2453、2636、2756 映射到 init 的 `zygote` service。C30 canary、ordered event、logger 持久文件仍是 0 字节，缺少 service state / PID / wait status。

## 两条候选因果链

### 1. netd crash → Zygote

| 证据 | 结论 |
|---|---|
| C26：netd 在 Linux 4.19.325 上被 25Q2 检查拒绝并 SIGABRT；约 94 ms 后 init 向两个 Zygote 进程组发 SIGKILL；当时 `netd.rc` 含两条 Zygote `onrestart` | C26 这次“netd 重启回调导致 Zygote 被 init 杀”的直接机制已实机记录。它不证明 netd 是整个系统第一次 Zygote 失败的根因。 |
| C27 及 C30 `netd.rc`：两条 netd→Zygote 回调已移除 | C30 没有这条直接回调边。 |
| C30 primary `zygote` `onrestart restart netd`；secondary Zygote `onrestart restart zygote` 仍在 | 仍可能出现 Zygote→netd 或 secondary→primary 的反向/旁路连锁。C28–C30 metadata marker 只有曾 running/restarting，没有可靠时间顺序。 |
| C30 pmsg：netd SIGABRT 与 `main` SIGABRT 反复交错 | 证明两种崩溃都发生；不能区分 netd 是先因、Zygote 重启的下游，还是并行故障。 |

因此，netd 25Q2/4.19 是**已确认的独立服务故障**；C26 的特定直接重启边已移除；C30 的 netd 是否仍以其他回调或服务依赖触发 Zygote 重启，尚未证明。Android 25Q2 上游 NetBpfLoad 源码明确有 Linux 5.4 内核门槛，与设备上的 netd fatal 记录相符。[AOSP NetBpfLoad.cpp](https://android.googlesource.com/platform/packages/modules/Connectivity/+/a0fa137d8524f41932bde5449a0db14254db4a7b/bpf/loader/NetBpfLoad.cpp)

### 2. Zygote `main` SIGABRT → critical fatal → PID1 panic

C30 primary Zygote 仍配置 `critical window=10 target=zygote-fatal`，vendor 属性缓存中有 `zygote.critical_window.minute=10`。Android 17 init 文档说明，critical service 在 boot complete 前退出超过四次会进入 fatal reboot target；`init.svc_debug.no_fatal.<service-name>=true` 是供测试跳过该 fatal 的调试属性。[Android 17 init README](https://android.googlesource.com/platform/system/core/%2B/android17-release/init/README.md)

C30 观察到五个 `main` SIGABRT，最后一个仅比 PID1 sysrq panic 早约 43 ms；因此“primary Zygote 多次退出触发 critical fatal，再触发 PID1 panic”目前是最强、可直接证伪的候选。但下列链节缺失：

1. `main` 五个 PID 与 init primary `zygote` service 的身份映射；
2. 每次 init service `running/stopping/restarting` 和 PID/wait status；
3. `sys.boot_completed` 在第五次退出前的实际值；
4. panic 前 init critical fatal 原文或其对应的 reboot target；
5. `main` SIGABRT 的 tombstone/backtrace。

故不能把“5 次 `main` abort + critical 配置 + 43 ms 后 panic”写成已确认根因，也不能判断 `main` 的 abort 是由 AVC、UltraFramework 之外的 native/Java 错误、或别的链路触发。

## AVC 与 UltraFramework 结论

- 7 条 AVC 都由 `u:r:zygote:s0` 中 `comm="main"` 发出，目标为 property-area 文件；type 共 5 种。其与首个 `main` SIGABRT 时间相邻，但 AVC 没有 PID/key，SIGABRT 没有 backtrace，未闭合 `AVC → consumer → abort`。
- `vendor_default_prop` 的三条 AVC 晚于首个 `main` SIGABRT约 77 ms，不能作为该次 abort 的触发证据。
- `UltraFrameworkComponentFactoryImpl` 的加载失败由 C30/K40 共同 framework.jar 代码捕获并 fallback；C30 同 PID 后续还记录了其他初始化完成。缺类异常不是当前可确认的直接 fatal。
- K40 对四类相关 property type 的 Zygote access grant 是策略差异，不等于这些权限为 C30 当前 panic 的根因修复。fingerprint schema 差异也因 exact property key 缺失，不能进入 C31。
- 不新增 SELinux allow，不修改 netd、Zygote、secondary callback、critical 配置或图形路径。

## 决策与下一实验

**结果：B——现有证据仍不足以形成系统行为修复；本轮不构建、不刷写 C31。** 当前 C30 `C31_SYSTEM_CHANGE_SET` 继续为空。

下一次唯一最必要实验是一个诊断型 Candidate（只有在决定进入下一次实机实验时才构建）：

1. 在 init 启动早期，以 init 自身的 `write /dev/kmsg`/pstore 可留存通道记录 `init.svc.zygote`、`init.svc.zygote_secondary`、`init.svc.netd` 的每次状态变化和 `init.svc_debug_pid.*`；记录 boot ID 与单调时间。实施前定点验证该 Android init 版本的 property expansion、kmsg write 和 SELinux 权限，不再依赖 C30 的 shell helper 写 `/metadata`。
2. 仅对 primary Zygote 临时设置测试属性 `init.svc_debug.no_fatal.zygote=true`，其他 critical service 与业务配置不变。若原先会在第五次退出触发 init fatal，下一次应不再出现相同 critical panic，且能继续留存第六次及后续的真实退出信息；若仍 panic，则该 critical 假说被显著削弱。
3. 第一次启动前仍需用户现场授权。失败后第一次 RAM 诊断必须先保存 Candidate pstore，再抓 metadata/misc 和完整 THYME_DIAG。

这次实验用于确认“谁在重启、init 是否因 Zygote critical 触发 fatal”，不是宣称修复 netd 或 Zygote。若诊断证明某条直接故障链，下一 Candidate 再只改那条已证实的链。

## 设备、构建与发布边界

- 本轮没有查询或操作手机；设备当前 USB/Fastboot 模式未核实。最近历史记录的 A retry=3 / unbootable=no 不是实时状态。
- 没有构建 C31、刷写、reboot、set_active、清除 userdata/metadata 或恢复 PixelOS。
- 本轮仅使用已归档 C30 pstore/pmsg 和 C26–C30 相关报告/最终 rc；未重新解包 ROM、重新计算历史镜像哈希或进行大型提取。
- 报告仅引用本地原始证据路径与 SHA，不包含 pstore 原始字节、metadata/misc raw、ROM、镜像或设备私密数据。
- C/D/E 最近实测分别有约 92.02 / 196.46 / 170.80 GiB 可用空间；均高于 50 GiB 门槛。没有清理，Docker 未触碰。
