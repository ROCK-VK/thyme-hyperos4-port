# THYME-OS4

**Xiaomi 15 (dada) HyperOS 4 / Android 17 移植至 Xiaomi Mi 10S (thyme)**

这是一个实验性 Android 移植工程。当前首要目标是让小米 10S 越过 HyperOS 4 启动阻塞并进入启动动画、设置向导或桌面。仓库保存可审核的脚本、补丁、项目日志与用户授权公开的 C13–C25 启动诊断证据；不提供 ROM 下载。

## 当前状态（2026-09-29）

- **C25 已启动约 898 秒，用户全程看到小米第一屏，未见 HyperOS 三点第二屏，ADB 未上线。** Standalone 只读导出的持久采样证明 Zygote/zygote_secondary 长时间处于 restarting，system_server/zygote64 PID 不存在；具体退出原因尚未保存。
- C25 诊断 helper 已通过真机验证：post-fs-data 标记存在，持久日志有 56 个样本；Window/Activity/Display 服务查询持续 service-not-found。SurfaceFlinger 可枚举 HWC display 0 和 BootAnimation layer，但没有物理面板成功 present 的证据。完整取证与逐文件校验见 [`evidence/candidate25/run_20260928_234427_meta_ro/`](evidence/candidate25/run_20260928_234427_meta_ro/)；报告见 [C25 首屏诊断报告](reports/candidate25/C25_FIRST_SCREEN_DIAGNOSTIC_BUILD_FLASH_20260928.md)。
- 当前下一步是采集 Zygote 崩溃/退出首因，再实施定点修复。C25 采样在设定 900 秒前结束，没有 COMPLETE 标记；不声称已获得完整窗口。
- 用户澄清：中央小米 Logo + powered by Android 是第一屏；带 Xiaomi HyperOS Logo 与三个点的图片是第二屏。此前观察只确认第一屏，不能当作已看到 HyperOS 第二屏。
- C24 的采样标记缺失；C25 已将当前停点推进为持续 Zygote 重启且没有 system_server 的可核对状态。BootAnimation layer 存在不等于物理面板成功 present，用户屏幕仍只有小米第一屏。
- 本轮没有清除 userdata/metadata、修改 boot-control/BCB/硬件身份分区或回锁 Bootloader。C25 的 Standalone 仅 RAM 启动，metadata 只读挂载并复制后卸载。
- 重点资料：[C25 构建/刷写报告](reports/candidate25/C25_FIRST_SCREEN_DIAGNOSTIC_BUILD_FLASH_20260928.md)、[C25 构建报告](reports/candidate25/BUILD_REPORT.md)、[C25 清单](reports/candidate25/BUILD_MANIFEST.json)、[当前项目状态](logs/PROJECT_STATUS.md)。
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
- **C20**：将 EGL 路由统一为 ANGLE，保留 RGBX=2，并加入 linker 诊断；实机仍有 EGLConfig abort，实际 EGL 后端未知。完整 C20 原始证据见 [`evidence/candidate20/`](evidence/candidate20/) 和 [C20 报告](reports/candidate20/REPORT.md)。
- **C21**：K40 threaded SkiaVk 路由绕开 EGLConfig fatal；实机因 Vulkan RenderEngine 初始化 fatal 未进入启动动画。
- **C22**：以 K40 Android 17 Vulkan UMD 及隔离 GSL/LLVM/Adreno Utils 依赖配套替换 Vulkan ICD；实机越过 RenderEngine 创建 fatal，后在 Skia shader-cache 预热因输出 buffer usage 检查反复 abort。
- **C23**：仅关闭可选 SurfaceFlinger shader-cache 预热。首次尝试保存到 Recovery；后续启动推进到 `/data`/fscrypt 和 BootAnimation shown-timing 日志阶段，但两轮均未见用户实际进入 HyperOS 动画、Setup Wizard 或桌面。长窗口 pmsg 未复现 C22 的 shader-cache fatal，但运行时属性值未采样；静态 Logo 的新根因仍未知。最新报告和完整原始证据见上方链接。
- **C24**：基于 C23 的 framework/display 诊断变体；启动观察约 16 分 43 秒，用户看到第一屏小米 Logo + `powered by Android`，未见 HyperOS 第二屏。ADB 未上线，pmsg 无诊断服务标记。详见[首次启动报告](reports/candidate24/C24_FIRST_BOOT_EVIDENCE_20260928.md)和[完整原始证据](evidence/candidate24/framework_display/20260928_194944/)。


- **C25**：有界 AArch64 helper 同时向 logd 和 metadata 持久目录写样本；实机验证到 Zygote/zygote_secondary restarting、system_server PID 不存在，SurfaceFlinger 与 BootAnimation layer 存在，但物理 present 未证明。Zygote 退出原因待采集。见 [C25 报告](reports/candidate25/C25_FIRST_SCREEN_DIAGNOSTIC_BUILD_FLASH_20260928.md)及[本轮导出与主机观察证据](evidence/candidate25/run_20260928_234427_meta_ro/)。

具体阶段和证据等级以项目状态文件及 Candidate 报告为准，旧报告的“计划/待验证”不会自动成为当前结论。

## 仓库内容

```text
docs/guides/       移植入门、准备计划、审核交接手册（部分内容是历史快照）
logs/              当前状态和按时间追加的执行记录
tools/             精选构建、预检、刷写和诊断脚本
patches/           可审阅的最小策略补丁
reports/           K40 对照与 Candidate 分析报告
evidence/          C13–C25 Standalone 诊断卷及 USB/ADB/Fastboot 主机观察记录
scripts/           带明确文件白名单的本地增量同步脚本
```

建议阅读顺序：先看 [C24 首次启动取证报告](reports/candidate24/C24_FIRST_BOOT_EVIDENCE_20260928.md)、[C24 Framework/display 诊断准备报告](reports/candidate24/C23_FRAMEWORK_DISPLAY_C24_DIAGNOSTIC_20260928.md)、[C23 SurfaceFlinger 预热绕过报告](reports/candidate23/REPORT.md)、[C22 实机故障报告](reports/candidate22/REPORT.md) 和 [C21 K40 SkiaVk 路由报告](reports/candidate21/REPORT.md)，再按以下历史材料阅读：

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
13. [C13–C24 原始启动诊断证据索引](evidence/README.md)
## 脚本与构建

`tools/` 中保留了历史 Candidate 构建/预检流程、C13 SELinux 审核、只读启动观察器、启动门控、Standalone 日志导出工具和 PixelOS A0′ 恢复脚本。C18–C23 构建脚本记录定点图形启动实验；C22 配套 K40 Android 17 Vulkan UMD，C23 跳过触发 C22 fatal 的可选 shader-cache 预热；C24 增加 Framework/display 启动诊断。Candidate 刷写脚本可能写入设备分区；启动脚本要求观察器 ARMED 和用户在场确认。脚本本身不构成设备操作许可。它们依赖本机 WSL 环境、外部 ROM 输入和原工程中的暂存资产。本仓库没有完整输入镜像，**不能仅凭 clone 一键复现完整 ROM 构建**。脚本来源及设备操作分类见 [`tools/README.md`](tools/README.md)。

后续更新公开副本时，先审核允许发布的本地变更，再运行文本与原始诊断证据同步器。原始证据同步器只递归处理明确列入 allowlist 的 Standalone 导出和 host-observation 目录，复制原始字节并生成逐文件 SHA-256 清单；可用 `-EvidenceCandidates C22` 只同步新增 Candidate，保留其他 Candidate 的 manifest 行而不重新遍历旧目录。识别到凭据、分区/固件镜像名或超大文件时会排除并记录原因：

```powershell
$env:THYME_OS4_SOURCE = 'C:\path\to\thyme-os4-local'
.\scripts\sync_from_local.ps1 -SourceRoot $env:THYME_OS4_SOURCE -EvidenceCandidates C22
git status --short
git diff --stat
# 人工审查完整 diff 与暂存文件清单后，再 Commit 和 Push
```

同步器不扫描整个工程。新增 Standalone 或 host-observation 目录时，应在 scripts/sync_raw_startup_evidence.ps1 中明确列入 allowlist。原始日志保持逐字节不变；evidence/RAW_EVIDENCE_MANIFEST.csv 记录发布路径、大小和 SHA-256，凭据特征排除项记录在 evidence/RAW_EVIDENCE_EXCLUSIONS.csv。本仓库不上传完整 ROM、固件包、分区镜像或 userdata/metadata 备份。原始日志可能包含设备序列号、CPUID、内核命令行和主机路径。

## 为什么不提供完整镜像

小米 15 原包、K40 成功移植包、PixelOS、展开后的 Android 系统树以及 Candidate 构建镜像都可能包含专有固件、厂商 HAL、应用或其他第三方内容。它们不属于本公开仓库的分发范围。这里不提供完整 ROM 或固件分发。按用户授权，evidence/ 保存 C13–C24 诊断日志和主机观察记录；C21 副本对设备序列号做了可追溯替换，C22–C24 公开诊断证据按逐文件 SHA-256 清单记录；misc、persist、modemst、EFS/NV、校准与设备身份分区备份，以及 userdata/metadata 分区镜像仍不公开。

仓库不附加统一开源许可证。项目代码与随附报告的权利状态应由各自作者/来源确定；不对小米固件、第三方 ROM 或厂商二进制授予任何许可证。

## 安全与免责声明

这是实验性 Android 移植工程。修改启动链或刷写分区可能导致设备无法启动、数据丢失或需要额外恢复。`flash_*.ps1` 和 `restore_*.ps1` 属于可能写入设备分区的脚本；运行前必须读懂目标分区、镜像来源、槽位和设备检查。公开仓库没有附带这些脚本需要的镜像。不要刷写或覆盖 `persist`、`modemst`、EFS/NV、射频校准、设备身份、用户数据或其他未授权分区；Bootloader 必须保持解锁。

本项目没有承诺日常可用，也不保证相机、音频、指纹、NFC、电话、加密或其他功能正常。刷写操作由操作者自行评估和承担风险。
