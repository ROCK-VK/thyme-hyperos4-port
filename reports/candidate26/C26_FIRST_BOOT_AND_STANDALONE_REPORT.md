# C26 首次启动与 Zygote 诊断报告

日期：2026-09-29（HKT）  
观察标签：`C26-zygote-first-exit`  
主机观察：[C26 host observation](../../evidence/candidate26/run_20260929_133135/host-observations/)  
Standalone 导出：[C26 Standalone evidence](../../evidence/candidate26/run_20260929_133135/standalone/)  
文件来源、公开副本大小及 SHA-256：[PUBLIC_EVIDENCE_MANIFEST.csv](../../evidence/candidate26/run_20260929_133135/PUBLIC_EVIDENCE_MANIFEST.csv)

## 结论

C26 已进入 Android 用户空间并触发 `post-fs-data`，但没有进入稳定的 Zygote/SystemServer 阶段。用户看到静态小米第一屏后，约 9 分 9 秒时手动进入 Fastboot；主机观察器没有记录设备自行返回 Fastboot。ADB 全程未上线，Android 日志和诊断采样只覆盖启动早期。

本轮首次捕获到明确的 `netd` 服务故障：Android 25Q2+ 的 `libnetd_updatable` 因当前 Linux 4.19 内核低于其 5.4 门槛而触发 `SIGABRT`。但是现有日志不能证明该故障导致 Zygote 首次退出。Zygote 配置包含 `onrestart restart netd`，因此后续一部分 netd 重启可能是 Zygote 重启的下游结果。

## 启动时间线与诊断覆盖

- 观察器在一次 `fastboot reboot` 前报告 `[ARMED]`。用户报告屏幕持续为静态小米 Logo；约 9 分 9 秒后手动进入 Bootloader Fastboot。A 槽 retry 由 2 降至 1，状态为 `unbootable=no / successful=no`；B 槽仍为 `retry=7`。未执行 `set_active`、分区写入、擦除、BCB 修改或 PixelOS 恢复。
- `C26_INIT_TRIGGER.txt` 证明 `post-fs-data` 动作触发。持久 logcat 在 uptime 15.297 s 启动并写出 8,564,736 bytes；最后可读 Android 记录约为 uptime 50.959 s，init 服务在 uptime 52.027 s 变为 stopped。服务为 oneshot；提前停止原因尚未确定。
- Zygote watcher 实际记录 8 份 logcat tail，事件文件写到 32 KiB 上限后以半行结束，未生成 900 秒 `COMPLETE`。C25 sampler 在此轮只记录 4 个样本，最后约 uptime 60.395 s。
- 首次观察到 64 位 Zygote `running` 约在 uptime 15.426 s，约 147 ms 后转为 `stopping`；secondary Zygote 也停止，随后服务反复恢复/停止。现有 logcat 与 tail 没有捕获可解释首次退出的 Zygote `FATAL EXCEPTION`、native fatal 或明确错误。
- 诊断 helper 对 `init.svc_debug_pid.zygote*` 的读取遭 enforcing SELinux 拒绝并产生 AVC。普通 `init.svc.zygote*` 属性和部分进程快照仍有数据；该诊断权限失败不是已证明的系统启动根因。

## 明确的 netd 错误

C26 logcat 在 uptime 14.409 s 首次记录：`libnetd_updatable_init: Failed: 25Q2+ platform with kernel version < 5.4.0 is unsupported`，随后 `/system/bin/netd` 收到 `SIGABRT`。Standalone 记录的内核为 `4.19.325-perf-g45b9b954f074`。同一错误在后续 netd 实例重复出现。

已有 K40/C13 Tethering APEX 缓存中的 `libnetd_updatable.so` 完全相同（103,648 bytes，SHA-256 `2c811151e99f227bc8e180f64f0b686e8d696b5323ce2f81313914cc597277ad`），因此这份 K40 参考没有给出可直接复制的软件绕过。K40 当时的内核和启动组合是否满足 5.4 门槛，本轮没有重新核验。

## 取证完整性与公开范围

Standalone 全卷副本含 14 个可访问文件、12,972,436 bytes，源/副本大小及 SHA-256 均已核对一致。其中文件中的 10 项公开；完整 4 MiB `misc.raw`、对应 SHA sidecar、含 misc 散列的源清单/校验文件和 Windows `System Volume Information` 文件没有发布。诊断状态中的 misc 散列、CPUID、设备 USB 序列号、主机名和本机路径均在公开文本副本中处理；本地未修改原件继续保留。

本卷没有 `console-ramoops`、`pmsg-ramoops`、`oops.raw` 或 `dmesg_diag_boot.txt`。C26 的 Android 用户空间证据来自持久 logcat、Zygote event/tail、C25 sampler 输出及触发标记。主机侧两个 logcat 文件为空，ADB 未上线。

## 当前判断与下一步

1. C26 补上了 C25 缺失的早期 Android logcat，但未保留 Zygote 退出首因，也没有达到 15 分钟采样目标。
2. `netd` 的 25Q2/4.19 冲突是真实服务故障，应单独评估其启动影响和最小兼容路径；不能把它直接当作 Zygote 根因。
3. 下一步先解释 logcat oneshot 为什么在约 52 秒停止，并取得 Zygote 首次退出时的可解释 fatal/crash 证据。当前没有足够因果证据构建 C27。
4. C26 仍是设备当前镜像；最后只读查询为 `thyme / A / unlocked / Bootloader Fastboot`，A `retry=1`、B `retry=7`。没有启动新版本或修改启动槽状态。
5. C/D/E 最新可用空间约为 78.00/233.95/265.84 GiB。C 盘空间治理门槛为低于 50 GiB；当前未触发。Docker 始终排除。

上游参考：

- [AOSP netd kernel tests](https://android.googlesource.com/platform/system/netd/+/refs/heads/main/tests/kernel_test.cpp)
- [AOSP Connectivity NetBpfLoad kernel gates](https://android.googlesource.com/platform/packages/modules/Connectivity/+/5f020a5ab853acf2a5a3ece263de716987c3f0d0/bpf/loader/NetBpfLoad.cpp)