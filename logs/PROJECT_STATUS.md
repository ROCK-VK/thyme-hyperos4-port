# THYME-OS4 项目当前状态

## 目标与策略

- 将 Xiaomi 15（dada）的 HyperOS 4 / Android 17 用户空间移植到 Xiaomi Mi 10S（thyme）；优先越过启动阻塞，进入启动动画、设置向导或桌面。
- 采用“证据驱动的最小修复集合”：可以在一个 Candidate 中合并多个有直接证据、彼此兼容的修复；不为形式坚持单变量，也不把只有理论依据的问题一起打包。
- 小米 10S 是目标机，Redmi K40（alioth，Snapdragon 870）提供成功移植参考。K40 的设备专属内核、DT、显示依赖及射频组件不能盲目照搬。

## 当前工程/设备状态

- 当前最新 Candidate：C15 ANGLE EGL 诊断版。已按本轮授权仅将 `vbmeta_system_a` 与 `super` 刷写为 C15；设备刷后仍处于 Bootloader Fastboot，尚未启动 C15。
- 当前持久分区版本：C15 的 `vbmeta_system_a`、`super`；`boot_a`、`vendor_boot_a`、`dtbo_a`、`vbmeta_a` 仍是 C13 基线（C14/C15 均未改动这些引导分区）。C14 曾启动一次；故障后用 `fastboot boot` 临时运行 Standalone 并只读导出 pstore。
- 最近只读复核：设备 `[REDACTED_DEVICE_ID]` 在线，`product=thyme`、`current-slot=a`、`unlocked=yes`、`is-userspace=no`；Fastboot 写入进程已退出。不要启动，除非获得单独的首次启动授权。
- PixelOS A0′ 未在 C14 后恢复或在线验证。
- C14/C15 均未在本阶段重新擦除 `userdata` 或 `metadata`。下一次 C15 方案也不需要擦除。

## 最新实机证据：C14

- 原始文件保存在 `work/reports/20260926_CANDIDATE14_FIRST_BOOT/standalone/run_20260926_153413/`。pstore 原始文件及 SHA-256 清单保存在本地；`oops.raw` 是历史/混合数据，Standalone dmesg 只属于诊断内核。
- console-ramoops 中一个可见 Android 启动实例：first stage 1.788557 秒，second stage 3.044160 秒，kernel console 延伸到约 115.817 秒；pmsg 设备时间从 23:26:13.211 延伸到 23:28:03.891。
- C14 pstore 未见 `NetBpfLoad` 或 `bpfloader-failed`，证明本次启动越过了 C13 已证实的 BPF 暖重启门控；不代表 BPF/网络已修复。
- 最明确的显示阻塞：pmsg 有 20 次 SurfaceFlinger abort，均为 `no suitable EGLConfig found`。这是当前最直接的视觉启动错误。
- 次级错误：graphicsengine 在 MIUI Vulkan pipeline cache 路径空指针崩溃一次；netd 有 14 次 fatal/tombstone，栈在 `libnetd_updatable_init.cfi+576`，无明确 abort message。二者原因及是否阻止显示/完成开机尚未确认，不据此扩大修改。
- ADB 从未上线；没有 `sys.boot_completed=1`、设置向导、锁屏或桌面证据。用户观察到小米 Logo 常亮后手动进入 Fastboot。不能宣称 C14 完成正常开机。
- C14/15 高价值结论与方案详见 `work/reports/20260926_CANDIDATE14_FAILURE_AND_CANDIDATE15_EGL_PLAN.md`。

## Candidate 15 构建状态

- 镜像目录：`work/stage_e_thyme_os4_candidate_15_angle_egl_run1/images/`。
- 构建基线为已实机启动的 C14 run5。C15 保留 C14 BPF bypass，并只增加 `system/build.prop` 属性 `persist.graphics.egl=angle`，尝试 Android 17 系统 ANGLE EGL 路径来解决 SurfaceFlinger 无 EGLConfig 的明确错误。
- 重建 system EROFS、匹配的 `vbmeta_system.img` 与 sparse `super.img`；boot、vendor_boot、dtbo、vbmeta 原样继承 C14。C13 SELinux/ION 规则、fstab、APEX、加密路径和 thyme 硬件底层不变。
- 基础验证：EROFS fsck 成功；build.prop 回读属性正确；AVB system descriptor 匹配 C15 system，product/system_ext descriptors 保留；LP dump 包含必需逻辑分区。脚本 `tools/flash_candidate15_angle_egl.ps1` 已通过 PowerShell 解析和默认 Dry-Run。
- 已实际写入仅 `vbmeta_system_a` 与 `super`。脚本默认仍为 Dry-Run，只有显式 `-Execute` 才刷写；本轮刷前镜像大小/SHA-256、设备身份、A 槽及 Bootloader 解锁状态均核验通过。完成后保持 Fastboot，没有自动启动。
- `vbmeta_system.img`：131,072 字节，SHA-256 `634EB12F681ECFFFF5E07CEF633377F5C16903E32901AFE7B6EF56FE4D5A4190`。
- `super.img`：7,684,274,964 字节，SHA-256 `4CD34B53A7E47E25522C191AC748B8EE91348091C9B0F31FF59EC677CF8C9B56`。
- ANGLE 依赖当前 Vulkan 运行时的风险尚未实机验证；C14 graphicsengine 单次 Vulkan 崩溃是已知风险，不是 ANGLE 必然失败的证明。

## 继承结论与未完成验证

- C9 Property Contexts 去重；C10 WarmDtb/Standalone pstore 取证；C11 system_ext EROFS 元数据/xattr；C12 `/dev/ion` 标签已在实机确认。
- C13 `hal_keymaster` 和 `hal_gatekeeper` 对 `ion_device` 的 allow 规则经过主机侧策略验证；真机 HAL/AVC/QSEECom 效果仍未验收。C14 pmsg 没有相应 AVC 记录，但不能据此宣称修复成功。
- C13 的 BPF 故障已有直接日志支持；C14 已跨过该重启点。C13.1 fstab 变体未上机，不是当前下一实验版本。
- C14 的 SurfaceFlinger EGLConfig 是当前下一步的直接目标；尚无证据证明 netd 或 graphicsengine 的崩溃使 init 重启。

## 关键文件与下一步

- C14/C15 主机报告：`work/reports/20260926_CANDIDATE14_FAILURE_AND_CANDIDATE15_EGL_PLAN.md`。
- C15 构建脚本：`tools/build_candidate15_angle_egl.py`；受限刷写脚本：`tools/flash_candidate15_angle_egl.ps1`。
- C14 观察器与 Standalone 采集：`tools/observe_candidate13_readonly.py`、`tools/salvage_c13_diag.py`；C14 原始观察及取证材料留在独立目录，不覆盖 C13 证据。
- 本轮实刷结果：`vbmeta_system_a` Fastboot 发送/写入均为 `OKAY`；`super` sparse 1/10 至 10/10 均返回 `OKAY`，流程退出码 0；Fastboot 提示 sparse 镜像跳过 AVB footer 复制，与既往相同且本轮所有 sparse 段成功。镜像分别为 131,072 字节（SHA-256 `634EB12F681ECFFFF5E07CEF633377F5C16903E32901AFE7B6EF56FE4D5A4190`）和 7,684,274,964 字节（SHA-256 `4CD34B53A7E47E25522C191AC748B8EE91348091C9B0F31FF59EC677CF8C9B56`）。
- 下一步：设备保持 Fastboot，等待用户单独授权首次启动；启动前先运行观察器并确认 ARMED，再执行一次启动并采集 C15 结果。若失败，保留现场并取得新的 Android pstore；不清除 `userdata`/`metadata`。
- 禁止回锁 Bootloader；无授权不得刷写、启动、擦除、修改 misc/BCB、persist、modemst、EFS/NV、射频校准或设备身份数据。刷写与启动授权相互独立。

## 公开仓库

- GitHub：<https://github.com/ROCK-VK/thyme-hyperos4-port>
- C14/C15 净化报告、构建/刷写脚本及当前状态已同步至公开 main；首个 C14/C15 内容提交为 `c0af6b80e36368ed2b0f8d79e38acdc102cc05ae`。完整 ROM、镜像、原始 pstore/pmsg、oops 和设备备份不公开。
