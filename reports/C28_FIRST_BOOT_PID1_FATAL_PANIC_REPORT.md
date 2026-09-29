# THYME-OS4 Candidate 28 首启与 PID 1 Fatal Panic 取证报告

**日期：2026-09-29（HKT）**
**范围：**分析 C28 唯一一次启动、Standalone 全量诊断卷及只读 metadata 导出。没有再次启动 Candidate、刷写、擦除、切槽、`set_active`、BCB 写入或恢复 PixelOS。

## 结论摘要

C28 保存的 console 不是 Recovery 启动，而是一次正常 Android 内核启动。启动约 **33.464 秒**时，内核记录 PID 1 `init` 正在向 `/proc/sysrq-trigger` 写入崩溃字符，随后出现 `Kernel panic - not syncing: sysrq triggered crash`。这直接证明本次 Android 启动被 init 的 fatal-signal 处理路径转成了内核 panic；**触发 init fatal signal 的编号、来源和具体代码仍未捕获**。

因此，C28 本次没有证明已经进入 PixelOS Recovery，也没有证明 C27 的 netd→Zygote 修改成功或失败。pmsg 仍记录 netd 连续 SIGABRT；Zygote、system_server、`sys.powerctl` 和 C28 logger 的最终状态没有可用的 C28 marker/logcat 证据。

## 启动与现场时间线

| 证据时间 | 观察 |
|---|---|
| 启动前 | Observer 已 ARMED；唯一一次 `fastboot reboot` 返回成功。A 槽启动前 `unbootable=no`、`successful=no`、`retry=6`。 |
| 用户观察 | 用户报告屏幕始终是第一屏静态小米 Logo，下方为“powered by Android”；未看到带进度点的 HyperOS 第二屏、设置向导或桌面。约 8 分钟后用户手动进入 Fastboot。 |
| 主机时间线 | ADB 始终未上线；USB/Fastboot 在启动后约 49 秒消失，Fastboot 约在观察器 elapsed 552.5 秒重新枚举，与用户手动返回 Fastboot 的时间相符。 |
| C28 console | 唯一可见 Linux 4.19.325 启动实例；约 33.464 秒 PID 1 fatal 路径触发 sysrq panic。 |
| Standalone 后 | 原始 THYME_DIAG 卷和 metadata 诊断目录已复制到独立目录。随后本轮最后一次主机查询在 G: 发现 `THYME_DIAG` FAT32 卷，`fastboot devices` 与 `adb devices` 均为空；所以**当前实际 Bootloader Fastboot 尚未被主机确认**，尽管用户报告已返回。未向设备发送写入或启动命令。 |

## 直接启动证据

`console-ramoops-0` 为 291,974 bytes，SHA-256 `930CF41C6E1B051992F54793A46D1B86143E63342566561F9AD4D887FE2582AB`。文件包含一个 Linux 4.19.325 启动实例；panic 附近原始记录为：

```text
[33.464590] sysrq: Trigger a crash
[33.464617] Kernel panic - not syncing: sysrq triggered crash
[33.464633] CPU: 2 PID: 1 Comm: init ...
...
write_sysrq_trigger
proc_reg_write
__vfs_write
vfs_write
ksys_write
```

本次 kernel command line 同时包含 `androidboot.init_fatal_panic=true` 和 `androidboot.init_fatal_reboot_target=recovery`。AOSP init 的 `InitFatalReboot()` 在 `init_fatal_panic=true` 时会记录 fatal signal/backtrace 并写 `c` 到 sysrq；否则才按配置的 reboot target 重启。C28 的 PID 1 → `write_sysrq_trigger` 调用栈与此机制一致。[AOSP init/reboot_utils.cpp](https://android.googlesource.com/platform/system/core/%2B/refs/heads/main/init/reboot_utils.cpp#144)

这解释了**本次启动如何被终止**，但不等于已找到 init 为什么收到 fatal signal。保存的 console/pmsg 没有留下该 signal 编号或其前置 backtrace。`init_fatal_reboot_target=recovery` 的存在也不能证明 C28 执行了 Recovery reboot；在实际 panic 分支中，没有捕获 `sys.powerctl=reboot,recovery` 或 `rebootrecovery --bad_nv` marker。用户本次也没有报告看到 Recovery 界面。

## pmsg 与 Framework/服务证据

`pmsg-ramoops-0` 为 89,337 bytes，SHA-256 `9A1687B0739B78AA6494D4DF98A6DC246BDC2D23F3542B988A4735F08FD2EBF4`；可解析时间范围为 `03:11:57.178` 至 `03:12:25.982`，共 798 个时间记录，早于 console 中约 33.46 秒的 panic。

- 记录到 **5 次 netd SIGABRT**（约 `03:12:08.081`、`10.449`、`15.446`、`20.469`、`25.477`）。多份 tombstone 指向 `/apex/com.android.tethering/lib64/libnetd_updatable.so` 的 `libnetd_updatable_init`。这证明 netd 崩溃仍发生；但没有直接 Zygote 状态 marker，不能证明 netd 重启后 Zygote 保持或停止。
- netd tombstone 中的 `ZygotePid: -1` 是 tombstone 字段，不能单独作为 Zygote 不存在或已重启的证据。
- pmsg 有 PID 1063 `main` 的 SIGABRT，以及 crash_dump helper 无法执行的记录；没有留下该 PID 的 executable/cmdline，故不能把它确定为 system_server，也不能把它与随后 PID 1 panic 建立因果关系。相邻 `UltraFrameworkComponentFactoryImpl` ClassNotFound 日志也没有直接 fatal 因果证据。
- pmsg 有 SurfaceFlinger 访问 `perf2`/MiHwc 服务时的 AVC，以及 PID 2211 的两条 `BootAnimation` 日志。它们证明相关进程代码曾运行，但没有 WMS/SystemUI/HOME、`sys.boot_completed`、HWC present fence 或物理面板成功呈现证据。不能由此确认 BootAnimation 帧已显示到屏幕。

## C28 logger 与 metadata 导出限制

第二次 Standalone 使用只读方式导出 `/metadata/thyme_os4_diag`。实际挂载选项为 `ro,relatime,norecovery`（请求 `ro,noload`）。可见的是 14 个既有 C25/C26/C27 文件，**没有可见 `C28_*` 文件**。

由于禁止 ext4 journal replay，这个目录视图无法证明 C28 marker/logger 从未运行：panic 前的文件创建或内容可能还只在 metadata journal 中。故以下均为**未知**：C28 logger 是否写入 `START`、是否成功读取 logd、采样了多少轮、netd/Zygote marker、`sys.powerctl` marker、`sys.boot_completed` marker。不能把“只读视图未见”写成“运行失败”。

metadata-only Standalone 导出器还因不存在顶层 `dmesg_diag_boot.txt` 返回非零；其实际可见的 20 个文件源/副本大小和 SHA-256 均一致。这个 dmesg 文件是 Standalone 环境自己的日志，不是 C28 kernel log。第一次 THYME_DIAG 导出共 8 个文件、0 个复制错误；`oops.raw` header 指向 2024 kernel 的 `Long Press` 记录，不属于本轮 C28。第二个镜像附带导出的 `misc.raw` 只保存在本地，没有解析或改写；没有执行 BCB 操作。

C27 logger 文件为零字节的**确切运行时原因仍未确定**。已知代码层差异是 C27 的 `START` 不是在 status 文件打开后立即 fsync，且失败路径缺少完整的 spawn/exec/wait 留证；这说明 C27 文件不能回答 helper 是否运行，但不能据此断言唯一原因。C28 已把这些留证路径补上，当前只读 metadata 视图却不足以检验它们是否生效。

## 实验边界和状态

- 没有清除 userdata/metadata、改写 misc/BCB、执行 `set_active`、切槽或恢复 PixelOS。
- C28 仍是当前最后已知刷入的 system Candidate（`super`、`vbmeta_system_a`）；其他启动镜像继承此前版本。
- 启动前 A retry=6；本次只启动一次。由于当前主机没有识别到 Bootloader Fastboot，启动后的 retry/unbootable/successful 尚未读回，不能写成 retry=5 的已验证事实。
- 19:40 HKT 主机实际看到 THYME_DIAG UMS 卷而非 Bootloader Fastboot；设备当前 A/B 状态未知。C/D/E 可用空间约 77.72/206.15/250.91 GiB，均高于 50 GiB 门槛；Docker 未访问或修改。

## 下一步

1. 先让设备真实退出 THYME_DIAG UMS，直到主机 `fastboot devices` 可见 Bootloader Fastboot；不运行 reboot、set_active 或刷写。
2. 利用已授权的 metadata 只读取证，通过唯一 `PARTNAME=metadata` 和容量/major/minor 检查读取完整 metadata 原始副本；在主机副本上检查/重放 ext4 journal，绝不在设备分区上 replay。目标是找回 C28 marker、logger START/status 和可能保存的 logcat，再决定是否还需要新启动。
3. 只有 journal 副本也没有 C28 诊断结果时，再准备最小后续诊断版本，重点留存 init fatal signal 编号/回溯与 PID 1063 的进程身份；不立即构建 C29，也不恢复 netd→Zygote callbacks。

**当前没有新修复或新 Candidate；C28 的主要新发现是 PID 1 fatal signal 后触发的 kernel panic，底层 fatal 来源和 C27 的 Zygote 修复效果仍待证。**

## 2026-09-29 20:06 HKT 补记｜metadata journal 主机副本恢复 C28 状态标记

此前“没有可见 C28 marker”是基于 `ro,norecovery` 的首次只读目录视图。随后按授权从唯一 `PARTNAME=metadata` 只读导出完整 metadata；设备端与主机副本长度及 SHA-256 一致。原始 metadata 保留在本机，未公开也未修改。ext4 journal 只在逐字节校验过的主机工作副本上恢复，再由该副本提取文件；没有向设备写入或 replay。

恢复副本中有 12 个 `C28_*` 文件，9 个有内容、3 个为零字节。Init marker 记录 netd 曾 `restarting` 和 `running`；zygote 曾 `running` 和 `restarting`；secondary zygote、SurfaceFlinger、bootanim 和 C28 watcher 曾 `running`；C28 logcat 服务记录为 `stopped`。这些 marker 来自 C28 init rc 的 `init.svc.*` property triggers，但不带时间戳；不能证明 netd restart 导致 zygote restart，也不能仅凭它们确认 system_server 或 Android boot complete。

logcat status 文件、zygote event/tail 文件均为零字节，没有可用 C28 logcat。C28 确实记录到 zygote 进入 restarting，所以 C27 移除 netd 的两条 onrestart 回调不足以保证该次启动中的 zygote 不重启；具体触发者仍未知。PID 1063 `main` 身份和 init fatal signal 来源仍未确认。

公开增量 `evidence/candidate28/first-boot-20260929/metadata-journal-recovery/` 只包含恢复的 C28 marker、文件 SHA-256 清单和来源说明；未包含完整 metadata、misc、ROM、分区镜像或设备身份数据。
