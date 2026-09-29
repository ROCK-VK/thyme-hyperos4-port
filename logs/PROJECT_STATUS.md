# THYME-OS4 项目当前状态

## 项目目标与阶段
将 Xiaomi 15（dada）的 HyperOS 4 / Android 17 移植到 Xiaomi Mi 10S（thyme）。当前要定位 C29 第一屏后的 Android 启动阻塞；还没有 system_server、Framework/UI 或 C29 fatal 的直接证据。

## 当前 Candidate 与实机状态
- C29 已刷入并只正式启动过一次；用户全程看到静态 Xiaomi Logo，ADB 未上线。
- 启动前 A 槽 retry=5；启动后最后读回 A retry=4、unbootable=no、successful=no。B retry=7 未变。没有执行 set_active。
- 经授权使用 `fastboot boot` RAM 启动 Standalone pstore 诊断镜像后，当前主机看到 THYME_DIAG USB Mass Storage；Fastboot/ADB 目标设备未枚举。因此当前 Bootloader Fastboot 尚未由主机确认。

## C29 新证据
- metadata 主机副本 journal recovery 找回 init markers：primary/secondary zygote 和 netd 曾进入 running；primary zygote 与 netd 也曾进入 restarting；C29 logcat service 曾 stopped。
- markers 无可靠顺序时间；event log 和 logcat status 文件为 0 bytes。无 system_server PID、fatal backtrace、boot-complete 状态或 C29 Android pstore 记录。
- 专门 pstore 采集成功，记录数 1：console-ramoops-0。内核与 Standalone 自身标记证明它属于前一 Standalone 会话；没有 pmsg。Standalone dmesg 不是 Candidate 启动日志。
- 两次 metadata raw 的设备端/主机哈希各自匹配，raw 间有 8 字节差异，原因未确定；恢复出的 C29 marker 与空输出逐字节相同。raw metadata/misc 仅保存在本地。
- 本地报告：`work/reports/20260929_C29_PID1_ZYGOTE_FATAL_DIAGNOSTIC/C29_FIRST_BOOT_AND_PSTORE_CLASSIFICATION_REPORT.md`；公开证据：`evidence/candidate29/first-boot-20260929/`。

## 当前判断与下一步
- 可确认 init 服务状态曾到达 Zygote/netd running/restarting；不能确认顺序、因果、system_server 是否 fork，或屏幕停留原因。
- C29 的 marker 成功，helper 已创建输出文件但 event/logcat 内容仍为空；应定点核查 shell 域对 `/metadata/thyme_os4_diag` 的写入/同步权限、文件标签和可得 AVC，解释首条数据为何未留存。无新直接错误前不构建 C30，也不重复启动 C29。
- 如需后续设备操作，先确认 Standalone UMS 已退出且 Bootloader Fastboot 被主机枚举；保持 A 槽，不切槽、不 set_active。

## 已验证继承成果与保护边界
C9 Property Contexts 去重、C11 system_ext EROFS 元数据、C14 BPF 启动门槛绕过、C17 graphics allocator ION open/read 权限，以及 C21–C23 图形启动推进有各自历史实机证据。C29 未改变这些路径。

不回锁 Bootloader；不擅自修改 persist 硬件分区、modemst、EFS/NV、校准或设备身份数据。不无依据清除 userdata/metadata，不写 misc/BCB。

C/D/E 任一盘低于 50 GiB 才暂停重型构建/大型提取。Docker 永久排除，不清理、不压缩、不修改。公开仓库不存放完整 ROM、分区镜像、metadata.raw 或 misc.raw。