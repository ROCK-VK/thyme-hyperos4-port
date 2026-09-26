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
- 新启动门控脚本：`tools/start_candidate18_observed_boot.ps1`，需要 C18 observer 的新鲜 ARMED 记录和显式现场确认开关；本报告生成时尚未用于启动。
- Observer `tools/observe_candidate13_readonly.py` 的属性快照已补入 `persist.graphics.egl`、`ro.hardware.egl`、`ro.hardware.vulkan`、`ro.board.platform`，实际 C18 启动应以运行时快照为准。
- system EROFS `fsck.erofs` 通过；从最终 `super` 提取的 `system_a.img` 与独立 C18 system 镜像逐字节相同，SHA-256 均为 `688d47c20002826231843fce53a42f77f2c9f510494af632bff653bc35eb38d5`，提取镜像 EROFS 检查通过。
- `vbmeta_system.img` 中 `system` hashtree descriptor root digest 与 C18 system 一致；`product` 和 `system_ext` descriptor 的 image size/root digest 沿用 C17。LP dump 确认 A 槽 `mi_ext_a`、`odm_a`、`product_a`、`system_a`、`system_ext_a`、`vendor_a` 保持 C17 布局。
- Python 编译检查、PowerShell AST 语法检查及刷写脚本 Dry-Run 通过。脚本计划仅顺序写 `super`、`vbmeta_system_a`，无自动 reboot。

镜像位置：`work/stage_h_thyme_os4_candidate_18_native_adreno_run1/images/`。大小与 SHA-256 见同目录 `BUILD_MANIFEST.json`。

## 实机结果与下一步

- C18 已刷写到 thyme：`super` 的 10/10 sparse 块全部 `OKAY`，Fastboot 用时 206.216 秒；随后 `vbmeta_system_a` 发送与写入均 `OKAY`，Fastboot 用时 13.321 秒。
- 刷后只读复核：唯一设备 `[REDACTED_DEVICE_ID]`、`product=thyme`、`current-slot=a`、`unlocked=yes`、`is-userspace=no`；Fastboot 在线，ADB 不在线，没有残留 fastboot 写入进程。
- 本次没有重启、擦除 userdata/metadata、写其他分区、修改 BCB/misc 或恢复 PixelOS。手机保持 Bootloader Fastboot，等待用户在场确认。
- C18 尚无真机启动验收结果；C17 实际 EGL 后端、最终 EGLConfig 根因和 Vulkan SIGSEGV 的因果均未闭合。

首次启动前使用 `tools/observe_candidate13_readonly.py --candidate C18-native-adreno --output-base work/reports/20260926_CANDIDATE18_NATIVE_ADRENO/observations`，等待 `[ARMED]` 并确认用户在场后，才使用启动脚本进行一次 Fastboot reboot。Observer 将捕获后端相关属性与完整 logcat；如启动失败，再由用户手动返回 Fastboot 后运行已授权的 Standalone 全量取证。

验收重点：C18 是否仍有 24 次 EGLConfig abort、SurfaceFlinger 是否推进、运行时属性是否为 `persist.graphics.egl=adreno`，以及 logcat/pstore 是否出现实际 native EGL/Adreno 初始化信息。Vulkan SIGSEGV 是否仍出现需单独记录，除非新的调用证据出现，否则不将它与 EGLConfig 故障合并归因。
