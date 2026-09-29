# THYME-OS4 Candidate 29 首次启动与 pstore 归属报告

日期：2026-09-29（HKT）
范围：C29 唯一一次正常启动、两次 Standalone 全量取证、metadata 主机副本 journal recovery，以及第二次 RAM 诊断启动的 pstore 分类。没有重新启动或刷写 Candidate。

## 结论

C29 正常启动至少推进到了 init 管理 Zygote 与 netd 服务的阶段：恢复出的 Init marker 记录 primary zygote、secondary zygote 和 netd 曾进入 `running`，primary zygote 与 netd 也曾进入 `restarting`。但 marker 不带可靠时间顺序；C29 event log 与 logcat status 文件均为 0 字节，没有 system_server PID、fatal backtrace、`sys.powerctl`、boot-complete 或 Android pstore 证据。因此无法确认 Zygote 是否 fork 出 system_server，也无法判定 netd 与 Zygote restart 的因果或 C29 为什么停在屏幕第一屏。

专门为 pstore 补采后，读取成功，但唯一的 `console-ramoops-0` 属于前一轮 Standalone 诊断 Linux 会话，不属于 C29 Android 启动。没有捕获到可归属 C29 的 console/pmsg/oops。当前 C29 根因仍未闭环；不据此构建 C30 或宣称 C27 的 restart callback 改动成功/失败。下一步只定点核查 helper 在文件创建后未留下首条 payload 的 shell 域写入/同步路径。

## C29 启动时间线

| 时间（UTC） | 证据 |
|---|---|
| 2026-09-29 14:46:37.926 | 主机观察器启动；Candidate 标签为 C29。 |
| 2026-09-29 14:47:34.818 | 唯一一次 `fastboot -s <device-id-redacted> reboot`，退出码 0。 |
| 14:47:34.946（elapsed 57.092s） | Fastboot 查询转为 absent；USB bootloader 接口仍短暂 present。 |
| 14:47:41.948（elapsed 64.072s） | USB/ADB/Fastboot 均 absent；ADB 从未上线。 |
| 14:54:12.078（elapsed 454.201s） | Fastboot 命令行状态再次可见；USB 接口随后在 14:54:17.079 重新 present。与用户手动返回 Fastboot 的过程相符。 |

用户报告启动期间一直看到静态 Xiaomi Logo。主机启动前 A 槽 retry=5、unbootable=no、successful=no；启动后只读读回 retry=4、unbootable=no、successful=no。B 槽 retry=7 且未变化。本轮没有 `set_active`。

## C29 metadata 诊断结果

第一份 16 MiB metadata 原始副本设备端与主机 SHA-256 一致：`[raw metadata SHA-256 withheld; retained locally]`。原始副本保持未修改；只在主机副本恢复 ext4 journal 并提取文件。

恢复出的 C29 marker：

- `C29_INIT_PRIMARY_RUNNING.txt`
- `C29_INIT_PRIMARY_RESTARTING.txt`
- `C29_INIT_SECONDARY_RUNNING.txt`
- `C29_INIT_NETD_RUNNING.txt`
- `C29_INIT_NETD_RESTARTING.txt`
- `C29_INIT_LOGCAT_STOPPED.txt`

这些 marker 是 init 服务状态触发器留下的状态事实，不含事件时间戳。不能据文件名或文件系统时间推导先后。C29 event 文件及对应 logcat status 文件均为 0 字节。定点对照已公开的 C29 helper 源码发现：`C29_events_<boot_id>.log` 由 `WatchServices()` 的 `EnsureEvents()` 创建；带 `u15291_p1027` 的 logcat status 文件由 `RunLogcat()` 的 `OpenUniqueFile()` 创建，命名记录了 helper PID 与启动后毫秒数。它们与 C29 唯一 boot_id 相符，支持两个 helper 都至少执行到输出文件创建/打开阶段；不是“诊断服务完全没启动”。但首条有效写入未留存，不能区分 write/fdatasync 失败、创建后立即退出/被终止或其他存储错误。`LOGCAT_STOPPED` 只说明 init 观察到服务 stopped，不能说明退出原因。没有 system_server PID 或真实崩溃栈。

## 第二次 Standalone 全量导出与 pstore 分类

- 专用诊断镜像：201,326,592 bytes；SHA-256 `0B6CD085E6764865A1CCF1D6F5B5B2A47BA801C30F3F5556BE6D2A3A60677B6D`。
- 使用 `fastboot boot` 仅 RAM 临时启动，命令成功；没有写入持久分区。
- 新目录 `standalone_exports_pstore/run_20260929_231456/` 共复制 40 个文件，复制错误为 0；每个可访问文件的源/副本大小与 SHA-256 相同。完整本地清单为 `FILE_MANIFEST.csv` 和 `SHA256SUMS.txt`。
- `pstore_status.txt` 显示只读挂载成功，复制 1 个文件：`console-ramoops-0`，224,259 bytes，SHA-256 `3D502B6D0EF9E80EDDBFC02BEFEDD88D050FF2ABDBF71210FE3632BB4908034E`。没有 pmsg 或其他 pstore 文件。
- 该 console 的内核标识为 `Linux 4.19.325-perf`，cmdline 与本次 Standalone `dmesg_standalone.txt` 相符；内容含 `[bq2597x-STANDALONE]`、`work mode:Standalone`，约 1054 秒还有触屏事件，末尾约 1059.466 秒。它是上一轮 Standalone 会话留下的 console，不是 C29 Android 启动日志。`dmesg_standalone.txt` 明确来自本次 Standalone 诊断内核，也不能当作 C29 dmesg。

第二份 metadata 原始副本为 16,777,216 bytes，设备端 sidecar 与主机副本 SHA-256 一致：`[raw metadata SHA-256 withheld; retained locally]`。它与第一份 snapshot 的哈希不同，但逐字节比较仅发现 8 个不同字节，均位于首个 4 KiB 块；`dumpe2fs` 可见的 filesystem state、last-mounted path、mount count、last mount/write time 和 journal sequence 字段相同。差异原因未确定。只对第二份的独立工作副本运行 journal recovery；`e2fsck -f -n` 随后检查干净。恢复出的 C29 marker、空 event 文件和空 logcat status 与第一份主机恢复结果逐字节相同。两份原始 metadata 均保留未修改。

### 文件与数据安全

本地完整导出包括 `metadata.raw` 与 `misc.raw`，它们仅本地保存，没有加入公开仓库。没有修改设备上的 metadata、misc/BCB、userdata 或其他分区。公开增量只发布 C29 专属 marker、pstore/Standalone 诊断日志、主机观察记录及哈希来源清单；已发布的 C25–C28 历史资料不重复复制，Windows `System Volume Information` 和 metadata/misc 原始分区镜像不公开。

## 设备状态与下一步

第二次 `fastboot boot` 后设备重新进入 Standalone USB Mass Storage 模式。最新主机查询看到 G: `THYME_DIAG` FAT32 卷；`fastboot devices` 和 `adb devices` 均无目标设备。故目前不能称设备为主机确认的 Bootloader Fastboot。没有对设备再发送命令。

C29 marker 已提供“Zygote/netd 服务至少被 init 启动且发生过 restart 状态”的线索，但尚未建立顺序、因果或 system_server 启动结果。下一步应先修复/验证 C29 事件采集实际为何没有持久化有效事件数据，再决定是否需要新的 Candidate；在新证据出现前，不盲目改 netd、Zygote critical/secondary callback，也不重复启动 C29。

## 公共证据

本次新增证据副本、来源/发布 SHA-256 清单和脱敏说明见 [Candidate 29 evidence](../evidence/candidate29/first-boot-20260929/README.md)。
