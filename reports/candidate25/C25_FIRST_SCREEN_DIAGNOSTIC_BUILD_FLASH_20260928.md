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

## C25 首次启动观察（2026-09-28）

- 主机观察目录：`observations/run_20260928_231358/`。观察器 ARMED 后，2026-09-28 23:14:16 HKT 执行唯一一次 `fastboot reboot`，命令返回 OKAY。观察器运行约 898 秒后自然结束；用户全程看到中央小米 Logo + `powered by Android` 第一屏，没有看到 HyperOS 三点第二屏。ADB 始终未上线。主机 USB/Fastboot 在启动期间大部分时间 absent；约 892 秒时 Fastboot 重新出现，随后 USB present。用户报告是手动进入 Fastboot。A 槽 retry 从 3 降到 2，unbootable=no、successful=no；B 槽保持 unbootable=no、successful=no、retry=7。
- 该观察证明 C25 在完整约 15 分钟窗口内未到达用户可见第二屏；不能据此确定 Framework、bootanimation 或物理显示的具体阻塞，也不能证明 C25 持久诊断服务是否启动。C25 首启结果仍需持久样本读取。

## 首次 Standalone 导出与只读校验器修正

- 第一轮 Standalone RAM 镜像为 `work/standalone_diag_c25_meta_ro_20260928_run2/standalone_diag_boot.img`，大小 201,326,592 bytes，SHA-256 `114C593F59825B745FCB81723D71CA702384976432A943FB9271F422F4E70E26`。设备预检为唯一 thyme、A 槽、解锁、Bootloader Fastboot；A retry=2。`fastboot boot` 返回 OKAY，仅 RAM 启动。
- 唯一 sysfs `PARTNAME=metadata` 匹配到 `/dev/sda18`，Major:Minor 103:2，节点与 sysfs 一致，容量 16,777,216 bytes。ext4 挂载表显示 `ro,relatime,norecovery`；由于旧验证器只接受字符串 `noload`，它在确认源/类型/只读后停止，未读取 metadata 诊断目录，并成功卸载。Linux 4.19 ext4 文档说明 `norecovery` 是不加载 journal 的选项，与此处请求的 `noload` 语义相符；因此该次是选项别名校验缺陷，不是放宽只读边界。
- THYME_DIAG 动态识别为唯一 F: FAT32 卷。全卷复制到 `standalone/run_20260928_233210/THYME_DIAG/`：5 个文件、4,197,876 bytes、1 个目录，大小与 SHA-256 校验 5/5 通过。可见文件包括 `diag_status.log`、4 MiB `misc.raw`、其 SHA 清单及 Windows `System Volume Information` 文件；无 C25 metadata 导出目录，也无 pstore 文件。完整 `misc.raw` 仅保存在本地取证副本，不公开上传。`diag_status.log` 明确记录在 metadata 读取前停止。
- 修正 `tools/build_standalone_diag.py`：保留 ext4、源设备、容量及 `ro` 检查；仅允许 mount table 的精确 token `noload` 或 `norecovery`，并把 requested/actual options 写入校验记录。run3 镜像独立构建于 `work/standalone_diag_c25_meta_ro_20260928_run3/`，201,326,592 bytes，实际 SHA-256 `EB6E47DBEBFB6469EC0178D17F793538A6C0A41FA09DB4DBC5C04034B2AB65E0`。此前执行记录中有一位抄写错误（`...EB6B...`），文件本体及 MANIFEST 均为 `...EB6E...`。最终 ramdisk 解包规则确认，BusyBox ash `-n` 检查通过。

## C25 持久诊断实机结果（run3）

- Fastboot 前置核对只有设备 `[REDACTED_DEVICE_ID]`：product=thyme、A 槽、Bootloader unlocked、非 userspace Fastboot；A 槽 unbootable=no、successful=no、retry=2，B 槽 retry=7。run3 镜像与 MANIFEST 一致后，`fastboot boot` 返回 Sending/Booting OKAY；仅 RAM 临时启动。
- Standalone 唯一识别 `PARTNAME=metadata`：DEVNAME=sda18、uevent major/minor=259:2、设备节点 stat 为十六进制 103:2、容量 16,777,216 bytes；以 ext4 `ro,noload` 请求挂载，实际挂载表为 `ro,relatime,norecovery`。脚本完成只读验证、复制两文件并卸载，没有写 metadata。
- 诊断卷动态识别为 G:（THYME_DIAG/FAT32）。完整复制到 `standalone/run_20260928_234427_meta_ro/THYME_DIAG/`：8 个文件、4,272,050 bytes、2 个目录；逐文件大小及 SHA-256 8/8 一致，枚举/复制错误为 0。卷中没有 console-ramoops、pmsg-ramoops、oops.raw；包含 `diag_status.log`、C25 metadata 导出、misc.raw 与其散列、Windows 系统卷文件。完整 misc.raw 留在本机，不公开。
- C25 导出两份 metadata 文件：`C25_INIT_TRIGGER.txt` 和 `C25_bootdiag_19700120T231537Z_1026.log`；`C25_METADATA_COPY_VERIFY.txt` 记录源/副本字节数和 SHA-256 一致（mismatch=0）。设备时钟显示 1970，C25 时间分析使用 elapsed_ms / uptime_ms，不采用该日历时间。
- 服务验证：init post-fs-data 标记存在；helper 写有 `START ... file=open`，且在文件中持久写入 56 个样本及 84 组 dumpsys 开始/结束记录。第 1 样本 uptime=15.310s 时多项服务尚未可读；其后 55 个约 15 秒间隔样本一致报告：`init.svc.zygote=restarting`、`zygote_secondary=restarting`、`netd=restarting`；system_server、zygote64、SystemUI、HOME、SetupWizard PID 均为 none；SurfaceFlinger 与 bootanimation 持续 running；`service.bootanim.exit=0`，`sys.boot_completed` 为 empty/unreadable。最后样本 uptime=842.681s、collector elapsed=827.404s。日志没有 `COMPLETE`，未达到配置的 900 秒；中断原因不能仅凭现有文件确定。
- Window、Activity、Display 以及 HOME 查询持续返回 service-not-found；SurfaceFlinger 查询成功，显示 HWC display 0、`PresentFences=true`，并列出 `BootAnimation` layer。它证明 compositor/display interface 可查询，不证明一帧成功 present 至物理面板。
- 因 system_server / zygote64 在后续样本均不存在，C25 的直接可见阻塞已收敛为 zygote 服务无法稳定启动；退出原因尚无 logcat/crash 记录。现有 C23/C24 pmsg 有重复 `ZygotePid: -1`，但无明确 `AndroidRuntime`/`ZygoteInit` fatal，不能当作根因。C25 没有采集或导出 logcat。
- 用户观察始终为中央小米 Logo + `powered by Android` 第一屏，未看到 HyperOS 三点第二屏。BootAnimation service/PID/layer 存在，但是否真实显示到物理面板仍未知；zygote/system_server 尚未启动，因此当前优先收集 zygote 退出原因，不改 HWC/GPU。
- C25 helper 记录只到 827.404s 且缺少完成标记。相较用户约 898s 的主机窗口，不能宣称诊断任务完整运行满 15 分钟；最后样本距 helper 配置的 900s 截止还差约 72.6s。
- 下一步应准备最小 logcat/crash 采集增量，优先保留现有 C25 功能条件；获取 Zygote 启动失败首条日志后再定点修复。当前不构建 C26：最新磁盘读数 C=76.91 GiB，低于本项目 80 GiB 重型工作门槛；D=119.58 GiB、E=176.64 GiB。Docker 未触碰。
- run3 后用户报告已手动返回 Bootloader Fastboot；本轮主机 `fastboot devices` 未枚举到设备，因此模式尚未主机确认。run3 期间为 Standalone RAM UMS，THYME_DIAG=G:。未执行持久分区修改、userdata/metadata 擦除、set_active、BCB 修改、PixelOS 恢复或 Bootloader 回锁。

ext4 选项语义参考：[Linux 4.19 ext4 文档](https://www.kernel.org/doc/html/v4.19/filesystems/ext4/ext4.html)。
