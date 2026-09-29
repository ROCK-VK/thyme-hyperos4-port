# THYME-OS4：C29 诊断写入审计与 C30 决策

时间：2026-09-30 00:36 HKT
范围：C29 元数据/SELinux 离线审计、首次响应 Standalone 静态构建、C30 诊断实现与主机侧构建。没有读取或改变设备状态；未刷写、启动 Candidate、set_active、擦除或修改设备分区。

## 结论摘要

- C29 helper 至少运行到动态文件创建阶段。恢复出的 event 与 logcat-status inode 都存在，但逻辑大小和块数为 0；不能据此断言 helper 没有运行。
- 目录和文件的真实 SELinux xattr 均为 `u:object_r:c25_diag_data_file:s0`。C29 merged platform policy 中 shell 对该类型有文件写/追加及目录创建所需权限，type transition 也存在。没有依据继续增加 shell 权限。
- C26 在同一 metadata 诊断目录、相同文件 type 下曾留下 32 KiB events 和约 8.56 MiB logcat；这排除了“该目录/type 一直不能写”这一简单解释，但没有发现足以解释 C26 与 C29 差别的决定性证据。
- C29 现存证据不能区分 `write` 失败、`write` 后 `fdatasync` 未持久化、或 helper 在首个有效 payload 写入前被终止。C30 因而采用独立 canary、Android log 与 init built-in marker，不把失败 errno 再写回同一路径。
- Unified First-Response Standalone run2 已主机侧构建并检查：先只读复制 pstore，再按 sysfs 唯一身份 raw-read metadata 和 misc，另存 Standalone 自身 dmesg，最后生成 manifest 并提供 UMS。它尚未 RAM 启动验证。
- C30 已主机侧构建；neverallow、EROFS readback、fsck、AVB/vbmeta_system 与 LP 输入关系检查通过。C30 未刷入、未启动，运行时 canary 及 Zygote/system_server 顺序未知。

## C29 ext4 inode 与 SELinux xattr

以下 `debugfs stat` 读取的是从两份设备 raw 副本各自生成的 host working copy；journal recovery 只在副本上进行，原始 `metadata.raw` 未修改。两个已恢复目录树中的相关文件内容一致。时间字段来自 ext4 inode，显示为 1970 年设备墙钟；它们不是 `CLOCK_BOOTTIME` 事件序列，不能用来排序服务事件。

| 路径 | inode | size / blocks | UID:GID / mode | crtime | ctime / mtime | 实际 SELinux xattr |
|---|---:|---:|---|---|---|---|
| `/thyme_os4_diag` | 281 | 4096 / 8 | 0:2000 / 0770 | Jan 21 07:15:37 | Jan 22 06:49:01 / 06:49:01 | `c25_diag_data_file` |
| `C29_events_…log` | 311 | 0 / 0 | 2000:2000 / 0660 | Jan 22 06:48:58 | Jan 22 06:49:11 / 06:49:11 | `c25_diag_data_file` |
| `C29_logcat_status_…txt` | 312 | 0 / 0 | 2000:2000 / 0660 | Jan 22 06:48:58 | Jan 22 06:48:58 / 06:48:58 | `c25_diag_data_file` |
| `C29_INIT_LOGCAT_STOPPED.txt` | 316 | 46 / 8 | 0:0 / 0600 | Jan 22 06:49:01 | Jan 22 06:49:01 / 06:49:01 | `c25_diag_data_file` |
| `C29_INIT_NETD_RESTARTING.txt` | 313 | 43 / 8 | 0:0 / 0600 | Jan 22 06:49:01 | Jan 22 06:49:11 / 06:49:11 | `c25_diag_data_file` |
| `C29_INIT_NETD_RUNNING.txt` | 318 | 40 / 8 | 0:0 / 0600 | Jan 22 06:49:01 | Jan 22 06:49:11 / 06:49:11 | `c25_diag_data_file` |
| `C29_INIT_PRIMARY_RESTARTING.txt` | 314 | 45 / 8 | 0:0 / 0600 | Jan 22 06:49:01 | Jan 22 06:49:11 / 06:49:11 | `c25_diag_data_file` |
| `C29_INIT_PRIMARY_RUNNING.txt` | 317 | 42 / 8 | 0:0 / 0600 | Jan 22 06:49:01 | Jan 22 06:49:11 / 06:49:11 | `c25_diag_data_file` |
| `C29_INIT_SECONDARY_RUNNING.txt` | 315 | 52 / 8 | 0:0 / 0600 | Jan 22 06:49:01 | Jan 22 06:49:01 / 06:49:01 | `c25_diag_data_file` |

其中 `…` 代表报告中完整文件名里的 C29 boot ID；完整原名保留在本地取证目录。所有列出的 C29 文件（含 init marker）xattr 均为 `u:object_r:c25_diag_data_file:s0`。

实际 C29 `plat_file_contexts` 将诊断路径映射到 `c25_diag_data_file`。实际 `plat_sepolicy.cil` 存在 shell→该文件 type transition；shell 对文件有 create/open/read/write/append/getattr/setattr，对诊断目录有 search/open/read/write/add_name/getattr。C29 platform CIL 在 secilc policy version 35、neverallow 开启时已通过主机验证。

### 空文件能说明什么

0-byte、0-block inode 证明恢复出的文件系统没有保存 payload；它本身不能证明 `fdatasync` 出错。C29 `EnsureEvents()` 在 `open(O_CREAT)` 后调用 `fchmod` 和目录同步，再尝试首条 `WriteSync`；status 文件在 `OpenUniqueFile()` 后也会 `fchmod`/同步目录，再写首条 status。文件存在和 inode 时间可与“已创建/打开”一致，但没有 errno、AVC、stderr、C29 pstore 或 status payload 可区分：首个 `write` 失败、数据写入后未持久化，或进程在首条 payload 前结束。事件 inode 的 ctime 晚于 crtime，但文件仍为零长度；该时间来自恢复副本的 inode，不足以建立 Android 进程事件顺序。

C26 在同一诊断路径/type 下曾恢复出非空 events（32,768 bytes）和 logcat（8,564,736 bytes）。C26 logcat 里虽有针对旧轮转文件 `remove_name` 的 AVC，主体日志仍然非空。现有材料没有找出 C26/C29 间一个已证实、足以导致 C29 首写失败的差异；不能把 C29 空文件归因为通用 SELinux 写权限缺失。

## Unified First-Response Standalone run2

最终 ramdisk `/init` 经解包只读检查，BusyBox `ash -n` 通过。顺序为：

1. 建立 `/proc`、`/sys`、RAM `/dev`/`/tmp` 与必需字符设备；
2. 只读挂载 `/sys/fs/pstore`，将每个可读文件复制到 RAM，并记录源/副本大小及 SHA-256 对照；
3. 从 sysfs 找唯一 `PARTNAME=metadata`，核对 uevent major/minor、真实块节点类型与精确 16 MiB 容量；只执行 `dd if=metadata` 到 RAM，记录源和副本 SHA-256；不挂载 metadata、不 replay journal；
4. 按现有唯一 `PARTNAME=misc`、major/minor、块设备类型、精确 4 MiB 容量和 by-name 最终目标校验规则只读导出 misc；
5. 单独生成 `standalone_dmesg.txt`，明确标注来自 Standalone 诊断内核；
6. 枚举全部 RAM payload，生成 `FILE_MANIFEST.tsv` / `SHA256SUMS.txt`，再创建 `THYME_DIAG` RAM FAT32 UMS。

镜像：201,326,592 bytes；SHA-256 `ab454793fbe595408b71a905ba176fe4a35e5c4c380439e5114e647a8ceb1dba`。Ramdisk SHA-256 `7c7bbb0231af81f6a174a3c97d92031ca0bbd3acc42afdc8d32a5335dce628d5`。最终 boot 解包中的 kernel/ramdisk 与打包输入 hash 匹配。以上只是主机侧静态验证；没有 `fastboot boot`，没有证明设备 pstore mount 或数据导出实测成功。

## C30 诊断实现与构建结果

C30 从 C29 继承启动行为，只替换诊断 helper/RC，并更新 init import、file/property contexts 和 platform CIL。netd→Zygote restart callback 仍保持删除；primary Zygote critical、secondary callback、netd 版本检查、GPU/HWC、kernel、fstab、加密路径没有随本次诊断改动。

- helper 由 init 执行文件触发 `c30_diag`/`c30_diag_exec` 专用域转换；不再以 shell domain 作为核心路径。
- `secilc -m -M true -G -c 35` 首次确实因泛化 `/proc` read/open 触发 `coredomain proc:file` neverallow。已删除该宽泛授权及 `readproc` 组；只保留读取 boot ID 所需的 `proc_random` 精确权限，system_server PID 改从已采集 logcat 的 `am_proc_start` 或 `SystemServer` 行识别。修正后 secilc/neverallow 通过。
- helper 首先依次执行独立的 create+write、create+write+fdatasync、create+write+fdatasync+append+fdatasync canary。每项 errno/结果发 Android log；init 分别写 post-fs-data、helper running/stopped markers。任一 canary 失败即不启动复杂 watcher/logcat。
- canary 全部通过后，ordered events 使用 CLOCK_BOOTTIME、boot ID、PID 和 O_APPEND+fdatasync，记录 zygote/secondary/netd 状态、system_server 首次 PID、sys.powerctl 与 sys.boot_completed。logcat 捕获 crash/system/main/events，最多 60 秒、无轮转、上限 8 MiB并保留至少 2 MiB metadata 空间；记录 exec/wait/退出码/信号/停止原因。

C30 AArch64 PIE helper、platform CIL neverallow、权限查询、EROFS 内容读回、fsck、AVB system/vbmeta_system 与 LP 非 system 输入关系校验通过。树差异清单中 `unexpected_changes=[]`。镜像结果：

| 镜像 | 字节 | SHA-256 |
|---|---:|---|
| `super.img` | 7,703,591,896 | `071A86171450B5832E2951E63145D0B5AB55AB622BDDEFB249781B819B1CC83C` |
| `vbmeta_system.img` | 131,072 | `D116F268C015382D5B7F0162959563530D1CFAFC368ED7C1D5DF0514743E5C75` |

对应完整构建清单在 `work/stage_c30_diag_write_canary_20260930_run1/images/BUILD_MANIFEST.json`；构建摘要在同 stage 的 `C29_WRITE_AUDIT_C30_BUILD_REPORT.md`。

## C30 运行时项目（均待实机验证）

以下没有 C30 实机数据，不能填写成成功或失败：三个 canary 的运行结果、ordered events 持久写、logcat 持久采集、zygote/secondary/netd 时间顺序、system_server 是否出现、Zygote critical escalation、是否需要 `init.svc_debug.no_fatal.zygote=true`。C30 本轮没有刷写或启动。

最新可靠历史 A 槽为 retry=4、unbootable=no；本轮按范围没有查询设备，所以该值不是本轮实测。设备实际模式也未查询，可能仍为 THYME_DIAG UMS。没有 set_active、Candidate flash/boot、userdata/metadata 操作或 PixelOS 恢复。

## 下一步

C30 的主机侧准备已完成，C29 写入失败原因仍未闭环。后续若另行进入设备阶段，先由用户退出 UMS，再只读确认 Fastboot/设备/槽位状态；经适当的刷写和启动授权后，首次故障后的第一次 RAM boot 必须使用 Unified First-Response Standalone，先拿 pstore，再拿 metadata/misc，全卷复制校验后才分析。C30 的 runtime canary 若不能写，利用 Android log 与 init marker 区分 helper 生命周期和 metadata 写路径；若写入通过，ordered events/logcat 再判断 Zygote 与 netd 因果。取得 C30 证据前，不关闭 Zygote critical、不改 secondary callback。
