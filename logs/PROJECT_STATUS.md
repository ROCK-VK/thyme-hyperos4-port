# THYME-OS4 项目当前状态

## 目标与阶段

将 Xiaomi 15（dada）的 HyperOS 4 / Android 17 用户空间移植到 Xiaomi Mi 10S（thyme）。当前优先越过第一屏进入 HyperOS 启动画面、设置向导或桌面，外围功能暂缓。
当前阶段：C27 已完成静态门禁并刷入 `super`、`vbmeta_system_a`；随后按单次授权执行 `fastboot set_active a`，A 槽 retry 已从 1 恢复到 7。设备保持 Bootloader Fastboot，C27 尚未启动。

## 最新因果结论

- C26 首个 Zygote PID 1060（helper CLOCK_BOOTTIME 15.426s）及 secondary PID 1061（15.430s）均曾进入 running。netd PID 1046 在 logcat monotonic 14.409s 因 25Q2+ 拒绝 Linux <5.4 而 SIGABRT。
- 14.503–14.509s，PID 1 日志记录向 Zygote 进程组 -1060 与 secondary 进程组 -1061 发送 SIGKILL；约 147ms 后两个 init 服务从 running 转为 stopping。实际 C26 netd.rc 含 netd 重启时重启两个 Zygote 的 onrestart 回调。
- 最有证据支持的解释：netd 因内核门槛崩溃并重启时，init 执行 netd.rc 回调杀掉两套 Zygote。SIGKILL 请求是直接日志证据；Zygote 最终 waitpid 状态/退出码未保存，不能称已取得退出码。
- netd tombstone 属于 /system/bin/netd；其中 ZygotePid:-1 不代表 Zygote 崩溃。无可归属 Zygote 的 tombstone、ART/Java/linker fatal、seccomp、OOM 或 kernel panic 证据。C26 helper 读取 init.svc_debug_pid.* 的 shell AVC 是诊断访问拒绝，不是 Zygote 被 SELinux 杀死的证据。
- C26 logger 约 uptime 52.027s 停止。其输出目录有 shell remove_name AVC，旧 logger 使用 logcat 轮转参数；SELinux 阻挡轮转是最可能解释，但无 logger 子进程退出码/错误，尚未证明。

## K40 定点对照

- Redmi K40 OS4.0.0.8 与 C26 的 netd、netd.rc 和 Tethering capex 完全一致；替换它们没有依据。
- K40 包内 boot kernel 字符串为 Linux 4.19.325，但不是运行时 uname。无 K40 runtime netd 日志。两边 SDK37/vendor API30。
- K40 netbpfload.rc 走默认 bpfloader/wait 路径；C26 有 C14 BPF bypass。该差异不证明 K40 如何处理 netd 的 25Q2/5.4 门槛。运行时差异未知，不推测补齐。

## C27 构建

- 构建目录：work/stage_c27_netd_zygote_cycle_break_20260929_run1/images/；最终报告：work/reports/20260929_C27_NETD_ZYGOTE_CYCLE_BREAK/REPORT.md。
- 以 C26 为基线，只移除 system netd.rc 中 onrestart restart zygote 与 onrestart restart zygote_secondary；保留 netd 自身的 Linux 4.19 拒绝和重启。网络仍可能不可用。
- C26 轮转 logger 替换为 helper 监管的单文件 pipe logger，不轮转/删除；限时 8 分钟，metadata 可用空间扣 12 MiB 后最多 24 MiB；持久记录子进程退出码、信号、stderr、耗时、字节数和停止原因。保留 watcher/C25 sampler；不改 SELinux、ART、内核、图形、fstab、加密或硬件配置。
- 主机验证：EROFS `netd.rc` readback 排除两条目标回调；可达 system init 树 87 个 `.rc` 定点扫描仅找到一份 `service netd` 定义；C27 logger 行为与容量限制经源码核对。system AVB、vbmeta_system descriptor、LP/Super 输入检查及 AArch64 PIE 编译通过；受限刷写脚本 Dry-Run 与实际分区写入通过。
- 实刷镜像：`super` 7,703,595,992 bytes，SHA-256 `2B7A2F055B55AFB0B52B3DEAE9B7963F7923F075D406449F0C5034B5E7236598`；`vbmeta_system_a` 使用 `vbmeta_system.img`，131,072 bytes，SHA-256 `19B1ECD7128874989792C1B3F5173E6F4A8D2E0AC08734D35338AFAD674FA881`。两项实际 Fastboot 写入均返回成功。

## 设备、磁盘与下一步

- C27 刷写前后 Fastboot 均只枚举到目标设备：`product=thyme`、`current-slot=a`、`unlocked=yes`、`is-userspace=no`；当时 A `unbootable=no / successful=no / retry=1`，B retry=7。本轮仅执行一次获准的 `fastboot set_active a` 后，A 为 `unbootable=no / successful=no / retry=7`，B 为 `unbootable=no / successful=no / retry=7`，current-slot 仍为 A。未执行 reboot、清数据或其他分区写入。
- 当前已刷版本：C27 的 `super` 与 `vbmeta_system_a`；C27 尚未启动。未刷其他分区、未擦除 userdata/metadata、未改 misc/BCB、未恢复 PixelOS、未回锁。
- 下一步停点：A 槽启动预算已恢复；等待用户现场确认并明确授权 C27 首次启动。不得自行 reboot。
- 2026-09-29 16:09 HKT 实测 C/D/E 可用空间 77.87/223.45/258.34 GiB；没有触发低于 50 GiB 门槛。Docker 及其任何资产绝对排除。
- 已实机验证的关键修复：C9 Property Contexts、C11 EROFS 元数据、C14 BPF 绕过、C17 ION read/open。完整历史和验证细节查执行记录与各 Candidate 报告。
- C26 原始 logcat/Standalone/主机观察留在本地；公开内容不含 ROM、分区镜像或原始设备备份。

验证级别：C26 因果链来自真实持久 logcat 和当时实际 init 配置；C27 已通过主机构建、镜像静态门禁和两项 Fastboot 分区写入，Android 启动效果尚未验证。构建器对 `dump.erofs --cat` 二进制输出使用文本捕获，因此 manifest 中 helper readback 的 `bytes` 不是原始 ELF 字节数，不将其作为 byte-for-byte ELF 校验。