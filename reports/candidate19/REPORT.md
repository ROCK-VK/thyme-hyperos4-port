# THYME-OS4 Candidate 19 RGBX EGL 实机结果

## 结论

C19 按计划启动并进入了正常 Android First Stage、Second Stage、APEX 激活及存储初始化阶段，但没有进入 HyperOS 启动画面。将 SurfaceFlinger 请求格式从 RGBA_8888 改为 RGBX_8888 后，EGLConfig 故障仍以相同调用路径重复出现。因此，这项像素格式实验未解决当前显示阻塞。

本轮 Standalone 证据已完整复制和逐文件校验。主机 Fastboot 观察记录中设备约 267 秒后重新枚举；用户确认是手动切回 Fastboot。没有证据表明设备自动回滚或自动重启至 Bootloader。

## C19 变更与刷写基线

- 基线为 C18 native Adreno 路由及其已验证修复。
- C19 唯一系统配置变化：`ro.surface_flinger.default_composition_pixel_format=2`（RGBX_8888）。
- 本轮实际刷写 `super` 与 `vbmeta_system_a`；其余引导分区保持 C18 基线。没有重刷、清数据或改动其他持久化分区。
- 首次启动前观察器以 `C19-rgbx-format` 标签进入 ARMED；`fastboot reboot` 返回成功，ADB 未上线。

## 启动进展证据

- `console-ramoops-0` 有一个 Linux 启动头，内核为 `4.19.325-perf-g45b9b954f074`；First Stage 与 Second Stage Init 均有记录，console 最后记录约为内核启动后 230.498 秒。未见 kernel panic。
- `pmsg-ramoops-0` 的 Android 日志约从设备时间 `01-19 08:33:50.388` 延续至 `08:37:34.914`。日志记录 SELinux 服务上下文加载、APEX 状态最终为 activated、vold 进入 metadata-encrypted `/data` 初始化路径，KeyStore2 的 `earlyBootEnded()` 对 TEE 成功。证据表明存储初始化继续推进；本轮没有清除 userdata/metadata。
- 没有 `bootanimation`、设置向导、桌面或 `sys.boot_completed=1` 的证据。用户观察到小米 Logo，随后手动进入 Fastboot。
- 本轮没有出现 graphics allocator 的 `ion_device` AVC、QSEECom 启动失败或 BPF Loader 错误。console 中存在与本轮显示阻塞无关的外围服务错误，不作为当前主线。

## 图形故障结果

- pmsg 中有 **43 次** `no suitable EGLConfig found`，每次 SurfaceFlinger 请求参数均为 `format: 2`。这证明 C19 的格式改动到达了 SurfaceFlinger 的 EGLConfig 请求；RGBX_8888 仍没有找到可用配置。
- 43 次崩溃重复经过 `SkiaGLRenderEngine::chooseEglConfig`、`create` 和 `RenderEngineThreaded::threadMain`，与 C18 的 EGLConfig 故障路径一致。当前证据不支持继续增加 SELinux 权限来解释该错误。
- `graphicsengine` 有一次位于 `/system/lib64/libvulkan.so` 的 `vkEnumeratePhysicalDevices+4` SIGSEGV 记录，时间上略早于首次 EGLConfig abort。它属于另一进程；时间相邻并不能证明 Vulkan 崩溃导致 EGLConfig 失败。
- pmsg 没有 ANGLE 或 Adreno 的实际加载记录；`vendor: Android`、`Android META-EGL` 是 EGL 实现报告文本，不能据此识别底层 GPU 驱动。C19 的运行时 EGL 后端仍未确认。

## 现场归属与取证完整性

- 主机观察目录：`observations/run_20260927_003223/`。记录显示 Observer ARMED、一次 `fastboot reboot` 成功、ADB 全程 absent；Fastboot 后来重新出现。用户说明其为手动切回，因此不将该事件标作自动回滚。
- Standalone 全量导出：`standalone/run_20260927_003826/`。THYME_DIAG 中 8 个源文件均已复制，源与副本大小及 SHA-256 全部一致，复制错误为 0。
- `dmesg_diag_boot.txt` 是 Standalone 自身内核日志，不是 C19 日志。`oops.raw` 的 SHA-256 与此前 C18 副本相同，是历史残留，不能当作 C19 崩溃现场。C19 Android 日志来自本轮 pstore 的 console 与 pmsg。
- 本地原始导出未修改；证据目录在公开同步时使用独立 Candidate 路径。原始 pstore 的公开由用户明确授权。

## 当前判断与下一步

C19 已证明启动链到达 Android 第二阶段和图形服务初始化，且 RGBX 请求值实际生效；但 EGLConfig 失败仍在。当前没有足够证据断言具体 GPU 后端或 Vulkan 崩溃的因果关系。

下一轮优先做一个有诊断价值的驱动路由实验：在持久属性加载完成后显式选择 Android 17 libEGL 支持的 ANGLE 路径，同时保留 RGBX=2 与 C18/C19 其余修复。C19 实际 system 中存在 ANGLE 库，实际 `libEGL` 包含 ANGLE 与 system driver 路由逻辑，但还没有真机 ANGLE 加载证据；ANGLE 路径也可能触及已观察到的 Vulkan 枚举崩溃。因此应把它作为可证伪的下一次实验，不宣称为已确定修复。C20 是否构建和刷写应在形成具体候选方案后按项目授权流程执行。

当前设备经只读预检为 `[REDACTED_DEVICE_ID]`、`product=thyme`、A 槽、Bootloader unlocked、非 userspace Fastboot。PixelOS 未恢复；没有本轮之后的新系统启动或分区写入。

## 公开证据

C19 Standalone 导出与主机观察记录已按用户授权公开于 `evidence/candidate19/`。增量 19 个文件、18,758,650 bytes；逐项大小与 SHA-256 校验通过，凭据/策略排除 0。C19 pmsg 公开文件为 758,682 bytes，SHA-256 `ACDD5DB289EE5D66CED38D0D3C6DBC740DC3849177882D35545ACB99D3F83C30`，匿名下载校验一致。公开证据提交：[`c6511dc`](https://github.com/ROCK-VK/thyme-hyperos4-port/commit/c6511dc54eda62ad77ac8f568ed1823429dc9b89)。
