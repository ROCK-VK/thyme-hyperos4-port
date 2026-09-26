# THYME-OS4

**Xiaomi 15 (dada) HyperOS 4 / Android 17 移植至 Xiaomi Mi 10S (thyme)**

这是一个实验性 Android 移植工程。目标是尽快让小米 10S 进入 HyperOS 4 的正常启动流程，继续推进到启动动画、锁屏、设置向导或桌面。仓库保存可审核的脚本、补丁、项目日志和精选启动证据；不提供 ROM 下载。

## 当前状态（2026-09-26）

- C14 已在真实启动中越过 C13 的 `bpfloader-failed` 重启点：console 进入 Android first/second stage 并记录至约 115.8 秒，保存的 pmsg 未出现该 BPF 重启错误。BPF 本身仍未适配，网络完整性未验证。
- C14 的直接显示故障是 SurfaceFlinger 反复因 `no suitable EGLConfig found` 中止（pmsg 记录 20 次）。没有 ADB 证据证明启动完成、设置向导或桌面出现。
- C14 还记录一次 MIUI graphicsengine Vulkan 调用空指针崩溃及多次 netd fatal；其根因和是否阻止 Android 完成启动尚未确认。当前没有把它们写成确定根因。
- Candidate 15 已在主机侧构建并按授权仅刷写 `vbmeta_system_a`、`super`。它保留 C14 BPF 绕过，只新增 `persist.graphics.egl=angle`，用于验证 SurfaceFlinger EGLConfig 故障的最小路由修复。ANGLE 是否能使用当前 Vulkan 底层尚未实机验证。
- C15 尚未启动。最近只读核验设备仍处于 Bootloader Fastboot，槽位 A、Bootloader 解锁；设备等待单独的首次启动授权。本轮未清除 userdata/metadata。
- C14 故障后通过 Standalone RAM 只读导出了 pstore。PixelOS A0′ 尚未恢复或验证为在线健康系统。

最新分析与构建状态见 [C14 启动故障与 C15 EGL 诊断方案](reports/candidate15/20260926_CANDIDATE14_FAILURE_AND_CANDIDATE15_EGL_PLAN.md)、[C13 netbpfload 故障和 C14 构建报告](reports/candidate13/20260926_CANDIDATE13_NETBPFLOAD_FAILURE_AND_C14_BUILD.md)、[项目当前状态](logs/PROJECT_STATUS.md) 和按时间追加的 [执行记录](logs/EXECUTION_LOG.md)。

## 设备与来源

| 角色 | 设备/平台 | 用途 |
|---|---|---|
| 目标机 | Xiaomi Mi 10S，`thyme`，Snapdragon 870 | 保留目标机自身的内核、设备树、启动链和硬件适配边界 |
| OS 供体 | Xiaomi 15，`dada`，HyperOS 4 / Android 17 | 提供待移植的系统用户空间 |
| 移植参考 | Redmi K40，`alioth`，Snapdragon 870 | 参考成功启动的移植方案和适配方式；不直接移植其硬件专属镜像或分区 |

K40 对照资料显示，成功包的 vendor_boot ramdisk 与原包不同，并增加了 EROFS first-stage fstab 项等适配。详细边界、尚未证明的来源关系及三方差异见 [K40 三方逆向分析](reports/k40/20260918_K40_THREE_WAY_PORT_REVERSE_ENGINEERING_1.md) 和[独立复核](reports/k40/20260918_K40_THREE_WAY_PORT_REVIEW_1.md)。这些内容用于指导 thyme 的适配，不意味着可以照搬 K40 内核、DT/DTBO、射频校准、firmware 或完整镜像。

## Candidate 历程摘要

- **C9**：清理重复 Property Contexts，解决 `persist.radio.imei` Duplicate Prefix 启动失败。
- **C10-WarmDtb**：加入温复位取证支持并建立 ramoops/Standalone 采集流程；温复位不保证所有故障日志都保留。
- **C11**：修复 `system_ext` EROFS 文件元数据和 SELinux xattr，使 APEX Bootstrap 得以继续。
- **C12**：实机确认 `/dev/ion` 使用 `ion_device:s0` 标签；Keymaster/Gatekeeper 的后续访问仍曾被拒绝。
- **C13**：在动态 system_ext SELinux policy 中增加 Keymaster/Gatekeeper 对 `ion_device` 的访问规则。主机侧编译与权限断言通过；真机 C13 日志已进入动态策略编译和 enforcing second stage，但未覆盖相关 HAL，因此 AVC 是否消失仍待验证。
- **C13.1**：主机侧构建过数据挂载保护变体，尚未实机验证；不是当前已验证版本。
- **C14**：绕过已证实与 Android 25Q2/kernel 4.19 不兼容的 BPF loader 重启门控；真机 pstore 证实越过该点，随后发现 SurfaceFlinger EGLConfig abort。
- **C15**：保留 C14 绕过并增加 Android 17 ANGLE EGL 选择属性；主机侧已构建，尚未刷写或实机验证。

具体阶段和证据等级以项目状态文件及 Candidate 报告为准，旧报告的“计划/待验证”不会自动成为当前结论。

## 仓库内容

```text
docs/guides/       移植入门、准备计划、审核交接手册（部分内容是历史快照）
logs/              当前状态和按时间追加的执行记录
tools/             精选构建、预检、刷写和诊断脚本
patches/           可审阅的最小策略补丁
reports/           K40 对照、Candidate 分析和已归属的启动日志
scripts/           带明确文件白名单的本地增量同步脚本
```

建议阅读顺序：

1. [当前项目状态](logs/PROJECT_STATUS.md)
2. [C14 故障与 C15 EGL 诊断方案](reports/candidate15/20260926_CANDIDATE14_FAILURE_AND_CANDIDATE15_EGL_PLAN.md)
3. [C13 netbpfload 故障与 C14 构建](reports/candidate13/20260926_CANDIDATE13_NETBPFLOAD_FAILURE_AND_C14_BUILD.md)
4. [C13 首次启动证据摘要](reports/boot-logs/candidate13_netbpfload_failure_excerpt.txt)
5. [C13 Second Stage 取证准备](reports/candidate13/20260926_CANDIDATE13_SECOND_STAGE_CAPTURE_PREP.md)
6. [K40 三方移植分析](reports/k40/20260918_K40_THREE_WAY_PORT_REVERSE_ENGINEERING_1.md)

## 脚本与构建

`tools/` 中保留了 C9–C13 的部分构建/预检流程、C13 SELinux 审核、首次启动只读观察器、时间戳启动助手、Standalone 日志导出工具和 PixelOS A0′ 恢复脚本。启动、刷写和 `fastboot boot` 辅助脚本都需要各自的授权；脚本本身不构成设备操作许可。它们依赖本机 WSL 环境、外部 ROM 输入和原工程中的暂存资产。本仓库没有完整输入镜像，**不能仅凭 clone 一键复现完整 ROM 构建**。脚本来源及设备操作分类见 [`tools/README.md`](tools/README.md)。

后续更新公开副本时，先审核允许发布的本地变更，再运行显式白名单同步器：

```powershell
$env:THYME_OS4_SOURCE = 'D:\projects\thyme-os4-local'
.\scripts\sync_from_local.ps1 -SourceRoot $env:THYME_OS4_SOURCE
git status --short
git diff --stat
# 人工审查完整 diff 与暂存文件清单后，再 Commit 和 Push
```

同步器只复制脚本中列出的文件，不扫描整个工程；新报告、配置或日志默认不会进入公开仓库。每次增补白名单前都应做敏感信息检查。

## 为什么不提供完整镜像

小米 15 原包、K40 成功移植包、PixelOS、展开后的 Android 系统树以及 Candidate 构建镜像都可能包含专有固件、厂商 HAL、应用或其他第三方内容。它们不属于本公开仓库的分发范围。这里仅放项目自编脚本、有限策略补丁、整理后的分析报告及必要的启动日志；原始 misc、设备分区备份、密钥/校准数据和用户数据均不公开。

仓库不附加统一开源许可证。项目代码与随附报告的权利状态应由各自作者/来源确定；不对小米固件、第三方 ROM 或厂商二进制授予任何许可证。

## 安全与免责声明

这是实验性 Android 移植工程。修改启动链或刷写分区可能导致设备无法启动、数据丢失或需要额外恢复。`flash_*.ps1` 和 `restore_*.ps1` 属于可能写入设备分区的脚本；运行前必须读懂目标分区、镜像来源、槽位和设备检查。公开仓库没有附带这些脚本需要的镜像。不要刷写或覆盖 `persist`、`modemst`、EFS/NV、射频校准、设备身份、用户数据或其他未授权分区；Bootloader 必须保持解锁。

本项目没有承诺日常可用，也不保证相机、音频、指纹、NFC、电话、加密或其他功能正常。刷写操作由操作者自行评估和承担风险。
