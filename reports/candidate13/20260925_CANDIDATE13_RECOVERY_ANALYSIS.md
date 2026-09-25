# THYME-OS4 Candidate 13 Recovery 异常与 PixelOS 安全恢复报告

- 日期：2026-09-25（Asia/Hong_Kong）
- 范围：C13 pstore、Standalone 导出、主机 USB/Fastboot 时间线、C12/C13 引导镜像与策略差异、当前 Fastboot 只读状态、BCB 获取方案。
- 本轮设备操作：未启动手机或 Standalone，未刷写、擦除、格式化、写入 misc/BCB。
- 原始证据：work/reports/20260925_CANDIDATE13_LOG_SALVAGE/run_20260925_165614/
- 设备身份/状态：[REDACTED_DEVICE_ID] / thyme；bootloader Fastboot，A 槽，已解锁。

## 结论摘要

保存的 console-ramoops 中只有一个可见 Candidate 启动实例。该实例的 init 第一阶段一开始便记录处于 Recovery 分支；其中没有普通 Android 正常挂载、核心服务启动或之后失败重启进入 Recovery 的证据。Recovery 随后收到带清数据确认提示的参数，并在 Recovery 用户空间写入 boot-recovery BCB。这证明本次 Recovery 的输入和写入结果，不证明启动前 BCB 已有相同命令，也不确定最初是谁选择了 Recovery。

用户补充：手动进入 Fastboot 时曾短暂看到“像 PixelOS Recovery”的界面及几行未读文字。该观察与 pstore 中 Recovery 用户空间已运行相符，但界面来源和文字内容无法确认。按已记录时间顺序，该观察发生在 PixelOS 救援镜像恢复之前；不能单凭外观认定它就是 PixelOS 分区启动的 Recovery。

当前 BCB 原始内容未知。Fastboot 不能提供已确认可用的只读 misc 获取能力；现有 Standalone 也不读取 misc。PixelOS A0′ 六分区已恢复，但尚未正常启动。未确认 BCB 安全前不启动 PixelOS，也不清除整个 misc。

## 1. Recovery 日志（问题 A–G）

### 启动实例计数

console-ramoops-0 有 1,982 行、约 147,496 字节。计数为：

| 标记 | 次数 |
|---|---:|
| Linux version | 1 |
| Kernel command line | 1 |
| init first stage started | 1 |
| init second stage started | 1 |
| recovery: Boot command | 1 |
| recovery: Writing BCB | 1 |

printk uptime 从 0 单调递增到约 6.992 秒，没有归零或第二组 Linux/init 起点。因此此文件只有一个可见 Candidate 启动实例；这不能证明物理启动期间没有其他未被 pstore 保留的尝试。dmesg_diag_boot.txt 是之后 Standalone Diag 自身的独立内核启动，不能并入 Candidate 的启动计数。

### 事件顺序

| console uptime | 事件 | 结论 |
|---:|---|---|
| 0.000 s | Linux 4.19.325-perf-g45b9b954f074 | 与历史 A5 内核版本相符 |
| 2.064 s | unable to open an initial console | 在 init 第一阶段前，日志未将其关联为 Recovery 原因 |
| 2.065389 s | init first stage started | 第一个可见 init 起点 |
| 2.065457 s | First stage mount skipped (recovery mode) | 第一条明确表明 init 已处于 Recovery 分支的记录 |
| 2.084 s | Invalid hash size / Failed to verify vbmeta digest | 发生在上述 Recovery 记录后，不能据此认定为进入 Recovery 的触发原因 |
| 2.0889 s | system_ext_a、product_a：DM_DEV_STATUS No such device or address；Could not update logical partition | 在跳过正常 first-stage mount 之后 |
| 2.162807 s | init second stage started | 同一 Recovery 启动继续 |
| 3.300096 s | recovery: Boot command: boot-recovery | Recovery 用户空间已运行 |
| 3.300131 s | Recovery 收到 /system/bin/recovery、--prompt_and_wipe_data、--reason=fs_mgr_mount_all | 实际参数含清数据确认提示 |
| 3.300972 s | Writing BCB boot-recovery recovery | Recovery 在此次运行中写入/更新 BCB |

日志没有显示 userdata 或 metadata 实际被擦除、格式化，也没有显示 wipe 已被确认。不得确认任何清数据提示。

Recovery 分支记录之前存在若干 SCM、PON、可选调节器、I2C、显示/触控/传感器等硬件探测告警，以及 initial console 提示；未发现能单独解释 Recovery 选择的 init fatal、AVB、fstab、动态分区或 Bootloader 致命错误。这里仅报告日志先后关系，不将未关联的硬件告警认定为无害或根因。

AVB 错误和 system_ext_a/product_a 逻辑设备映射失败都在 init 已报告 Recovery mode 后。此前 C13 主机 LP 元数据检查确认 A 槽逻辑分区定义存在。顺序支持“Recovery 跳过正常 first-stage 挂载后，逻辑设备未建立”这一可能解释，但不能证明其必然只是后果，也不能排除运行时条件差异。参数里的 fs_mgr_mount_all 是 Recovery 收到的原因字符串；不能单独证明此前曾有一次普通 Android mount_all 失败并重启至 Recovery。当前 pstore 没有那次普通启动。

## 2. 用户所见 Recovery 页面

用户记得在按键进入 Fastboot 前短暂看见像 PixelOS Recovery 的页面及几行未读文字。日志确认 Recovery 用户空间确实启动，故该观察与现场相符；但没有照片/视频，无法还原错误文字或识别实际 Recovery 镜像。若观察对应本次 C13 首启后进入 Fastboot 的过程，它早于 PixelOS 六分区救援恢复，故不能按 UI 外观判定系统当时实际运行的是 PixelOS。该观察也不构成普通 Android 曾启动的证据。

## 3. C12 与 C13 引导资产和策略比较

两套 Candidate 的以下镜像逐字节相同：

| 镜像 | 字节数 | SHA-256 |
|---|---:|---|
| boot.img | 201,326,592 | E5A016056D5C93C7A886980A7C062617EC44DC06A48417D7DD0F4476708A6368 |
| vendor_boot.img | 100,663,296 | 02333B82BA936F1BAAB1ECAB744632C70F8FC16688A206C7041EF319F112A137 |
| dtbo.img | 33,554,432 | 50E1AC0EDCBD333778217AA6FE8D972F6FF85ADD0DAE8A015A6642C2172DD886 |
| vbmeta.img | 131,072 | 013335BCA9B312E0BEFF737D30903A9B0A1EF829BA19A7BD5802BF83C04F40E9 |

所以 kernel、ramdisk/recovery 相关内容、DTBO 和 vbmeta 没有 C12→C13 文件差异。unpack_bootimg 对照也确认 boot v3 kernel/ramdisk 尺寸及 vendor_boot v3 ramdisk、DTB、cmdline 一致。vendor_boot cmdline 含 androidboot.init_fatal_reboot_target=recovery，但不含 androidboot.mode 或 androidboot.force_normal_boot。该参数指向 init fatal 后的目标；日志在 Recovery 分支前没有明确的 init fatal 记录，不能据此认定该 fallback 是本次触发原因。

C13 system_ext CIL 与 C12 的差异仅为新增注释和两条规则：

    (allow hal_keymaster ion_device (chr_file (ioctl read getattr lock map open watch watch_reads)))
    (allow hal_gatekeeper ion_device (chr_file (ioctl read getattr lock map open watch watch_reads)))

相关重建资产比较：

| 镜像 | 大小 | C12 SHA-256 | C13 SHA-256 |
|---|---:|---|---|
| vbmeta_system.img | 131,072 | B81437549B2361AD60830A417DCDE28270C8C07456DD57614BE0EAB877D5F5A8 | BF4155CD99F125B8CAD26490FD2F3412EA4389F090CE56F36FAA2BF2A759C633 |
| system_ext EROFS | 942,669,824 | 403930AD84A9A3EB50C7BE4CE0614DEE9E6240CE411B24D7ADAF1065E4F8D987 | 34598E99D7FB63FC52966A620426AB2BCF7280D2CBC51093626488F6BD4A560C |
| super.img | 7,684,274,964 | C111F1A1CF501D484776126285B823367A07BCDE3F464845AB7B29015C8614B7 | 8AFEFDDBCA2357D003DEF055418CC08A832B91EA08EDCB40DEECBEBD42FA2252 |

直接从最终 system_ext EROFS 读取确认 C13 含规则而 C12 不含。可核对的静态差异符合“继承相同引导镜像，仅更新 system_ext 策略并重建 vbmeta_system 与 super”的方案。此次针对性比较没有逐个重新哈希 super 内所有逻辑分区，因此结论限于列出的外层镜像、引导镜像与最终 system_ext CIL 证据。

console 内核命令行打印内容中途截断，不能据其排除 Bootloader 运行时追加的 androidboot.mode、force_normal_boot 或其他参数。引导镜像相同只排除了 Candidate 间的静态文件差异，不排除 BCB、运行时环境、槽位状态或 Bootloader 参数差异。C12 曾到达 Android 核心服务阶段，也不能证明 C13 本次经过普通 Android 路径。

## 4. 主机 USB/Fastboot 时间线

| 本地时间 | 证据 | 限制 |
|---|---|---|
| 16:48 | 执行记录记载 C13 六分区刷写结束并留在 Fastboot | 刷写记录 |
| 16:54:09 | Windows Kernel-PnP 枚举 VID_18D1/PID_D001、序列号 [REDACTED_DEVICE_ID]，启动 WinUSB/OPLUS 驱动 | USB 枚举，不是 Fastboot 命令 transcript |
| 16:56:12 | StorDiag 出现四个非 ReadWrite SCSI SRB 失败请求 | 时间接近 UMS 导出，不能证明发生额外设备写入 |
| 16:56:14–15 | 导出目录创建、SHA 清单最后写入 | 与 Standalone UMS 导出相符 |
| 17:04 | 执行记录标题将取证完成记为 17:04 | 与目录/主机事件时间有差异，保留差异 |
| 17:15–16 | PixelOS A0′ 六分区恢复记录 | 只证明镜像写入，未启动验证 |

没有发现首次 fastboot reboot 的逐命令主机 transcript，USB 时间线不能确定预启动 BCB 内容或每次模式切换命令。Standalone 的设备时间显示 1970 年，不作为可靠主机时间使用。

## 5. BCB 状态与只读获取

### 当前 BCB：未知

Recovery 曾记录写入 boot-recovery recovery；后续 PixelOS 恢复脚本只刷六个授权分区、不触碰 misc。因此存在 BCB 残留风险，但没有原始 misc 读数：既不能说当前仍有该命令，也不能假设已清空。

本轮只读 Fastboot 查询结果：

    serial: [REDACTED_DEVICE_ID]
    is-userspace: no
    product: thyme
    current-slot: a
    unlocked: yes
    partition-size:misc: 0x400000
    getvar:max-fetch-size: Variable not found

misc 分区大小为 4,194,304 字节。设备为 bootloader Fastboot，不是 fastbootd。Fastboot 客户端支持 fetch 并不代表设备端实现了 fetch；AOSP 客户端先依赖 max-fetch-size，再逐块取分区。此设备返回该变量不存在，故没有确认可用的 Fastboot 只读取 misc 路径。本轮没有试发 fetch 或未知 vendor 命令。

### 结构与读取边界

AOSP bootloader_message.h 将 misc 开头 2 KiB 定义为 bootloader_message：command 32 字节、status 32、recovery 768、stage 32、reserved 1,184。misc 后续区域还可能承载厂商/A-B boot control、擦除包及 Android 数据。只解析原始副本的偏移 0–2,047，不重建结构写回，不清零整块 misc。AOSP recovery 源码把读取与写入分为不同实现，读取使用只读打开。

### Standalone 最小读取计划（未执行）

现有 tools/build_standalone_diag.py 和 work/standalone_diag/wsl_build_ramdisk.sh 仅采集 pstore、oops、dmesg，再导出到 64 MiB RAM FAT 镜像；没有 misc/BCB 读取。mass-storage gadget 导出的 RAM 镜像设为主机只读，脚本声明不自动重启。tools/salvage_c13_diag.py 会执行 fastboot boot，故会改变设备运行状态；本轮没有运行。

若用户另行授权，步骤为：

1. 主机侧对 Standalone 做最小采集改动：只检查 /dev/block/by-name/misc 存在、为块设备且大小等于 4,194,304 字节；检查不成立则停止，不猜 sdaN。
2. 只将 misc 原始读入 tmpfs，导出完整 4 MiB，核对字节数和 SHA-256；不挂载 misc，不向 misc 写数据。
3. 将原始副本及状态/哈希放入现有 RAM 导出镜像。主机复制后再核对长度和哈希。
4. 在主机只读解析副本偏移 0–2,047；保存 command/status/recovery/stage 的原始字节、十六进制与可见字符串，原始 4 MiB 文件不覆盖。
5. 临时 RAM 启动和导出后保持 Fastboot。该操作不包含 PixelOS 启动、BCB/misc 修改或分区刷写。

参考资料：

- [AOSP bootloader_message.h：BCB 字段与 misc 布局](https://android.googlesource.com/platform/bootable/recovery/+/refs/heads/main/bootloader_message/include/bootloader_message/bootloader_message.h)
- [AOSP bootloader_message.cpp：只读读取与单独写入路径](https://android.googlesource.com/platform/bootable/recovery/+/98f875e/bootloader_message.cpp)
- [AOSP Fastboot fetch 客户端实现](https://android.googlesource.com/platform/system/core/+/bcd27702071cb12df042883c4b120e9b5ebe5ecb)

若读取发现 boot-recovery、wipe_data、prompt_and_wipe_data 或相关恢复参数：完整保留原始 misc 与哈希，提出只处理必要 BCB 字段的方案并等待单独授权。绝不 fastboot erase/format misc。若 BCB 安全或为空，不改 misc，再单独申请 PixelOS 正常启动授权。

## 6. PixelOS A0′ 当前恢复状态

boot_a、vendor_boot_a、dtbo_a、vbmeta_a、vbmeta_system_a、super 六项救援镜像均经清单校验并成功刷写；super sparse 1/9–9/9 均成功，脚本退出码 0。恢复脚本没有自动重启，也未清除 userdata/metadata。设备留在 Fastboot。

本轮只读查询确认 [REDACTED_DEVICE_ID]、product thyme、slot a、unlocked yes。没有启动 PixelOS，因此 ro.product.device、ro.boot.slot_suffix、sys.boot_completed、ADB 和运行内核版本都无法作为当前 Android 属性重新核验。结论：**PixelOS A0′ 镜像恢复完成，健康启动验证未完成。**

## 7. Candidate 13 实验状态与后续顺序

两条 ion_device allow 规则已在 C13 最终 EROFS 中，目标 HAL 域主机侧权限断言通过；但此 pstore 显示 init 走 Recovery，并在 Recovery 路径加载 monolithic /sepolicy。没有验证动态 system_ext CIL 加载，也未到达 Keymaster、Gatekeeper、QSEECom、vold 或 userdata 解密。ion_device AVC、QSEECom_start_app failed、HAL 稳定性和数据解密均仍待验证，C13 SELinux 实机验收不能记为通过或失败。

后续顺序：

1. 保持 Fastboot，先取得用户对一次 Standalone RAM 临时启动的单独授权，仅用于只读导出 misc/BCB；授权前不启动 Standalone。
2. 对完整 4 MiB 原件验长和哈希，只读解析 BCB；如有 wipe/recovery 命令，保留原件并另行申请最小 BCB 字段修正授权。
3. BCB 确认安全后，另行申请 PixelOS A0′ 首次启动授权。若看到清数据提示，不确认、不自动重试。
4. 验证 PixelOS 健康基线后，再准备 C13 后续实验。首次启动也需单独授权；分别检查策略加载、ION AVC、QSEECom、HAL、vold 和数据挂载。AVC 消失、QSEECom 成功、用户数据解密是不同验收层次。

## 后续状态更新（2026-09-25）

BCB 只读取证结果未改变：原始 misc 已保留，command/status/recovery/stage 为空，未修改 misc。此后用户单独授权 PixelOS A0′ 正常启动；设备已通过 ADB、thyme、A 槽、sys.boot_completed=1、Android 17/SDK 37、预期内核匹配、vold running、加密 /data F2FS rw 挂载及 Verified Boot 属性核验。完整结果见同目录 PIXELOS_A0_PRIME_STARTUP_VALIDATION.md。设备当前不在 Standalone UMS，也不在 Fastboot；Candidate 13 仍未完成 SELinux 实机验收。