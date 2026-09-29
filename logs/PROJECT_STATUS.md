# THYME-OS4 项目当前状态

## 项目目标与阶段
将 Xiaomi 15（dada）的 HyperOS 4 / Android 17 移植到 Xiaomi Mi 10S（thyme）。当前目标是突破第一屏进入 HyperOS 后续启动界面。最新 Candidate 为 C28；本轮完成一次真实启动和 Standalone 取证，未构建 C29。

## 当前刷入版本与设备状态
- C28 已刷入 `super` 与 `vbmeta_system_a`；其他启动镜像继承此前版本。
- C28 已执行一次 `fastboot reboot`。启动前 A 槽 `unbootable=no / successful=no / retry=6`。
- 用户报告已手动返回 Bootloader Fastboot；但在该报告后主机复核仍看到 G: `THYME_DIAG` FAT32 UMS 卷，`fastboot devices`/ADB 均无设备。当前 Bootloader Fastboot 与启动后 A/B 状态尚未实测确认。
- 未执行 set_active、刷写、擦除、BCB 修改或 PixelOS 恢复。

## C28 最新实机证据
- console-ramoops 只有一个 Linux 4.19.325 启动实例。约 33.464 秒，PID 1 `init` 写 `/proc/sysrq-trigger`，内核随即 `sysrq triggered crash` panic。
- cmdline 有 `androidboot.init_fatal_panic=true` 与 `androidboot.init_fatal_reboot_target=recovery`。实际栈与 init fatal handler 的 panic 分支相符；触发 fatal signal 的编号/原因未知。没有证据表明 C28 通过 `sys.powerctl=reboot,recovery` 或 `--bad_nv` 正常请求 Recovery；用户本次也未报告进入 Recovery。
- pmsg 记录 5 次 netd SIGABRT；C27 删除的 netd→Zygote callbacks 在 C28 镜像中仍保持删除，但 Zygote 状态未能验证。
- pmsg 还有 PID 1063 `main` SIGABRT，但 executable/cmdline 未留存；是否为 system_server 未知。BootAnimation 有两条日志，SurfaceFlinger 有服务查找 AVC；无显示 present、WMS/SystemUI/HOME 或 boot complete 证据。
- 用户从启动到约 8 分钟报告一直看到第一屏静态小米 Logo（下方 powered by Android），未见 HyperOS 第二屏/设置向导/桌面；ADB 未上线。

## C28 logger 与证据限制
- Standalone 的 THYME_DIAG 首次导出 8 个文件、0 个复制错误；原始文件保留于 `work/reports/20260929_C28_RECOVERY_ZYGOTE_DIAGNOSTIC/standalone_salvage/run_20260929_192136/`。
- metadata 目录通过只读 `ro,relatime,norecovery` 视图导出；可见 14 个旧 C25/C26/C27 文件，未见 C28 文件。由于禁用 journal replay，C28 marker/logger 是否写入仍未知，不能据此断言服务未运行。
- metadata-only 导出缺少顶层 `dmesg_diag_boot.txt`，工具因此非零退出；实际可见 20 个文件校验无大小/SHA 不匹配。附带 `misc.raw` 保留本地未解析、未写入。
- `oops.raw` 是 2024 kernel / Long Press 历史记录，不属于 C28；Standalone dmesg 是诊断环境自己的日志。

## 当前判断与未知项
- 已确认的直接停机路径：init PID 1 收到某个 fatal signal 后走 `init_fatal_panic=true` 的 sysrq panic 路径。
- 尚未确认：fatal signal 编号和来源；PID 1063 身份；C28 logger START/logd 状态；netd 崩溃后 Zygote 是否存活；`sys.powerctl`/Recovery 请求；启动后的 A 槽 retry；实际物理显示 present。
- C28 不是有效的 C27 Zygote 修复验收；不恢复 netd→Zygote callbacks，不因 ClassNotFound alone 修改 Framework。

## 下一步
1. 先让设备从 THYME_DIAG UMS 真正回到可被主机枚举的 Bootloader Fastboot，然后只读读取设备身份与 A/B 状态。
2. 用唯一 sysfs `PARTNAME=metadata` 只读导出完整 metadata 原始副本；只在主机副本检查/replay ext4 journal，尝试恢复 C28 markers、logger status 和 logcat。不得对真实 metadata replay。
3. 若 journal 中也没有 C28 输出，再设计最小诊断变体捕获 init fatal signal/backtrace 和 PID 1063 身份；目前不构建 C29、不重刷、不清数据。

## 固定安全和资源边界
- Bootloader 保持解锁；禁止回锁，禁止擅自修改 persist 硬件分区、modemst、EFS/NV、射频校准、设备身份及 misc/BCB。
- 未经明确授权不清 userdata/metadata；启动新 Candidate 前需用户在场确认。
- C/D/E 任一盘低于 50 GiB 才暂停重型构建/大型提取。最近余量约 77.72/206.15/250.91 GiB；Docker 绝不触碰。
- 公共证据位于 GitHub `evidence/candidate28/first-boot-20260929/`；原始含硬件标识文件仅在本机保存，发布副本按 MANIFEST 标注脱敏/排除。
