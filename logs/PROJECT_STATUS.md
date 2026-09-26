# THYME-OS4 项目当前状态

## 目标与策略

- 将 Xiaomi 15（dada）的 HyperOS 4 / Android 17 用户空间移植到 Xiaomi Mi 10S（thyme）。
- 当前目标：突破图形/启动初始化阻塞，进入 HyperOS 动画、设置向导或桌面。
- 按真实日志进行最小修复；不因非启动功能缺陷延迟启动实验。

## 当前 Candidate 与设备

- 最近一次持久分区刷写为 C17：仅 `vbmeta_system_a` 与 `super`；其余引导分区仍为 C13 基线。C17 后未再写分区、擦除数据或恢复 PixelOS。
- 用户报告 C17 启动时小米 Logo 持续亮屏，随后手动进入 Fastboot；该次启动没有主机 observer/USB 时间线，归属依据是 C17 为最后刷入版本与用户报告。
- 故障后依据既有授权执行 Standalone RAM 只读取证。Host 成功核验设备曾处于 Bootloader Fastboot（thyme、A 槽、已解锁、非 userspace Fastboot），随后 `fastboot boot` Standalone 成功，没有持久分区写入。
- Standalone 导出后，主机未枚举 ADB、Fastboot 或 THYME_DIAG 卷；设备当前物理模式未知。最后一次确认的持久镜像状态仍是 C17。
- 未擦除 userdata/metadata；不应因本次图形故障重清数据。Bootloader 保持解锁。
- PixelOS A0′ 未恢复，不可报告为在线健康系统。

## C17 首启取证

- 报告：`work/reports/20260926_CANDIDATE17_FIRST_BOOT/REPORT.md`。
- 原始本地诊断卷：`work/reports/20260926_CANDIDATE17_FIRST_BOOT/standalone/run_20260926_194616/`；7 个可访问文件均经源/副本字节数及 SHA-256 核验，零复制错误。原始证据不上传公开仓库。
- pstore 只有 `console-ramoops-0`（165,019 字节）；没有 `pmsg-ramoops`。console 含一份正常启动/A 槽命令行的 4.19.325 kernel 记录，uptime 最后可见约 168.466 秒；没有 `init first stage started`、Android userspace、SELinux、SurfaceFlinger/EGL、zygote、bootanimation 或 panic/reboot 记录。
- 因本轮没有启动前 observer、且 pmsg 缺失，当前不能确认该 kernel console 是否完整代表所报告的 C17 首启；C17 的 SELinux open 权限效果、EGL/ANGLE/Vulkan、Android service 和界面均未实机验收。
- `oops.raw`（16 MiB）SHA-256 与 C14、C15、C16 相同，是重复旧数据，不是新的 C17 崩溃证据。
- 未找到足以支持 C18 改动的明确错误；当前不重建镜像。

## C16 已确认基线

- C16 确实到达 first-stage、dynamic SELinux enforcing Second Stage、APEX Bootstrap 和 `/data` 挂载；BPF 重启点消失。
- C16 pmsg 记录图形分配器 `ion_device` `{ open }` AVC 早于 SurfaceFlinger EGLConfig abort；C17 对该域增补 `{ open read }`，但本轮无运行时日志验证其效果。
- C16 有 EGLConfig abort、一次 graphicsengine Vulkan SIGSEGV；二者因果关系未确认。Keymaster/Gatekeeper 功能未验收。

## 安全边界与下一步

- 不执行 Bootloader 回锁；不改 `persist`、`modemst`、EFS/NV、无线电校准或设备身份分区。
- 先让主机重新识别 Bootloader Fastboot；若 Standalone 画面/模式仍在，需用户手动操作并告知，不发不明确的模式切换命令。
- 下一次不刷写、不清数据：设备可见且用户准备观察后，先以 C17 标签启动只读 observer，确认 ARMED，再由用户现场确认后受控启动当前 C17。观察 ADB、logcat、pstore；若未上线且用户返回 Fastboot，再用既有 Standalone 流程取证。
- 在取得更明确启动证据前，不构建 C18、不扩展 SELinux 权限、不修改 EGL/ANGLE/HAL。
- C16/C17 公开同步待完成；发布仅净化后的报告、脚本与状态日志，不上传原始 pstore/oops、镜像或设备备份。
