# THYME-OS4 项目当前状态

## 目标与当前策略

- 将 Xiaomi 15（dada）的 HyperOS 4 / Android 17 用户空间移植到 Xiaomi Mi 10S（thyme）；优先突破小米 Logo 后的启动阻塞，进入启动动画、设置向导或桌面。
- 采用证据驱动的最小修复集合：合并有直接证据且兼容的修复，不堆叠只有理论依据的变更。
- Redmi K40（alioth，Snapdragon 870）仅作成功移植参考，不盲目复制其设备专属内核、DT、射频及硬件分区。

## 当前 Candidate 与设备状态

- C16 已按用户授权写入 vbmeta_system_a 和 super；尚未首次启动，设备保持 Bootloader Fastboot，等待用户现场确认。
- C16 以 C15 为基线；boot_a、vendor_boot_a、dtbo_a、vbmeta_a 仍是 C13 基线。写入后只读复核设备为 product=thyme、A 槽、Bootloader 解锁、非 userspace Fastboot；ADB 不在线。
- PixelOS A0′ 未在 C16 后恢复，当前健康在线状态未验证。不要将其记作当前系统。
- C15 已成功挂载 F2FS /data，vold 记录 format:0 并建立用户密钥；C16 图形实验无需擦除 userdata/metadata。
- C16 刷写只影响 vbmeta_system_a 与 super；未重启、未擦除数据、未改动其他分区或 Bootloader 状态。

## C15 最近实机证据

- 本地原始取证目录：work/reports/20260926_CANDIDATE15_FIRST_BOOT/standalone/run_20260926_174212/。console、pmsg、Standalone 状态、Standalone dmesg、oops 数据及校验文件均导出；Standalone dmesg 属于诊断内核，oops.raw 不归属为 C15 启动日志。
- 一个可见 Android 启动实例进入 first stage（1.895 秒）、enforcing second stage（3.168 秒）；APEX Bootstrap 激活 4 个核心 APEX（3.541 秒）。console 延伸至约 156 秒，pmsg 覆盖约 151 秒。
- 未见 C13 NetBpfLoad / bpfloader-failed；C14 BPF 绕过在 C15 仍有效。
- SurfaceFlinger 仍反复以 no suitable EGLConfig found 中止（C15 记录 28 次）。C15 有 persist.graphics.egl=angle 和 ANGLE 库，但 pstore 未证明 ANGLE 实际被选择。
- C14、C15 均有 hal_graphics_allocator_default 对 ion_device 缺少 read 的 enforcing AVC。C15 首次 EGLConfig abort 早于该 AVC，故该拒绝是直接缺陷，但是否为首个 EGL 故障根因尚未证明。
- 多次 netd SIGABRT 未证明导致整机复位；不纳入 C16 补丁。
- 详细证据见 work/reports/20260926_CANDIDATE15_FIRST_BOOT_AND_CANDIDATE16_GRAPHICS_ALLOCATOR_FIX.md。

## Candidate 16 已写入镜像与刷写结果

- C16 基于 C15，唯一策略修改 system_ext_sepolicy.cil：允许 hal_graphics_allocator_default 对 ion_device 字符设备执行 read。保留 C14 BPF bypass、C15 ANGLE 属性及 C13 Keymaster/Gatekeeper 规则。
- 新建 system_ext EROFS、匹配的 vbmeta_system 与 super。刷前镜像大小与 SHA-256 核验通过；EROFS、规则回读、既有规则与标签、AVB 描述符关系、LP 逻辑分区和受限刷写脚本检查通过。
- vbmeta_system_a：131,072 字节，SHA-256 24AA0C2971ECA3E2B88F01DBB4E7285834A30AA20498713712DEF8333BC8AAEC；Fastboot send/write 均为 OKAY。
- super：7,684,274,964 字节，SHA-256 888988A0D9E5307F751B718D573032A14DE4B80A2F47223FB34D5BC8EFEFC6C8；sparse 1/10 至 10/10 全部返回 OKAY，流程成功结束。
- C16 尚无真机启动结果。图形分配器 AVC 是否消失、ANGLE 是否被选中、SurfaceFlinger 是否获得 EGLConfig、是否进入启动动画均待首次启动验证。

## 继承与边界

- C9 Property Contexts 去重；C10 WarmDtb/Standalone 取证；C11 system_ext EROFS 元数据/xattr；C12 /dev/ion 标签实机验证；C13 Keymaster/Gatekeeper 策略主机侧验证、真机 HAL 效果未验收；C14 绕过 BPF loader 重启点；C15 证明进入 second stage、APEX 及 /data 挂载但未显示启动界面。
- C13 的 Keymaster/Gatekeeper ion_device allow 规则仍未通过相应 HAL 阶段的真机验收。C13.1 未上机。
- Bootloader 必须保持解锁；禁止回锁、EDL/9008、跨槽试验，以及未经授权修改 persist、modemst、EFS/NV、misc/BCB、userdata、metadata 等分区。

## 下一步

1. 等待用户确认已在现场观察，再启动 C16。启动前先运行只读观察器并确认 ARMED、Candidate 标签为 C16，再执行一次 Fastboot reboot。
2. 若进入 HyperOS 动画/设置向导/桌面，优先保留启动状态并采集可得证据，不主动重启。
3. 若失败，等待用户手动回到 Fastboot 后，先完整保存本轮 Standalone 诊断卷文件并核验副本；再分析 Candidate 日志，不自动恢复 PixelOS。
4. 不清 userdata/metadata；不修改非授权分区。

## 公开仓库

- 仓库：https://github.com/ROCK-VK/thyme-hyperos4-port
- C16 报告、构建/刷写脚本和项目资料已公开；内容提交 4b45a185a48dfef9aed1fb535ab61ba625576bc0。C16 实际刷写结果已记录并随本轮日志同步公开；不公开镜像、原始 pstore/oops、设备备份或身份资料。