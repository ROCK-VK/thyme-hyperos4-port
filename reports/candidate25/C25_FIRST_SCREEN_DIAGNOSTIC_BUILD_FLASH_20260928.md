# C25 首屏 / Framework 显示诊断构建与刷写记录

日期：2026-09-28（HKT）
基线：C24 Framework/UI/display readiness diagnostic
状态：C25 已构建并刷写；仍在 Bootloader Fastboot，尚未首次启动。

## 背景与判断边界

C24 约运行 16 分 43 秒。用户看到的是中央小米 Logo 和 “powered by Android” 的第一屏；用户随后澄清此前展示的 Xiaomi HyperOS Logo/三点图片属于第二屏，不能将两种画面混为一谈。ADB 未上线，C24 的持久采样标记为零，因此 system_server、WindowManager、SystemUI/HOME、BootAnimation 退出、boot-complete 及物理 display present 均仍未知。pmsg 的 BootAnimation 代码路径记录不等于确认一帧已到达面板。

K40 Android 17 成功包的定点复核没有找到可直接解决当前显示断点的通用 Framework/WMS 改动。C23/C24 中 SurfaceFlinger 查询 Xiaomi IMiHwcExtension 的拒绝仍缺少因果证据；缓存的 K40 service context/provider 资料没有建立相同接口的注册—标签—客户端规则链。C25 不加入宽泛 SELinux allow，也不替换 K40 HWC、vendor、boot、DTBO 或面板专属资源。

## C25 实际改动

C25 仅替换 C24 未能形成可验证采样的 logd-only shell 诊断机制：

- 使用 AArch64 原生诊断 helper，由 init 在 post-fs-data 阶段以显式、已存在的 shell SELinux domain 启动。
- 先创建 /metadata/thyme_os4_diag 和 C25_INIT_TRIGGER.txt，helper 随后创建独立日志文件；每条采样同时发往 logd 和持久文件，文件写入执行 fdatasync。
- 约 15 分钟采样：启动属性与关键 PID 每 15 秒；WindowManager、ActivityManager、SurfaceFlinger、display/layers/HOME 等有界查询约每 60 秒。每条查询有 4 秒超时/结果记录；每文件上限 512 KiB，目录总上限 8 MiB。
- 添加限定到该目录的新 SELinux 文件类型和最小读取/查询规则；未添加 default_android_service 访问。
- 继续保留 C23 shader-cache 绕过、C21/C22 图形路径、C13/C16/C17 已验证修复以及 thyme 原内核、vendor、fstab、加密配置。不修改 GPU/HWC、启动参数、userdata、密钥元数据记录或硬件分区。

为失败后读取持久诊断文件，新增独立 Standalone 镜像构建选项 --export-c25-metadata。它从 sysfs 唯一识别 metadata 分区、核对设备号和容量，以 ro,noload 只读挂载并验证 mount 状态，只导出 /metadata/thyme_os4_diag/ 子树后卸载。该镜像只在主机侧构建和静态验证，本轮没有 RAM 启动或读取设备分区。

## 构建与静态验证

- C25 构建目录：work/stage_o_thyme_os4_candidate_25_first_screen_diag_20260928_run5/images/。
- 报告与镜像清单：同目录上层的 BUILD_REPORT.md，以及 images/BUILD_MANIFEST.json。
- 原生 helper 为 AArch64 PIE；仅动态依赖 liblog.so，C++ runtime 静态链接。
- CIL neverallow 检查启用。主机 libsepol 不支持 Android 17 的 functionfs_seclabel policycap；只在临时检查输入中去掉该声明，最终镜像保留原策略声明，且 vendor 不带 precompiled policy，设备 init 使用动态 CIL 路径。
- 新 EROFS fsck/readback、文件与策略内容断言、AVB system footer/hashtree、vbmeta_system system descriptor、LP extent 和继承镜像输入断言通过。
- Standalone 最终镜像解包后的内核和 ramdisk SHA-256 与输入匹配；BusyBox ash 对最终 init 脚本的语法检查通过。它还没有在设备执行验证。
- run1–run4 的构建尝试在发现脚本/断言缺陷后停止，未触及设备且未覆盖旧成品；最终 run5 成功。各尝试目录保留。

## C25 镜像

本轮刷写目标仅为 super 和 vbmeta_system_a。

| 镜像 | 大小 | SHA-256 |
|---|---:|---|
| super.img | 7,702,744,024 bytes | 87022BC2BE868B1A3CF51F2B3A63C377BBA245BCEEA2BB72610D5A3270BDDF1F |
| vbmeta_system.img | 131,072 bytes | 63B03D20B8EF718C70EF36F063DA57EDD858CE9D7570E490AFE48681A89104C7 |

沿用不刷写：boot、vendor_boot、dtbo、vbmeta。以上镜像组合与 C25 manifest 一致；C25 system AVB 描述符与新 system 内容配套，super 使用 C24 其余 logical partition 输入及原 LP 几何。

## 实际刷写与当前设备

刷写前只读预检确认唯一设备 [REDACTED_DEVICE_ID]、product thyme、A 槽、Bootloader 已解锁、非 userspace Fastboot；A 槽 unbootable=no、successful=no、retry=3。

顺序刷写结果：

- fastboot flash super .../super.img：10/10 sparse chunks 全部传输和写入返回 OKAY，总计约 196.471 秒。
- fastboot flash vbmeta_system_a .../vbmeta_system.img：发送与写入均返回 OKAY。

刷后再次确认设备仍为 thyme / A / unlocked / non-userspace Bootloader Fastboot，A 槽仍 unbootable=no / successful=no / retry=3。Fastboot 写入命令成功，但没有分区回读；因此这里只报告命令返回结果，不声称设备端逐字节读回验证。

未执行 reboot、userdata/metadata 清理、set_active、BCB/misc 操作、其他分区写入、PixelOS 恢复或 Bootloader 回锁。

## 下一步

C25 首次启动尚未执行，等待用户现场确认。设备保持 Fastboot；待用户在场并明确表示“开始启动 C25”后，先启动并确认 C25 观察器 ARMED，再执行一次 reboot。观察期间记录屏幕、USB/ADB/Fastboot；若 ADB 未上线或屏幕仍为第一屏，用户返回 Fastboot 后使用新建的 Standalone 只读 metadata 导出镜像完整备份诊断卷及 C25 持久采样，再分析采样服务是否启动、采样轮数和 Framework/display 状态。

观察启动门控已准备：tools/start_candidate25_observed_boot.ps1 只接受新鲜、候选标签正确的 ARMED 记录；默认不 reboot，只有明确传入 Execute 和 UserWatchingConfirmed 才会执行单次 fastboot reboot。PowerShell AST parser 检查通过。观察器调用参数为 --candidate C25-first-screen-diag，输出目录为 work/reports/20260928_C25_FIRST_SCREEN_DIAG/observations。

本报告不把 C25 诊断功能描述为已获真机验证，也不推断当前启动阻塞已解决。
