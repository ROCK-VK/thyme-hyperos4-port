# THYME-OS4 Candidate 20 ANGLE 路由与运行时诊断准备

## 目标与结论

C20 基于已刷入并实机验证启动至 SurfaceFlinger 的 C19，集中验证 Android 17 system ANGLE 路由是否能改变 `no suitable EGLConfig found`。本轮保留 C19 的 RGBX_8888 请求和所有已验证启动修复，没有替换 GPU/Vulkan/HWC/Gralloc 库、扩展 SELinux 或清除数据。

C20 已完成主机构建、针对性静态验证、`super` 与 `vbmeta_system_a` 刷写及一次受控首次启动。启动日志确认 First/Second Stage、APEX、vold 与 `/data` 推进，但 47 次 SurfaceFlinger EGLConfig abort 仍持续；未见 HyperOS 启动画面。用户随后手动返回 Bootloader Fastboot。

## C19 诊断缺口与 C20 依据

- C19 的 pmsg 证明 SurfaceFlinger 以 `format: 2` 请求 EGLConfig，43 次相同配置选择路径均失败；此前没有实际 ANGLE/Adreno 驱动身份记录。
- C19 实际 system `libEGL.so` 含 ANGLE 路由、`persist.graphics.egl` 属性名和请求 ANGLE 失败时使用的 fatal 文本。检查其字符串未找到成功路径的 `ALOGV` 文本，因此只设置 `log.tag.libEGL=VERBOSE` 不会可靠地产生库路径记录；C20 未采用这一无效门路。
- C19 system 中已有 64 位 system ANGLE EGL/GLES 库。没有证据要求替换图形库。
- C19 的 `system/build.prop` 默认设置和 `system/etc/init/surfaceflinger.rc` 中 `ro.persistent_properties.ready=true` 后的动作都强制 Adreno。C20 将两处一致改为 ANGLE，避免 `/data` 中的旧持久属性在加载后重新覆盖路由。
- 实际 C19 `com.android.runtime` APEX payload 内的 AArch64 `linker64` 含 `debug.ld.app.`、`debug.ld.all` 及 `dlopen` 成功/失败日志实现。C20 为 SurfaceFlinger 与 graphicsengine 设置按进程过滤的 dlopen/dlerror 诊断，并设置 `log.tag.linker=DEBUG`。是否产生日志仍受进程 dumpability 等运行时条件影响；无日志不能单独证明库未加载。

## C20 变更

1. `system/build.prop`：`persist.graphics.egl=angle`；保留 `ro.surface_flinger.default_composition_pixel_format=2`；增加：
   - `debug.ld.app.surfaceflinger=dlerror,dlopen`
   - `debug.ld.app.graphicsengine=dlerror,dlopen`
   - `log.tag.linker=DEBUG`
2. `system/etc/init/surfaceflinger.rc`：保留持久属性加载后的覆盖动作，但将值改为 `angle`，删除冲突的 Adreno 覆盖。
3. 只读观察器：在 ADB 可用时按 PID 保存 SurfaceFlinger 与 graphicsengine 的 `/proc/<pid>/maps`，并记录上述运行时属性；不能读取时保留失败记录。

以上是当前图形故障链上的最小修复/诊断集合。没有改变启动内核、vendor_boot、DTBO、SELinux、Vulkan/Adreno 驱动文件、fstab、加密或用户数据。

## 构建与静态验证

- Candidate：`Candidate 20 ANGLE EGL route and runtime diagnostics`
- 基线：C19 RGBX EGLConfig 实验；复用 C19 system tree、当前 thyme 硬件栈、system_ext 与分区配置。
- 新构建目录：`work/stage_j_thyme_os4_candidate_20_angle_route_diag_run1/images/`
- `fsck.erofs` 通过；从最终 EROFS 回读确认 `persist.graphics.egl=angle`、RGBX=2、三项 linker 诊断属性均存在，且没有 Adreno 属性。
- 从最终 EROFS 回读 `surfaceflinger.rc`：持久属性就绪动作是 `setprop persist.graphics.egl angle`，没有残留 Adreno 动作。
- `vbmeta_system` 的 system hashtree descriptor 与新 system 匹配；product/system_ext 描述符沿用 C19，构建器对此进行了断言。
- `lpdump` 确认预期 A 槽逻辑分区与 super 布局；用 `lpunpack` 提取的 `system_a.img` 与 C20 `system_c20.img` 大小相同且逐字节一致。
- Python 与 PowerShell AST 检查通过；刷写脚本只允许 `super`、`vbmeta_system_a`，不包含 reboot/wipe/lock 命令。

## 实际刷写结果

只写入以下目标，命令均返回成功：

| 分区 | 镜像大小 | SHA-256 |
|---|---:|---|
| `super` | 7,684,274,964 bytes | `9DAE08D2288E1F590DD803FDBDA79230A64136B2C3F529AB82E0D0B8F7946334` |
| `vbmeta_system_a` | 131,072 bytes | `E45FCEEC95592764E23DB54114DC6235A4AA6057EA0BB5C5518F10135E85B662` |

`super` 的 10 个 sparse 写入块全部返回 OKAY。刷后 Fastboot 查询仍为唯一设备 `[REDACTED_DEVICE_ID]`、`product=thyme`、A 槽、`unlocked=yes`、`is-userspace=no`、`slot-unbootable:a=no`、`slot-successful:a=no`、`slot-retry-count:a=5`；报告的 `super` 与 `vbmeta_system_a` 分区容量分别为 `0x220000000` 和 `0x20000`。没有重启、擦除、切槽、BCB 操作、其他分区写入或 Bootloader 状态更改。

## C20 首次实机结果与取证

- 观察器目录：`work/reports/20260927_CANDIDATE20_ANGLE_DIAG/observations/run_20260927_093948/`。观察器先于启动进入 ARMED；预启动只读查询确认 `thyme`、A 槽、unlocked、Bootloader Fastboot、A 槽 unbootable=no/retry=5。主机在 2026-09-27 01:40:10.987 UTC 执行一次 `fastboot reboot`，命令 exit 0；ADB 始终未上线。主机于 01:44:31 UTC 重新看到 Fastboot，USB 于 01:44:37 UTC 枚举；用户反馈米标常亮并手动进入 Fastboot。
- Standalone 诊断卷已先完整复制至 `work/reports/20260927_CANDIDATE20_ANGLE_DIAG/standalone/run_20260927_094544/`。8 个源文件共 18,811,280 bytes（不含导出附加文件）；大小与 SHA-256 全部一致，复制错误 0。原件未修改。
- C20 的 `console-ramoops-0` 有一个 Linux 启动头，内核 `4.19.325-perf-g45b9b954f074`；First Stage 约 2.059s、Second Stage 约 3.206s。SELinux 以 enforcing 方式记录 AVC。`pmsg-ramoops-0` 含 6,620 个带时间戳记录，设备日志时间从 17:41:10.370 延续至 17:45:15.527；记录显示 APEX 状态为 activated、vold 找到现有 metadata key，并成功以 F2FS 挂载 `/data`（`__mount(...target=/data...)=0`）。本轮未擦除 userdata/metadata。
- SurfaceFlinger 从 17:41:25.066 至 17:45:14.502 共记录 47 次 `no suitable EGLConfig found`，每次均为 `format: 2`。C20 的 ANGLE 路由没有消除 RGBX EGLConfig 失败。
- pmsg 没有 `ANGLE`、`libEGL`、`debug.ld.app`、`dlopen`/`dlerror` 或运行时 EGL 路由属性记录；观察器因 ADB 未上线也不能读取属性或 `/proc/<pid>/maps`。因此 C20 **没有证明 ANGLE 是否被实际加载**；`vendor: Android` / `Android META-EGL` 不能识别底层驱动。
- `graphicsengine` 在 17:41:24.435 收到 SIGSEGV；其栈在 `libvulkan.so (vkEnumeratePhysicalDevices+4)` 与 `MiVulkanPipelineCacheBuilder()+1232`，最后一帧记录约在首条 EGL abort 前 0.48s。时间相邻但因果未证。
- pmsg 未记录 `ion_device` 或 graphics allocator AVC；console 中可见的是 `hal_camera_default` 的 ION read AVC，不能据此归因当前 EGL 阻塞。无 bootanimation 记录；也没有 `sys.boot_completed=1` 成功状态证据，pmsg 中唯一匹配是 keystore2 “monitoring for sys.boot_completed=1”。
- `oops.raw` 与 C19 文件 SHA-256 完全相同（`7D1E254BBEB4803D79FDF96F673EF4DC9C7D0EAE68DF3019C2384B3439E4BB66`），按历史残留处理；`dmesg_diag_boot.txt` 是 Standalone 自身日志，不是 C20 日志。C20 console 文件为 1,048,140 bytes，最后内核 uptime 250.744s；pmsg 也在仍有服务活动的记录处结束。没有 kernel panic，也没有解释日志结束或返回 Fastboot 的明确记录。
- 首启后只读 Fastboot 查询：唯一设备 `[REDACTED_DEVICE_ID]`、`thyme`、A 槽、unlocked=yes、is-userspace=no、unbootable=no、successful=no、retry-count=4；ADB 不在线。A 槽重试计数由启动前 5 减至 4；未执行额外 boot-control 操作。PixelOS 未恢复，未再次刷写或擦除。

## 结论与下一步

C20 没有越过当前 EGLConfig 阻塞，也没有进入 HyperOS 启动画面、设置向导或桌面。已确认的进展是正常 Android 启动链再次到达 Second Stage、APEX、vold 和 `/data`，C17 以来的图形 allocator ION AVC 在本轮日志中没有出现。C20 的诊断目标未完全达成：ANGLE/Adreno 实际后端仍未知，linker 诊断没有产生可用记录；不能据此选择替换驱动，也不能宣称 ANGLE 路由生效。

下一项最小信息增益方案是 C21 诊断版：保持当前 ANGLE/RGBX 与硬件栈不变，只增加一个在 SurfaceFlinger 首次运行时触发的一次性只读快照，将运行时 `persist.graphics.egl`、`ro.hardware.egl` 及 SurfaceFlinger/graphicsengine 的 GPU/EGL/Vulkan 映射摘要写入 logd/pmsg。先静态确认该 init hook 不阻塞启动且实际日志路径可用，再决定是否构建。暂不切换 Adreno、替换 Vulkan/Gralloc/HWC 库或放宽 SELinux。

## 产物与公开范围

- 构建清单：`work/stage_j_thyme_os4_candidate_20_angle_route_diag_run1/images/BUILD_MANIFEST.json`
- 构建器：`tools/build_candidate20_angle_diag.py`
- 刷写脚本：`tools/flash_candidate20_angle_diag.ps1`
- 启动门控：`tools/start_candidate20_observed_boot.ps1`
- 观察器：`tools/observe_candidate13_readonly.py`

本报告不包含 ROM、分区镜像、APEX 提取内容或设备分区备份。C20 已完成一次真机启动；图形后端身份和 EGLConfig 故障根因仍未验收。完整 Standalone/观察器原始证据另按授权公开于 `evidence/candidate20/`。
