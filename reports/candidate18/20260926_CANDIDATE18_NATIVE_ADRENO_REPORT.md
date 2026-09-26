# THYME-OS4 Candidate 18：native Adreno EGL 路由实验

## 目的

C17 已证明 Second Stage、enforcing SELinux、APEX Bootstrap、vold 与 `/data` 均能推进，且图形分配器对 `ion_device` 的 open/read AVC 不再出现。当前显示阻塞仍是 SurfaceFlinger 的 `no suitable EGLConfig found`。

C18 是有针对性的原生图形后端实验，不宣称已经找到 EGLConfig 不匹配的最终根因。目标是让系统 EGL Loader 明确走 thyme vendor 中的 Adreno EGL 实现，并观察 EGL 配置选择是否改变。

## C17 证据与边界

- 本地原始 pmsg：`work/reports/20260926_CANDIDATE17_RETEST/standalone/run_20260926_203340/THYME_DIAG/pstore/pmsg-ramoops-0`。
- SurfaceFlinger 的 24 次 `no suitable EGLConfig found` 具有重复的 `SkiaGLRenderEngine::chooseEglConfig` → `SkiaGLRenderEngine::create` → `RenderEngineThreaded::threadMain` 调用路径。说明失败稳定发生在 EGLConfig 选择阶段；原始记录和公开完整取证目录中的调用栈可供复核。
- `graphicsengine` 在 `vkEnumeratePhysicalDevices+4` 的 SIGSEGV 比第一次 SurfaceFlinger abort 早约 0.6 秒，发生于另一个进程/调用路径。时间接近，但没有调用关系或因果证据。
- C17 中 `persist.graphics.egl=angle` 存在于系统构建属性；实际 Android 17 `/system/lib64/libEGL.so` 含有该属性和 ANGLE 相关路由符号。日志没有 ANGLE 初始化、ANGLE EGL 库加载或实际 EGL 后端身份记录。因此 **C17 的运行时 EGL 后端仍未确定**。
- `graphicsengine` 的 `vendor_default_prop { read }` AVC 没有可确认的属性名或与本次 EGLConfig abort 的调用链证据，本版不改变该策略。

## C18 改动

在 C17 基础上只改 system 分区中的 EGL 路由：

1. 将 `system/build.prop` 的 `persist.graphics.egl` 从 `angle` 改为 `adreno`，对应 thyme vendor 的 `ro.hardware.egl=adreno`。
2. 在 `/system/etc/init/surfaceflinger.rc` 加入 `ro.persistent_properties.ready=true` 属性动作，持久属性加载后重新设置 `persist.graphics.egl=adreno`。这样即使 `/data` 中保留了旧 ANGLE 持久值，本次测试仍把 EGL 路由限定为 native Adreno。该设置改动的是 Android 系统属性，不触碰硬件 `persist` 分区。

依据：目标 vendor 的 `build.prop` 声明 `ro.hardware.egl=adreno`、`ro.hardware.vulkan=adreno`，并包含 `libEGL_adreno.so` 和 `libGLESv2_adreno.so`。之前提取的 K40 Snapdragon 870 成功包也选择 `ro.hardware.egl=adreno`；仅参考路由，不复制 K40 硬件二进制。

Android 17 AOSP EGL Loader 以 `persist.graphics.egl`、硬件 EGL 属性选择驱动；`angle` 选择 system ANGLE，其它硬件后缀走相应 vendor EGL 路径。[Android 17 EGL Loader](https://android.googlesource.com/platform/frameworks/native/+/android-17.0.0_r1/opengl/libs/EGL/Loader.cpp) AOSP 属性策略也说明该属性用于 ANGLE/native EGL 路由；系统 init 在持久属性加载后设置 `ro.persistent_properties.ready`。[graphics property policy](https://android.googlesource.com/platform/system/sepolicy/+/889dd078e977f41dcf9920d72c956a035178bd22) [persistent-property loading](https://android.googlesource.com/platform/system/core/+/dff165d3a2db868689bae12db1ed8b3c74fa7d60/init/property_service.cpp)

保留 C17 的 BPF 绕过、Keymaster/Gatekeeper ION 权限、图形 allocator ION open/read 权限、fstab、数据加密路径、system_ext 策略，以及 thyme 内核/vendor 图形 HAL。没有清除数据、替换 Vulkan 库、扩大 SELinux 权限或关闭 enforcing。

## 构建与静态验证

- 新构建脚本：`tools/build_candidate18_native_adreno.py`；`--resume` 仅用于继续本次已存在的 C18 暂存目录，并在继续前检查旧 staging images 仍与 C17 manifest 一致。
- 新受限刷写脚本：`tools/flash_candidate18_native_adreno.ps1`，默认 Dry-Run，仅允许 `super` 和 `vbmeta_system_a`，不擦除、不重启。
- 新启动门控脚本：`tools/start_candidate18_observed_boot.ps1`，需要 C18 observer 的新鲜 ARMED 记录和显式现场确认开关；本轮已通过门控并用于一次 C18 首启。
- Observer `tools/observe_candidate13_readonly.py` 的属性快照已补入 `persist.graphics.egl`、`ro.hardware.egl`、`ro.hardware.vulkan`、`ro.board.platform`，实际 C18 启动应以运行时快照为准。
- system EROFS `fsck.erofs` 通过；从最终 `super` 提取的 `system_a.img` 与独立 C18 system 镜像逐字节相同，SHA-256 均为 `688d47c20002826231843fce53a42f77f2c9f510494af632bff653bc35eb38d5`，提取镜像 EROFS 检查通过。
- `vbmeta_system.img` 中 `system` hashtree descriptor root digest 与 C18 system 一致；`product` 和 `system_ext` descriptor 的 image size/root digest 沿用 C17。LP dump 确认 A 槽 `mi_ext_a`、`odm_a`、`product_a`、`system_a`、`system_ext_a`、`vendor_a` 保持 C17 布局。
- Python 编译检查、PowerShell AST 语法检查及刷写脚本 Dry-Run 通过。脚本计划仅顺序写 `super`、`vbmeta_system_a`，无自动 reboot。

镜像位置：`work/stage_h_thyme_os4_candidate_18_native_adreno_run1/images/`。大小与 SHA-256 见同目录 `BUILD_MANIFEST.json`。

## 实机结果与下一步

- C18 已刷写到 thyme：`super` 的 10/10 sparse 块全部 `OKAY`，Fastboot 用时 206.216 秒；随后 `vbmeta_system_a` 发送与写入均 `OKAY`，Fastboot 用时 13.321 秒。
- 首次启动观察器于 2026-09-26 21:55:04（UTC+8）显示 C18 ARMED；`fastboot reboot` 于 21:55:33 返回成功。主机在约 34 秒后检测到 Fastboot 消失，约 69 秒后重新出现；ADB 全程未上线。用户看到小米 Logo 亮约十几秒后黑屏，随后设备自动进入 Fastboot；未看到 HyperOS 启动动画、设置向导或桌面。
- 重启后的只读查询仍为 `product=thyme`、A 槽、`unlocked=yes`、`is-userspace=no`。另读到 `slot-unbootable:a=yes`、`slot-successful:a=no`、`slot-retry-count:a=0`；这些值仅在启动失败后采集，缺少刷前对照，不能据此确定原因。
- 取证初期两次 Standalone RAM 尝试均通过主机镜像大小/SHA-256 检查和 Fastboot 身份预检，但 Bootloader 在传输 196608 KB 后返回 `Failed to load/authenticate boot image: Load Error`。第一次发生在自动回到 Fastboot 后，第二次发生在用户手动重新进入 Fastboot 后；结果相同。两次具体记录分别在 `work/reports/20260926_C18_NATIVE_ADRENO/standalone/run_20260926_215725/` 与 `run_20260926_220042/`。
- 自动进入或手动进入 Fastboot 不影响主机识别设备；最初两次取证阻塞是 Bootloader 根据当时 A 槽状态拒绝加载 Standalone RAM 镜像。该阻塞已在后续授权操作中解除。Standalone 本地 SHA-256 与既有已验证镜像一致：`8A5803F09CBCB11056D8356F8D235C3C4450846244FA1B4033ABAAACB213E98B`。
- C18 的 native Adreno 属性是否在 Android 运行时生效、EGLConfig/SurfaceFlinger 是否推进、崩溃发生在哪个 Android 启动阶段，均未取得日志，尚不能验收 C18 修改效果；也没有依据构建 C19。

本次主机证据位置：观察记录 `work/reports/20260926_CANDIDATE18_NATIVE_ADRENO/observations/run_20260926_215459/`；Standalone 失败尝试及其 Fastboot 时间线分别在 `work/reports/20260926_C18_NATIVE_ADRENO/standalone/run_20260926_215725/` 和 `run_20260926_220042/`。两次目录没有设备诊断卷副本，保留的是主机侧尝试记录。

项目执行记录中有一条同设备、同类症状的历史实测（2026-09-23 Candidate 5）：当 A 槽 `slot-unbootable=yes` 时，`fastboot boot` 返回同一 `Load Error`；执行 `fastboot set_active a` 后，槽位状态重置且 Standalone RAM 镜像随即成功启动。该先例解释的是诊断镜像为何被拒绝，不反推 C18 系统启动根因。

### A 槽状态恢复后的 Standalone 取证（2026-09-26 22:16，UTC+8）

用户明确授权后，先记录并复核 Fastboot 状态，再只执行一次 `fastboot set_active a`。执行前为 `product=thyme`、`current-slot=a`、`unlocked=yes`、`is-userspace=no`、`slot-unbootable:a=yes`、`slot-successful:a=no`、`slot-retry-count:a=0`。命令返回 `OKAY`；执行后 `slot-unbootable:a=no`、`slot-retry-count:a=7`，其余身份/槽位状态一致。

随后使用既有 Standalone 镜像 `fastboot boot` 成功，未写入持久分区。动态发现 `THYME_DIAG` 卷为 `F:`，将整个卷复制到 `work/reports/20260926_C18_NATIVE_ADRENO/standalone/run_20260926_221653/`，保留空目录和系统文件。共复制 6 个文件、16,934,939 bytes，复制错误为 0；脚本逐文件比对源/副本大小与 SHA-256，结果全部一致。副本包括完整 `diag_status.log`、Standalone `dmesg_diag_boot.txt`、`oops.raw`、其校验文件、两个 `System Volume Information` 文件，以及清单和导出时间线。

此轮 THYME_DIAG 的 `pstore/` 目录为空；Standalone 报告 `/sys/fs/pstore` 已挂载，但没有可复制记录（0 records）。因此本轮没有取得 C18 的 console-ramoops、pmsg 或其他 Android pstore 记录。`oops.raw` 为 16 MiB，SHA-256 `7D1E254BBEB4803D79FDF96F673EF4DC9C7D0EAE68DF3019C2384B3439E4BB66`，与 C15–C17 的旧副本一致，判为历史残留，不能归属 C18。`dmesg_diag_boot.txt` 是 Standalone 自身内核日志；其中 pstore 无记录和 mtdoops 容量提示不能当作 C18 Android 的错误。

Standalone 启动及导出时间线位于上述目录的 `host_salvage_timeline.csv`；C18 首启的 USB/ADB/Fastboot 时间线位于 `observations/run_20260926_215459/`。首启时 Fastboot 在启动命令返回后约 34 秒消失、约 69 秒重新出现，ADB 未上线。导出完成时 Windows 识别到 `THYME_DIAG` FAT32 卷 `F:`。之后用户手动将手机切回 Bootloader Fastboot。约 22:40（UTC+8）的只读复核显示唯一设备 `[REDACTED_DEVICE_ID]`、`product=thyme`、`current-slot=a`、`unlocked=yes`、`is-userspace=no`、`slot-unbootable:a=no`、`slot-successful:a=no`、`slot-retry-count:a=7`；ADB 离线。该模式变化来自用户手动操作，不是 Standalone 自动重启的证据。

**结论边界：** A 槽不可启动状态造成的 Standalone `Load Error` 取证阻塞已解除；这只恢复了 RAM 诊断入口，没有解释 C18 为什么回到 Fastboot。由于没有任何能归属 C18 Android 的 pstore 或 ADB 日志，First/Second Stage、Adreno 路由、EGLConfig、SurfaceFlinger、Vulkan、panic 或 init fatal 均仍未知。当前没有足够证据构建 C19 或将 C18 归因于图形栈。未重启 C18、未刷写/擦除任何分区、未恢复 PixelOS、未改 misc/BCB 或切换 B 槽；Bootloader 未回锁。

后续应先解决 C18 首次失败现场没有留下 Android pstore 的取证缺口，再决定是否重试 C18 或修改图形方案。A 槽状态修改仅限本次用户授权的一次 `set_active a`；不得据此推导出对其他 boot-control 操作的授权。
