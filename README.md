# THYME-OS4

**Xiaomi 15 (dada) HyperOS 4 / Android 17 移植至 Xiaomi Mi 10S (thyme)**

这是一个实验性 Android 移植工程。当前首要目标是让小米 10S 越过 HyperOS 4 图形初始化并进入启动动画、设置向导或桌面。仓库保存可审核的脚本、补丁、项目日志与用户授权公开的 C13–C19 原始启动诊断证据；不提供 ROM 下载。

## 当前状态（2026-09-27）

- **C20 已构建并刷写，尚未首次启动。** 仅将 `super` 和配套 `vbmeta_system_a` 写入 A 槽；设备保持 Bootloader Fastboot，等待用户现场确认后启动。未擦除 userdata/metadata，也未改动其他分区。
- C20 基于实机 C19，保留 RGBX_8888 (`ro.surface_flinger.default_composition_pixel_format=2`)；将 EGL 路由在默认属性与 `/data` 持久属性加载后的 init 动作中统一设为 ANGLE，移除冲突的 Adreno 覆盖。
- 为 SurfaceFlinger 和 graphicsengine 增加进程级 linker `dlopen`/`dlerror` 诊断属性；ADB 可用时观察器另保存运行时属性和进程 maps。该诊断为 best-effort，仍待 C20 实机验证。
- C19 已在真实启动中推进至 First/Second Stage、APEX Bootstrap、vold 与 `/data` 初始化；43 次 SurfaceFlinger `no suitable EGLConfig found` 均请求 format 2。graphicsengine Vulkan 枚举 SIGSEGV 与 EGLConfig 故障的因果关系尚未证明。
- C14 的 BPF 启动绕过和 C16/C17 图形 allocator ION 权限修复已在后续实机记录中得到支持；目前没有启动动画、设置向导或桌面成功证据。

最新材料：[C20 报告](reports/candidate20/REPORT.md)、[C20 构建清单](reports/candidate20/BUILD_MANIFEST.json)、[项目当前状态](logs/PROJECT_STATUS.md) 与 [按时间追加的执行记录](logs/EXECUTION_LOG.md)。

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
- **C15**：保留 C14 绕过并增加 ANGLE EGL 选择属性；实机进入 second stage 和 /data 挂载，但仍有 SurfaceFlinger EGLConfig abort，未进入启动动画。
- **C16**：图形 allocator 的 ion_device read 拒绝消失，但仍有 open AVC；SurfaceFlinger EGLConfig abort 继续出现。
- **C17**：依据 C16 的 open AVC 增加精确权限，已刷写 vbmeta_system_a 与 super。复验已确认进入 Second Stage，图形 allocator 的 open/read AVC 未复现；SurfaceFlinger EGLConfig abort 持续，尚未进入启动动画。
- **C18**：保留 C17 启动链和修复，将 EGL 路由改为 thyme vendor 配置的 native Adreno；其后 C19/C20 实验继续探索运行时后端。
- **C19**：保留 Adreno 路由并改为 RGBX_8888 EGL 请求；format=2 仍有 43 次 EGLConfig 失败。`reports/candidate19/REPORT.md` 与 `evidence/candidate19/` 保存报告和原始诊断证据。
- **C20**：将 EGL 路由统一为 ANGLE，保留 RGBX=2，并加入 linker 诊断；已刷写 `super`、`vbmeta_system_a`，尚未启动，等候用户现场确认。


具体阶段和证据等级以项目状态文件及 Candidate 报告为准，旧报告的“计划/待验证”不会自动成为当前结论。

## 仓库内容

```text
docs/guides/       移植入门、准备计划、审核交接手册（部分内容是历史快照）
logs/              当前状态和按时间追加的执行记录
tools/             精选构建、预检、刷写和诊断脚本
patches/           可审阅的最小策略补丁
reports/           K40 对照与 Candidate 分析报告
evidence/          C13–C19 Standalone 原始诊断卷及 USB/ADB/Fastboot 主机观察记录
scripts/           带明确文件白名单的本地增量同步脚本
```

建议阅读顺序:

1. [C20 ANGLE 路由与运行时诊断报告](reports/candidate20/REPORT.md)
2. [当前项目状态](logs/PROJECT_STATUS.md)
3. [C19 RGBX EGLConfig 实机报告](reports/candidate19/REPORT.md)
4. [C17 复验报告](reports/candidate17/20260926_CANDIDATE17_RETEST_REPORT.md)
5. [C17 首次取证结果](reports/candidate17/20260926_CANDIDATE17_FIRST_BOOT_REPORT.md)
6. [C16 首启与 C17 构建/刷写报告](reports/candidate17/20260926_CANDIDATE16_FAILURE_AND_CANDIDATE17_BUILD_FLASH.md)
7. [C15 首启与 C16 图形权限修复报告](reports/candidate16/20260926_CANDIDATE15_FIRST_BOOT_AND_CANDIDATE16_GRAPHICS_ALLOCATOR_FIX.md)
8. [C14 故障与 C15 EGL 诊断方案](reports/candidate15/20260926_CANDIDATE14_FAILURE_AND_CANDIDATE15_EGL_PLAN.md)
9. [C13 netbpfload 故障与 C14 构建](reports/candidate13/20260926_CANDIDATE13_NETBPFLOAD_FAILURE_AND_C14_BUILD.md)
10. [C13 首次启动证据摘要](reports/boot-logs/candidate13_netbpfload_failure_excerpt.txt)
11. [C13 Second Stage 取证准备](reports/candidate13/20260926_CANDIDATE13_SECOND_STAGE_CAPTURE_PREP.md)
12. [K40 三方移植分析](reports/k40/20260918_K40_THREE_WAY_PORT_REVERSE_ENGINEERING_1.md)
13. [C13–C19 原始启动诊断证据索引](evidence/README.md)
## 脚本与构建

`tools/` 中保留了历史 Candidate 构建/预检流程、C13 SELinux 审核、只读启动观察器、启动门控、Standalone 日志导出工具和 PixelOS A0′ 恢复脚本。C18–C20 构建脚本记录定点 EGL 路由实验；C20 将 ANGLE 路由与进程级 linker 诊断结合。C20 刷写脚本只写 `super`/`vbmeta_system_a`，启动脚本要求 observer ARMED 和用户在场确认。启动、刷写和 `fastboot boot` 辅助脚本都需要审阅其操作范围；脚本本身不构成设备操作许可。它们依赖本机 WSL 环境、外部 ROM 输入和原工程中的暂存资产。本仓库没有完整输入镜像，**不能仅凭 clone 一键复现完整 ROM 构建**。脚本来源及设备操作分类见 [`tools/README.md`](tools/README.md)。

后续更新公开副本时，先审核允许发布的本地变更，再运行文本与原始诊断证据同步器。原始证据同步器只递归处理明确列入 allowlist 的 Standalone 导出和 host-observation 目录，复制原始字节并生成逐文件 SHA-256 清单；识别到凭据、分区/固件镜像名或超大文件时会排除并记录原因：

```powershell
$env:THYME_OS4_SOURCE = 'C:\path\to\thyme-os4-local'
.\scripts\sync_from_local.ps1 -SourceRoot $env:THYME_OS4_SOURCE
git status --short
git diff --stat
# 人工审查完整 diff 与暂存文件清单后，再 Commit 和 Push
```

同步器不扫描整个工程。新增 Standalone 或 host-observation 目录时，应在 scripts/sync_raw_startup_evidence.ps1 中明确列入 allowlist。原始日志保持逐字节不变；evidence/RAW_EVIDENCE_MANIFEST.csv 记录发布路径、大小和 SHA-256，凭据特征排除项记录在 evidence/RAW_EVIDENCE_EXCLUSIONS.csv。本仓库不上传完整 ROM、固件包、分区镜像或 userdata/metadata 备份。原始日志可能包含设备序列号、CPUID、内核命令行和主机路径。

## 为什么不提供完整镜像

小米 15 原包、K40 成功移植包、PixelOS、展开后的 Android 系统树以及 Candidate 构建镜像都可能包含专有固件、厂商 HAL、应用或其他第三方内容。它们不属于本公开仓库的分发范围。这里不提供完整 ROM 或固件分发。按用户授权，evidence/ 保存 C13–C19 Standalone 原始诊断日志和主机观察记录；misc、persist、modemst、EFS/NV、校准与设备身份分区备份，以及 userdata/metadata 分区镜像仍不公开。

仓库不附加统一开源许可证。项目代码与随附报告的权利状态应由各自作者/来源确定；不对小米固件、第三方 ROM 或厂商二进制授予任何许可证。

## 安全与免责声明

这是实验性 Android 移植工程。修改启动链或刷写分区可能导致设备无法启动、数据丢失或需要额外恢复。`flash_*.ps1` 和 `restore_*.ps1` 属于可能写入设备分区的脚本；运行前必须读懂目标分区、镜像来源、槽位和设备检查。公开仓库没有附带这些脚本需要的镜像。不要刷写或覆盖 `persist`、`modemst`、EFS/NV、射频校准、设备身份、用户数据或其他未授权分区；Bootloader 必须保持解锁。

本项目没有承诺日常可用，也不保证相机、音频、指纹、NFC、电话、加密或其他功能正常。刷写操作由操作者自行评估和承担风险。
