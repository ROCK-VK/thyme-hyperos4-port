# THYME-OS4 项目当前状态

## 目标与当前策略

- 将 Xiaomi 15（dada）的 HyperOS 4 / Android 17 用户空间移植到 Xiaomi Mi 10S（thyme）；优先突破小米 Logo 后的启动阻塞，进入启动动画、设置向导或桌面。
- 采用证据驱动的最小修复集合：合并有直接证据且兼容的修复，不堆叠只有理论依据的变更。
- Redmi K40（alioth，Snapdragon 870）仅作成功移植参考，不盲目复制其设备专属内核、DT、射频及硬件分区。

## 当前 Candidate 与设备状态

- C15 已实机启动并由用户观察；屏幕停留在小米 Logo，用户手动进入 Bootloader Fastboot。无 Android ADB 上线，无启动动画、设置向导或桌面验收。
- 最新只读 Fastboot：`product=thyme`、A 槽、Bootloader 解锁、非 userspace Fastboot；ADB 不在线。当前设备留在 Fastboot，无已发现的刷写/恢复后台进程。
- 当前持久分区：C15 `vbmeta_system_a` 与 `super`；`boot_a`、`vendor_boot_a`、`dtbo_a`、`vbmeta_a` 仍为 C13 基线。C16 尚未写入。
- PixelOS A0′ 未在 C15 后恢复，当前健康在线状态未验证。不要将其记作当前系统。
- C15 已成功挂载 F2FS `/data`，vold 记录 `format:0` 并建立用户密钥；下一轮不需要擦除 userdata/metadata。

## 最新 C15 实机证据

- 本地原始取证目录：`work/reports/20260926_CANDIDATE15_FIRST_BOOT/standalone/run_20260926_174212/`。console、pmsg、Standalone 状态、Standalone dmesg、oops 数据及校验文件均导出；Standalone dmesg 属于诊断内核，`oops.raw` 不归属为 C15 启动日志。
- 一个可见 Android 启动实例进入 first stage（1.895 秒）、enforcing second stage（3.168 秒）；APEX Bootstrap 激活 4 个核心 APEX（3.541 秒）。console 延伸至约 156 秒，pmsg 覆盖约 151 秒。
- 未见 C13 `NetBpfLoad` / `bpfloader-failed`；C14 BPF 绕过在 C15 仍有效。
- SurfaceFlinger 仍反复以 `no suitable EGLConfig found` 中止（C15 记录 28 次）。C15 有 `persist.graphics.egl=angle` 和 ANGLE 库，但 pstore 未证明 ANGLE 实际被选择。
- C14、C15 均有 `hal_graphics_allocator_default` 对 `ion_device` 缺少 `{ read }` 的 enforcing AVC。C15 首次 EGLConfig abort 早于该 AVC，故该拒绝是直接缺陷，但是否为首个 EGL 故障根因尚未证明。
- 多次 netd SIGABRT 未证明导致整机复位；不纳入当前补丁。
- 详细证据与时间线见 `work/reports/20260926_CANDIDATE15_FIRST_BOOT_AND_CANDIDATE16_GRAPHICS_ALLOCATOR_FIX.md`。

## Candidate 16 主机侧状态

- C16 基于 C15，唯一修改 `system_ext_sepolicy.cil`：允许 `hal_graphics_allocator_default` 对 `ion_device` 字符设备执行 `read`。保留 C14 BPF bypass、C15 ANGLE 属性及 C13 Keymaster/Gatekeeper 规则。
- 新建 system_ext EROFS、匹配的 vbmeta_system 与 super。EROFS、策略回读、既有规则与标签、AVB 描述符关系、LP 逻辑分区和刷写脚本解析/Dry-Run 均通过主机检查；没有真机验证。
- C16 镜像：`work/stage_f_thyme_os4_candidate_16_graphics_allocator_ion_run1/images/`。准备刷写范围仅 `vbmeta_system_a`、`super`。
- `vbmeta_system.img`：131,072 字节，SHA-256 `24AA0C2971ECA3E2B88F01DBB4E7285834A30AA20498713712DEF8333BC8AAEC`。
- `super.img`：7,684,274,964 字节，SHA-256 `888988A0D9E5307F751B718D573032A14DE4B80A2F47223FB34D5BC8EFEFC6C8`。
- C16 尚未刷写或启动。脚本 `tools/flash_candidate16_graphics_allocator_ion.ps1` 默认 Dry-Run；不得把主机侧通过写成实机成功。

## 继承与边界

- C9 Property Contexts 去重；C10 WarmDtb/Standalone 取证；C11 system_ext EROFS 元数据/xattr；C12 `/dev/ion` 标签实机验证；C13 Keymaster/Gatekeeper 策略主机侧验证、真机 HAL 效果未验收；C14 绕过 BPF loader 重启点；C15 证明进入 second stage、APEX 及 `/data` 挂载但未显示启动界面。
- C13 的 Keymaster/Gatekeeper ion_device allow 规则仍未通过相应 HAL 阶段的真机验收。C13.1 未上机。
- Bootloader 必须保持解锁；无单独授权不得刷写或启动。禁止回锁、EDL/9008、跨槽试验以及对 `persist`、`modemst`、EFS/NV、misc/BCB、userdata、metadata 等未授权目标的写入或擦除。

## 下一步

1. 等待用户授权 C16 的两分区写入：`vbmeta_system_a`，随后 `super`。刷后保持 Fastboot，不自动重启。
2. 用户单独授权后，先启动只读观察器并确认 ARMED，再启动 C16；观察 SurfaceFlinger/EGLConfig、图形分配器 AVC 与屏幕阶段。
3. 若失败，先保留原始启动现场，再按授权 Standalone 流程取证；不清 userdata/metadata，不自动恢复 PixelOS。
4. PixelOS A0′ 未验证在线；如后续要恢复，须在故障证据保存后按相应授权执行。

## 公开仓库

- 仓库：<https://github.com/ROCK-VK/thyme-hyperos4-port>
- 本轮报告、C16 构建/刷写脚本及状态和执行记录待安全筛选后增量同步；不得公开完整镜像、原始 pstore/oops/设备分区备份或身份资料。