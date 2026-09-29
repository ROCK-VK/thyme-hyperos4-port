# THYME-OS4 C28 PID 1 Fatal 与 Zygote 重启链调查、C29 决策及刷写报告

日期：2026-09-29（HKT）

## 结论

C28 的直接终止方式已确认：约 33.464 秒时 PID 1 init 向 sysrq 接口写入 crash 字符，随后内核 panic。触发 init fatal handler 的具体 signal、此前的 init LOG(FATAL) 和 userspace backtrace 没有保存在本轮证据中，底层 fatal 根因仍未闭环。

C28 也证实 zygote 曾从 running 进入 restarting，但 marker 没有时间戳，无法还原 primary/secondary 顺序。C29 因此采用仅增加诊断记录的方案，不关闭 zygote critical，也不切断 secondary zygote 的 onrestart callback。C29 已构建并按授权刷写 super 与 vbmeta_system_a；设备仍在 Bootloader Fastboot，尚未启动。

## C28 证据与因果边界

主要证据在 work/reports/20260929_C28_RECOVERY_ZYGOTE_DIAGNOSTIC/，包括首次 Standalone pstore、metadata 原始只读副本和仅在主机工作副本上恢复 journal 后提取的诊断文件。metadata 原始副本保留本机；没有在设备上 replay journal 或写入。

- console-ramoops-0 只有一个可见 Linux 4.19.325 启动实例。约 33.464 秒记录 PID 1 init 写 /proc/sysrq-trigger，随后 sysrq crash 和 kernel panic。
- 同一启动命令行含 androidboot.init_fatal_panic=true、androidboot.init_fatal_reboot_target=recovery。该组合与 init fatal handler 的 panic 终止路径相符，但不能识别触发 signal 或 fatal 起因。
- console/pmsg 没有保存可确认的 signal 编号、触发前 LOG(FATAL) 或 init userspace backtrace。内核栈仅显示 sysrq 写入路径。
- C28 metadata marker 证明 netd 和 zygote 都曾 running、restarting；secondary zygote 只记录到 running。marker 没有时序字段，文件名是固定状态名，不能计算服务重启次数或判定谁先失败。
- pmsg 记录 5 个 SIGABRT 的进程名 main，相关 AVC 的 SELinux 域为 zygote；但没有 PID 对应关系、可用 tombstone 或命令行。因此不能把它们分配给 primary zygote、secondary zygote 或 system_server。PID 1063 的实际身份也未知。
- primary zygote init 配置含 critical window 属性展开，默认值为 off；C28 对应 vendor build.prop 静态内容为 zygote.critical_window.minute=10。故镜像配置强烈指向 10 分钟 critical window，但实际运行时展开值及 critical escalation 是否触发均未采样确认。
- secondary zygote 的配置包含 onrestart restart zygote。这证明存在一条配置上的 secondary→primary 重启路径，不证明该路径在 C28 实际发生。
- C27 删除 netd 的两条 Zygote onrestart callback 在 C28 仍保持删除；C28 记录 netd 重启和 zygote 重启，但没有时间顺序或直接因果记录。netd 崩溃是并发问题，不是已证实的 Zygote 重启触发者。
- C28 的 logcat、zygote event/tail 输出文件为零字节。用户态服务状态只靠无时间戳 marker，导致 PID、顺序、重启次数和 fatal 来源无法闭环。
- C28 panic 后是否自动发生第二次 Android boot：未知。pstore 只有一个可见启动实例；主机记录与用户手动回 Fastboot 相符，但没有足够连续 USB/boot-id 证据证明或排除 panic 后自动二次启动。

## 问题逐项回答

1. PID 1 fatal 的具体 signal：未知。pstore 显示 fatal handler 最终写 sysrq 并 panic，不含 signal 编号。
2. androidboot.init_fatal_panic：C28 运行时 kernel command line 实际记录为 true。
3. fatal handler 前最后一条 init LOG(FATAL)：没有保存，无法确认。
4. init backtrace：没有可用的 userspace backtrace；现存内核栈是 PID 1 执行 sysrq 写入的内核调用栈。
5. zygote.critical_window.minute：C28 实际 vendor 镜像 build.prop 静态值为 10；运行时属性读数缺失，不能声称已实测有效值。
6. Zygote critical escalation：镜像有启用候选配置，按属性加载预期很可能为 10 分钟；是否实际解析为启用及是否触发，未证实。
7. primary zygote restart 次数：未知。5 个 zygote 域 main SIGABRT 记录不等同于 primary 服务 restart 计数。
8. secondary zygote restart 次数：未知。仅有 secondary 曾 running 的 marker。
9. primary 与 secondary 谁先失败：未知。marker 无时间戳，也没有 PID/服务映射。
10. secondary onrestart restart zygote 是否是实际第二重启链：配置存在，但 C28 没有证据证明该 callback 实际触发。
11. PID 1063 身份：未知；现有 pmsg 只留下进程名 main 和 SIGABRT，缺少 executable/cmdline 映射。
12. C28 panic 后自动第二次 boot：未知；未发现直接证据，也不能从单一 console 实例断言没有发生。
13. netd 作用：C28 中 netd 在 libnetd_updatable_init 路径重复 SIGABRT，并记录 restarting/running；netd→Zygote callback 已移除。没有时序证据证明 netd 造成 zygote restart 或 PID 1 fatal。
14. 是否需要 C29：需要。C28 的状态 marker 和 logcat 空文件无法回答关键顺序和进程身份。
15. C29 新增实验变量：仅为诊断留证机制，Android 启动策略保持不变；不修改 critical 配置、secondary callback、netd 行为或 SELinux 策略。
16. A 槽 retry：刷写前、写入时和刷写后均为 5；A unbootable=no、successful=no。B retry=7、unbootable=no、successful=no。
17. C29 报告及工具首次公开同步于 commit 02db3953b0ba11015b3790e50bd22c811e2b7809。

## C29 诊断改动

C29 从 C28 继承现有 system 和启动链，仅以新的 helper/RC 替换 C28 诊断组件：

- init 在 post-fs-data 启动 C29 helper，位于继承的 zygote-start 触发之前；同时用 init property action 写入 netd、primary/secondary zygote、logger、shutdown 和 boot-complete 状态 marker。
- helper 每 10 ms 采样 init 服务状态和 sys.boot_completed/sys.powerctl，记录服务 PID 属性；每 100 ms 扫描 system_server 首次出现的 PID。
- 单一事件文件按 CLOCK_BOOTTIME、kernel boot_id、event、service、PID 追加并 fdatasync；每条诊断记录可按启动实例排序。
- logcat 继续采用 C26 实机曾产生日志的直接 logcat -b all -v threadtime,monotonic -f 路径；单文件、最长 60 秒、最多 8 MiB、不启用轮转，并记录 START、child PID、exec errno、wait status、退出码/信号和停止原因。
- 采样轮询可能漏掉短于 10 ms 的状态跳变；init 独立 marker 是补充通道。内核 panic 可能打断最终状态写入，但已经 fdatasync 的前序事件应保留。
- 此版不是 zygote 修复版，不能预先保证 helper 在设备上成功运行；该结果需要首次实机启动及故障后取证验证。

## C29 构建与受限刷写

构建目录：work/stage_c29_pid1_zygote_diag_20260929_run6/
技术报告：work/stage_c29_pid1_zygote_diag_20260929_run6/C29_PID1_ZYGOTE_DIAGNOSTIC_BUILD_REPORT.md

主机静态验证通过：C++ AArch64 PIE/依赖、EROFS fsck/readback、helper 原始字节 readback、system AVB hashtree、vbmeta_system system descriptor、LP 布局，以及 C28→C29 预期树差异检查。构建与 Dry-Run 均核对了镜像 manifest。

实际写入范围仅为：
- super：7,703,587,800 bytes；SHA-256 A67994F75146E87EB74F772A2BEAF7547BFCC4B31C80C94003239FE6E47BB09D
- vbmeta_system_a：131,072 bytes；SHA-256 A03AFBEDF1A60DDCBC3D0A1F9A391782876F15323F397F108CB8637CEA142A40

super 的 10/10 sparse 块均返回 OKAY；随后 vbmeta_system_a 发送及写入返回 OKAY。刷写脚本结束后及独立回查均确认设备为唯一序列号 [设备序列号已脱敏]、product=thyme、current-slot=a、unlocked=yes、is-userspace=no，仍处于 Bootloader Fastboot。A/B 槽标志与重试预算未变化。没有执行 reboot、set_active、擦除、misc/BCB 写入、PixelOS 恢复或 Bootloader 回锁。

本报告所述内容不构成 C29 已启动或 Zygote fatal 根因已解决的证明。

## 下一步

C29 现已刷入，设备保持 Bootloader Fastboot。启动观察器尚未 ARMED，本 Candidate 尚未启动。必须先由用户确认在场准备观察，然后只启动一次 C29；故障后优先全量保存 THYME_DIAG，再分析有序事件文件、logcat、init marker 和 pstore。只有取得新时序证据后，再决定是否改变 primary critical policy 或 secondary callback。
