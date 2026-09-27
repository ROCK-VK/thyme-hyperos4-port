# C23 Recovery 原因核查与 A 槽复验准备

日期：2026-09-27（香港时间）

## 结论

C23 保存的 console 从 Init First Stage 起属于 Recovery 分支，没有 C23 普通 Android 用户空间日志。恢复界面显示 PixelOS，不代表当前 C23 的 super 已被 PixelOS 替换：对 C23 vendor_boot 与 PixelOS A0′ 基线解包后，Recovery 属性、recovery 可执行文件、recovery.fstab、Recovery init 配置及两个 Recovery UI 库的 SHA-256 逐文件一致；本轮 C23 只更新了 super 与 vbmeta_system_a。

C23 vendor_boot 的命令行含 androidboot.init_fatal_reboot_target=recovery，表明 Init fatal 后转入 Recovery 是实际可行路径。保存的 C23 console 没有普通 Android fatal 现场，所以这只是有证据支持的路径，不是本次进入 Recovery 的已证实原因。Recovery 启动后记录 bootonce-bootloader 并清除 BCB；这不能还原最初启动原因，也不能证明此前一定进入过普通 Android。

## BCB 与 A/B 状态

使用 Standalone RAM 环境按唯一 PARTNAME=misc 只读读取 misc，并只解析 BCB 前 2 KiB。command、status、recovery、stage 均为空；没有 boot-recovery 或清数据相关字段。此结果来自 Recovery 已运行并清 BCB 之后，不能还原启动前瞬态内容。完整 4 MiB misc 原始副本仅本地保留，不公开上传。

最后一次刷前状态为 A 槽 retry=1、unbootable=no、successful=no；B 槽 retry=7。用户本轮明确授权后，仅执行一次 fastboot set_active a，命令返回 OKAY。复查后 A 槽 retry=7、unbootable=no、successful=no，当前槽仍为 A，设备保持解锁的 Bootloader Fastboot。没有重新线刷 PixelOS、没有清 userdata/metadata、没有修改 BCB，也没有启动 C23。

## 下一步

C23 的 Recovery 原因仍未确定；C23 的图形初始化和 service.sf.prime_shader_cache=0 仍未实机验证。只读观察器已准备为 C23-retest。等待用户确认在手机旁后，先启动观察器并确认 ARMED，再进行一次 C23 受控启动；若再次进入 Recovery，不确认清数据菜单，先保存现场。

完整 misc.raw、Standalone 诊断卷原始副本和包含设备标识的原始诊断状态保存在本机，不包含在此公开报告中。
