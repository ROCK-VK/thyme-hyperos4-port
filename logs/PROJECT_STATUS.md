# THYME-OS4 项目当前状态

## 当前阶段

- 项目目标：将 Xiaomi 15（dada）的 HyperOS 4 / Android 17 用户空间移植到 Xiaomi Mi 10S（thyme），优先越过厂商启动阶段，进入 Android 后续启动、开机动画、设置向导或桌面。
- 当前有效诊断版本：Candidate 14 BPF bootstrap bypass（C14），由已实机测试过的 C13 派生；仅主机侧构建，尚未刷写或启动。
- 当前最明确阻塞：C13 正常进入 Android second stage、APEX bootstrap 和 vold 数据初始化后，Connectivity NetBpfLoad 因 Android 25Q2 要求内核 5.4、而目标内核为 4.19.325，触发 init 的 bpfloader-failed 暖重启。
- 本轮设备测试现象：用户看到小米 Logo、黑屏、Logo 循环，随后手动进入 Fastboot。Standalone RAM 取证已完成；其后主机枚举未发现 ADB、Fastboot 或 THYME_DIAG 卷，当前设备物理模式尚未重新确认。
- PixelOS A0′：救援镜像仍在本地，但 C13 重刷和启动实验后没有恢复 PixelOS；当前没有 PixelOS 在线或健康验证证据。

## 已验证的工程事实

- C13 console-ramoops 目录：work/reports/20260925_CANDIDATE13_LOG_SALVAGE/run_20260926_122358/。
- 此 C13 启动实例在 1.898 秒进入 first stage，1.983 秒开始动态 SELinux policy 编译，2.978 秒进入 second stage；随后 APEX bootstrap 成功扫描 41 个 APEX 并激活 4 个 bootstrap APEX。
- 约 10.56 秒 vold 将 /data 挂载为 F2FS；pmsg 记录 fscrypt system、DE/CE key 创建与安装活动。这不等价于已验证完整凭据解锁、Keymaster/Gatekeeper 长期健康或桌面可达。
- 约 15.96 秒出现 NetBpfLoad 错误；25.911 秒 init 请求 bpfloader-failed 重启，25.924 秒内核记录 warm reset。观察器没有 ADB，故没有实时 logcat。
- 本轮没有看到 C13 进入 Recovery 的证据；Logo 闪烁与该明确暖重启请求相符。
- C13 两条 hal_keymaster/hal_gatekeeper 对 ion_device 的策略规则已进入动态策略输入并走 enforcing second stage；本次 pstore 没有足够的 HAL AVC/服务状态证据，不能算作 ION 权限真机验收。
- C13 本轮没有再次擦除 userdata/metadata；不计划在 C14 实验前重复清理。

## Candidate 14 构建状态

- 镜像目录：work/stage_d_thyme_os4_candidate_14_bpf_bootstrap_bypass_run5/images/。
- 新构建了 system EROFS、system_ext EROFS、vbmeta_system 与 Android sparse super；boot、vendor_boot、dtbo、vbmeta 与 C13 完全相同并从 C13 镜像原样复制。
- 修改范围仅为两个 BPF init 触发文件：跳过不兼容的 bpfloader、netd1shot 和 hyper_bpfloader 自动触发；设置 bpf.progs_loaded=1 并启动 netd，供下一启动阶段诊断。
- SELinux allow、Enforcing、APEX、fstab、userdata 加密、目标内核及设备专属底层均未改动。BPF 程序不加载可能影响网络功能；C14 是启动诊断变体，不代表 BPF 兼容性已修复。
- 新 EROFS 的 fsck.erofs、回读触发段、SELinux 规则保留、vbmeta_system hashtree 描述符和 super LP 元数据检查已通过。具体报告：work/reports/20260926_CANDIDATE13_NETBPFLOAD_FAILURE_AND_C14_BUILD.md。
- 拟写入范围仅为 vbmeta_system_a 和 super。脚本 tools/flash_candidate14_bpf_bootstrap_bypass.ps1 默认 Dry-Run；显式 -Execute 才写入。脚本没有重启、userdata/metadata 擦除、其他分区写入或 bootloader lock/unlock 命令。

## 继承的有效修复与约束

- C9 Property Contexts 去重修复避免 persist.radio.imei Duplicate Prefix 冲突。
- C10 WarmDtb 和 Standalone Diag 取证链可保存并导出 pstore；Standalone 的 dmesg 只代表诊断环境，不能当作先前 C13 日志。
- C11 system_ext EROFS 元数据与 SELinux xattr 修复使 APEX Bootstrap 得以继续。
- C12 已实机确认 /dev/ion 标签为 ion_device:s0；C13 增加 Keymaster/Gatekeeper ion_device 权限，但 HAL 效果仍待实机验收。
- C13.1 fstab 变体未实机验证，当前不作为下一实验镜像。

## 设备操作边界与下一步

- 最近一次已识别 Fastboot 预检在此次启动实验前；之后设备启动失败并经 Standalone RAM 导出。不要将历史 slot/unlocked 读数当作当前值。
- 下一步先重新确认设备处于 Bootloader Fastboot，再对 serial、product=thyme、A 槽、unlocked=yes、is-userspace=no 做只读预检。
- 当前需要用户单独授权后才可依序写 Candidate 14 的 vbmeta_system_a、super；刷完保持 Fastboot。首次启动仍需另一条明确授权。
- 失败后如需新的 Standalone RAM 临时启动，也须取得相应授权；日志保存完成前不恢复 PixelOS。
- 严禁回锁 Bootloader；未经单独授权不擦除 userdata/metadata，不修改 persist、modemst、EFS/NV、射频校准、设备身份或 misc/BCB。
- 当前源码、C14 主机成品与设备上运行版本并不一致：设备最近运行的是 C13 测试流程；C14 尚未部署。
