# THYME-OS4 项目当前状态

## 目标与阶段

将 Xiaomi 15（dada）的 HyperOS 4 / Android 17 用户空间移植到 Xiaomi Mi 10S（thyme）。当前优先越过第一屏进入 HyperOS 启动画面、设置向导或桌面，外围功能暂缓。
当前阶段：C26 Zygote 首次停止原因已从离线证据收敛到 netd 重启回调；C27 已构建并通过主机验证，尚未刷写或启动。

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
- 主机验证：EROFS readback、system AVB、vbmeta_system descriptor、LP/Super 输入检查及 AArch64 PIE -Wall -Wextra -Werror 编译通过；刷写脚本 Parser/Dry-Run 通过。
- 待刷 super：7,703,595,992 bytes，SHA-256 2B7A2F055B55AFB0B52B3DEAE9B7963F7923F075D406449F0C5034B5E7236598。待刷 vbmeta_system.img（目标 vbmeta_system_a）：131,072 bytes，SHA-256 19B1ECD7128874989792C1B3F5173E6F4A8D2E0AC08734D35338AFAD674FA881。Dry-Run 只计划顺序写这两个目标。

## 设备、磁盘与下一步

- 最近可靠 A/B 状态（C26 启动后）：A unbootable=no / successful=no / retry=1；B retry=7。本轮没有 set_active 或其他 boot-control 修改。
- 本轮 fastboot devices -l 无设备输出，当前设备模式/槽位无法重新确认；最后确认写入版本是 C26，C27 尚未刷写/启动。
- 本轮未启动 Candidate、未运行 Standalone、未刷写、未擦除 userdata/metadata、未改 misc/BCB、未恢复 PixelOS、未回锁。
- 下一步：设备重新枚举后只读核验唯一 thyme、Bootloader Fastboot、A 槽、unlocked、is-userspace=no 和 retry；通过后刷 C27 super、vbmeta_system_a 并保持 Fastboot。C27 首启前须单独授权恢复 A 槽启动预算，且另需用户现场启动确认；不得自行 set_active a。
- 2026-09-29 15:42 HKT 实测 C/D/E 可用空间 77.87/223.45/258.34 GiB；低于 50 GiB 才做项目空间治理。Docker 及其任何资产绝对排除。
- 已实机验证的关键修复：C9 Property Contexts、C11 EROFS 元数据、C14 BPF 绕过、C17 ION read/open。完整历史和验证细节查执行记录与各 Candidate 报告。
- C26 原始 logcat/Standalone/主机观察留在本地。本轮公开仅同步去标识报告、工具和文本清单，不同步 ROM、镜像或原始设备备份。

验证级别：C26 因果链来自真实持久 logcat 和当时实际 init 配置；C27 目前只有主机构建/静态验证，尚无刷写或实机验证。