# C32-DIAG 首次实机结果与 Unified First-Response 取证

- 状态：完成一次 C32-DIAG 首启与一次 Unified First-Response Standalone 全量取证；没有形成 Android 启动修复。
- 设备边界：没有刷写、set_active、擦除或恢复 PixelOS。C32 不再重复启动。

## 实验时间线与设备状态

- 启动前：唯一目标设备为 thyme，A 槽，Bootloader 解锁，非 userspace Fastboot；A 为 unbootable=no、successful=no、retry=2，B 为 no/no/retry=7。
- 观察器先 ARMED。唯一一次 fastboot reboot 于 2026-10-01 14:29:35.333 UTC 返回成功。
- 主机时间线在 14:38:01.484 UTC 再次检测到 Bootloader Fastboot，距启动命令约 506.15 秒（8 分 26 秒）。稍后的启动后槽位读取仍是 A；用户报告屏幕保持 Xiaomi 第一屏（小米 Logo + Powered by Android），没有报告第二屏、动画、设置向导或桌面。ADB 全程未上线，实时 logcat 文件为 0 字节。
- 屏幕口述与主机 Fastboot 重新枚举时间没有严格同步，不能据此断言设备在 Fastboot 重现时屏幕仍显示何种画面，也不判断该次 Fastboot 返回是自动还是实体按键导致。
- 启动后 A 槽为 unbootable=no、successful=no、retry=1；B 为 no/no/retry=7。当前实时只读查询仍为 product=thyme、current-slot=a、unlocked=yes、is-userspace=no，手机保持 Bootloader Fastboot。 Standalone 返回后再次保存了完整只读回读：`evidence/candidate32/standalone/firstboot/run_20261001_224407/observer/fastboot_state_after_standalone_user_return.redacted.txt`。

## 完整取证与校验

Unified First-Response Standalone 的首轮 RAM 启动先捕获 Candidate pstore，再 raw-copy metadata 和 misc、记录 Standalone 自身 dmesg，并完整复制 THYME_DIAG。原始副本位于：

reports/c32_diag_zygote_domain_canary_20261001/standalone/run_20261001_224407/

- THYME_DIAG 中 13 个文件/目录项全部复制；复制错误为 0。主机清单复核 13/13 项的文件大小和 SHA-256 一致。
- console-ramoops-0：1,968,841 bytes，SHA-256 835CB9AD383AC389A14763F3917C1197D241879A56EFA6A900729F5B204E079C。
- pmsg-ramoops-0：1,074,295 bytes，SHA-256 4F0965E425256C508D1BD5766D124D7002D70FAD52229B1F9BF0F05D5238CE06。
- metadata.raw：16,777,216 bytes，源与副本 SHA-256 均为 3DEA9B7DDAD1BA3C2F9FBB12B4D3A5B46BA8C20C32D5D24E31684357013A844D。
- misc.raw：4,194,304 bytes，源与副本 SHA-256 均为 2988E9FEAEC8C2C1BFEFF1ED924E90F98C84E14C98EFCC4B48F8D3EC6D778F51。
- standalone_dmesg.txt 是 Standalone 自身内核日志，不作为 C32 Android 日志。pstore/status、metadata/misc 的容量和只读复制结果见同目录原始 diag_status.log、manifest 与 salvage timeline。

## Canary 结果

- C32 console 在 uptime 16.966524 秒记录 init marker：tombstoned=running。
- pmsg 中出现 canary 自身 tombstone：Executable=/system/bin/c32_zygote_canary，PID 1453、PPID 1、UID 0，SIGABRT，abort message 为 THYME_C32_CANARY_ABORT；回溯包含 libc abort、canary main、__libc_init 共 3 帧。这证明该 init 启动的普通 native abort 产生了可读 tombstone。
- C32 静态构建检查确认 canary 文件使用 zygote_exec context，且合并策略存在 init → zygote 的 type transition；service 没有显式 seclabel。但该 tombstone 文本没有 SELinux label，canary 自己的 START/PID/DOMAIN 日志以及 init trigger/running/stopped marker 没进入 pstore。因此运行时 domain 仍未直接确认，不能把预期 zygote domain 写成实测结论。
- console 仅保存 event=boot tombstoned=running；pmsg 没有 THYME_C32_CANARY_START、PID、DOMAIN_EXPECTED。可确定 canary 执行并留下 tombstone，无法从现存日志确定其完整 init 生命周期或标签。

## 实际 Zygote 崩溃对照

- console uptime 15.541006 秒的 C31DIAG marker 给出 primary zygote PID 1068、secondary PID 1069、netd PID 1059。
- pmsg 的 primary PID 1068 有 UltraFrameworkComponentFactoryImpl ClassNotFoundException 记录，之后出现 SIGABRT；约 30 ms 后同 PID 出现 crash_dump helper failed to exec, or was killed。该 ClassNotFound 与 abort 有时间关联，但没有 abort message/backtrace，不能确认是根因。
- pmsg 中 98 个 comm=main SIGABRT PID 包含 canary PID 1453；其余 97 个真实 main PID 与 97 条 crash_dump helper failure 的 PID 集合逐一相同。canary PID 1453 是唯一不匹配的 main SIGABRT，也唯一具有固定 abort message 和可读 tombstone。该差异支持 crash-dump 问题与真实 Zygote 进程上下文有关，而不是全局 crash_dump/tombstoned 完全不可用；由于 canary 的运行时 SELinux label 缺失，尚不能把差异归因到特定机制。
- 同份 pmsg 另有 97 个 netd SIGABRT 和 96 个进程名截断为 android.hardwar 的 SIGSEGV。它们不是当前 Zygote abort 根因的直接证据。
- pmsg 的 realtime 日期处于 1970 年，绝对日期不可信；使用 console uptime 和 pmsg 内部记录顺序，不把 pmsg 墙钟当作真实日期。
- 这次 pstore 没有捕获 PID1 sysrq/kernel panic 记录。没有证据显示 C32 到达 system_server、SystemUI、SetupWizard、Launcher 或 sys.boot_completed。

## 结论与下一步

1. C32 确认：普通 init 启动的 native canary 能产生完整固定 abort tombstone；真实 primary Zygote PID 的 crash handler 仍持续报 helper exec/killed。
2. C32 没有确认 canary 运行时 SELinux domain，也没有给出真实 Zygote 的 abort 首因；不据此增加 SELinux 权限，不构建正式修复。
3. 下一步优先定点比较 canary 与真实 Zygote 的 crash handler 运行上下文，并寻找不改变安全策略即可留出真实 Zygote abort/backtrace 的方法；不能再重复 C32。
4. 当前 A retry=1。不要再启动 C32或执行 set_active；后续实验需先解决启动预算边界并等待新 Candidate 启动确认。

GitHub 公开副本对 console、Standalone dmesg、diag_status 和主机 USB 记录中的设备序列号/CPUID 做了脱敏；本地原件保持未修改。metadata.raw、misc.raw、ROM/分区镜像和设备备份不公开。
