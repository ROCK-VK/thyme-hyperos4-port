# THYME-OS4 项目当前状态

更新时间：2026-09-29（香港时间）

## 目标与当前阶段

将 Xiaomi 15（dada）的 HyperOS 4 / Android 17 用户空间移植到 Xiaomi Mi 10S（thyme）。当前目标是尽快越过第一屏，进入 HyperOS 动画、设置向导或桌面；外围功能暂缓。

当前 Candidate 为 C25。一次约 898 秒的观察中，用户始终看到中央小米 Logo + `powered by Android` 第一屏，ADB 未上线，未看到 HyperOS 三点第二屏。C25 持久诊断服务已确认启动并写入 `/metadata/thyme_os4_diag`。

## 已验证的 C25 结果

- Standalone run3 只读导出 metadata 成功：唯一 sysfs metadata 分区容量 16 MiB，ext4 以 `ro,noload` 请求挂载，挂载表显示 `ro,relatime,norecovery`；只复制诊断子目录后卸载。
- C25 helper 写入 56 个样本；其中 55 个连续样本显示 zygote/zygote_secondary/netd 为 `restarting`，system_server/zygote64、SystemUI、HOME、SetupWizard PID 均不存在。SurfaceFlinger 与 bootanimation 持续运行，`service.bootanim.exit=0`；Window/Activity/Display 查询返回 service-not-found。
- SurfaceFlinger 可列出 HWC display 0 和 BootAnimation layer；这不是成功物理面板 present 的证据。没有 C25 logcat/crash 信息，Zygote 退出原因未知。采样最后 uptime=842.681s、helper elapsed=827.404s，没有 COMPLETE，不能说采样跑满 900 秒。
- C25 未见此前 EGLConfig、Vulkan RenderEngine 初始化、shader-cache output-buffer 或 graphics allocator ion_device AVC 阻塞。

## 设备与构建状态

- C25 写入的分区为 `super` 和 `vbmeta_system_a`，Fastboot 命令均成功；未做分区回读。boot、vendor_boot、dtbo、vbmeta_a 沿用前版。
- 启动前 A 槽状态：unbootable=no、successful=no、retry=3；启动后 retry=2。B 槽最后记录 retry=7。此后未复核 A/B。
- 用户报告已手动返回 Bootloader Fastboot；最新主机只读 `fastboot devices` 返回 0 台，故当前设备模式尚未由主机确认。PixelOS 未恢复；未执行 userdata/metadata 清除、slot 操作、BCB/misc 写入或 Bootloader 回锁。
- C25 报告及完整、去标识的本轮可公开证据：[C25 报告](../reports/candidate25/C25_FIRST_SCREEN_DIAGNOSTIC_BUILD_FLASH_20260928.md)、[Standalone 与主机观察证据](../evidence/candidate25/run_20260928_234427_meta_ro/)。完整 `misc.raw`、散列和未脱敏原件仅本地保留。

## 空间与下一步

- 最新 C/D/E 可用空间：76.91 / 119.56 / 176.47 GiB。C 低于项目重型工作门槛 80 GiB；暂不启动 C26 重型构建。D/E 直接项目清理盘点：E 上 C13.1 未上机旧 stage 44.42 GiB 仍存在，删除请求被执行策略拒绝；D 上 Ubuntu VHDX 164.64 GiB，此前压缩因占用失败，本轮未重试。Docker 未访问或修改。
- 下一步先恢复主机 Fastboot 枚举，再准备最小 Zygote 首次退出原因采集（logcat/crash/进程启动错误）；取得首条真实错误前不盲改 Framework/GPU/HWC。
- 重型构建前按空间门禁检查 C/D/E 并仅清理确认属于本项目且获准的目标；不要触碰 Docker。