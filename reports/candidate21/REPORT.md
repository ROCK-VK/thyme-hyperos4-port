# THYME-OS4 Candidate 21：K40 Skia Vulkan RenderEngine 路由

日期：2026-09-27
状态：主机构建与指定分区刷写完成；尚未首次启动，等待用户现场确认。

## 结论

C20 的真实 SurfaceFlinger 路径是 `SkiaGLRenderEngine`，在 `chooseEglConfig()` 以 `format=2` 反复失败。pmsg 中 EGL 对外报告 `vendor=Android`、`version=1.4 Android META-EGL`，扩展列表也没有暴露 Adreno 或 ANGLE 身份。现有记录证明了 SurfaceFlinger 走 GL/EGL 初始化，却不能确认 META-EGL 后面实际分派到 ANGLE 还是 Adreno，也没有配置枚举数量，因此不能区分“没有 EGLConfig”与“属性筛选后无匹配项”。

K40 Android 17 OS4.0.0.8 成功移植包没有替换 system EGL Loader 或 SurfaceFlinger/RenderEngine：缓存中的 `surfaceflinger`、`libgui`、`libui`、`libvulkan`、`libEGL`、`libEGL_angle` 与 C20/Xiaomi 15 供体对应文件 SHA-256 一致。K40 的直接图形适配在其 `/product/etc/build.prop` 中：

```properties
debug.renderengine.vulkan=true
debug.hwui.renderer=skiavk
ro.hwui.use_vulkan=true
debug.renderengine.backend=skiavkthreaded
```

Android SurfaceFlinger 源码将 `debug.renderengine.backend=skiavkthreaded` 映射到 threaded Skia Vulkan RenderEngine；当前 C20 `libsurfaceflinger.so` 也包含 RenderEngine backend 属性和 SkiaVk 实现标识。[AOSP RenderEngine backend selection](https://android.googlesource.com/platform/frameworks/native/%2B/1b685dd3b6373ba55be1c57c672a22533e16664d%5E2..1b685dd3b6373ba55be1c57c672a22533e16664d/) [AOSP SurfaceFlinger RenderEngine implementation](https://android.googlesource.com/platform/frameworks/native/%2B/b956058d7fcd3057cd0329b2098caa3c1977174d/libs/renderengine/RenderEngine.cpp)

因此 C21 采用这条已用于 K40 的渲染路径，目标是绕开当前失败的 SkiaGL EGLConfig 初始化。它是有成功移植包依据的启动路径适配，不等于已经修复底层 EGL 驱动或证明 thyme Vulkan 工作正常。

## C21 实际改动

基于 C20 system tree 只新增以下三项 debug 属性：

```properties
debug.renderengine.vulkan=true
debug.hwui.renderer=skiavk
debug.renderengine.backend=skiavkthreaded
```

保留 C20 的 `persist.graphics.egl=angle`、属性加载后的 ANGLE init 动作、RGBX `format=2`、C13–C19 已验证修复、thyme 内核与硬件栈。没有替换 K40 vendor/Vulkan/Gralloc/HWC 文件，没有改 fstab、SELinux、userdata/metadata 或硬件身份分区。

K40 profile 中的 `ro.hwui.use_vulkan=true` 未加入 C21：thyme vendor build.prop 对该 `ro.*` 属性给出空值，而 C21 不重建 product；C21 使用 `debug.hwui.renderer=skiavk` 作为直接的 HWUI 路由覆盖。AOSP HWUI 的 renderer debug 属性优先于默认 Vulkan 设置。[AOSP HWUI renderer property handling](https://android.googlesource.com/platform/frameworks/base/%2B/f7cffb7b2b5865f913c557f811b76d770125ddfc/libs/hwui/Properties.cpp)

## Vulkan 风险与验证边界

C20 pmsg 另有 `/system/bin/graphicsengine` 在 `MiVulkanPipelineCacheBuilder` 中通过 `vkEnumeratePhysicalDevices+4` 发生空指针 SIGSEGV。这是独立进程的真实风险；目前没有证据证明该崩溃与 SurfaceFlinger EGLConfig 失败有因果关系，也没有证据证明 SkiaVk RenderEngine 能在 thyme vendor 驱动上成功初始化。

K40 与 thyme 的 vendor Adreno/Vulkan 二进制并不相同（例如缓存中 K40 `vulkan.adreno.so` 约 4.74 MB，thyme 约 2.23 MB）。C21 不复制这些硬件相关库，首次启动需要直接观察 SkiaVk 是否初始化、是否仍有 Vulkan fatal，以及是否越过米标。

## 构建与刷写

- 构建脚本：[build_candidate21_k40_vk_renderengine.py](../../tools/build_candidate21_k40_vk_renderengine.py)
- 刷写脚本：[flash_candidate21_k40_vk_renderengine.ps1](../../tools/flash_candidate21_k40_vk_renderengine.ps1)
- 启动门控：[start_candidate21_observed_boot.ps1](../../tools/start_candidate21_observed_boot.ps1)
- 清单及六镜像：[BUILD_MANIFEST.json](BUILD_MANIFEST.json)

主机检查通过：最终 system EROFS fsck 与属性回读成功；system AVB hashtree 更新，product/system_ext descriptors 保持不变；LP dump 显示预期 A 槽逻辑分区与原布局；C20 继承的 `boot/vendor_boot/dtbo/vbmeta` 大小和 SHA-256 一致。C21 manifest 记录全部六镜像大小及 SHA-256。

实际写入仅两项：

| 分区 | 结果 | 镜像大小 | SHA-256 |
|---|---|---:|---|
| `super` | 成功，10/10 sparse 块 `OKAY` | 7,684,274,964 | `C8BF3F895639C648D947E201E9E12EFCB7CCA33B63B0EAA807AE4672939EC2DF` |
| `vbmeta_system_a` | 成功 | 131,072 | `E3A2807CE59CFAF93BEF7E08EE45A1D055DE1264FFEA8F6E8EED06893892AC74` |

刷写前后只读状态为设备 `thyme`、A 槽、Bootloader unlocked、非 userspace Fastboot；刷后 A 槽 `unbootable=no`、`successful=no`、`retry-count=4`。没有擦除 userdata/metadata、没有改其他分区、没有发出启动命令。

## C21 首次启动观察

C21 尚未启动。现场确认后，先运行：

```powershell
python tools/observe_candidate13_readonly.py --candidate C21-k40-vk-renderengine --output-base work/reports/20260927_CANDIDATE21_K40_VULKAN_RENDERENGINE/observations --seconds 600
```

观察器出现 `[ARMED]` 后，再由启动门控脚本检查新鲜 ARMED、设备身份及 A 槽状态，执行一次 Fastboot reboot。ADB 一旦上线，观察器会采集完整 logcat、启动属性（包括三个 C21 renderer 属性）和图形进程 maps；失败时仍需按既有 Standalone 流程完整导出诊断卷后再分析。

主要验收点：SurfaceFlinger 是否报告 threaded SkiaVK backend；是否进入 `bootanimation`、设置向导或桌面；SkiaVk/Vulkan 初始化是否失败；`graphicsengine` Vulkan 崩溃是否仍出现。C21 不会提供 EGLConfig 数量或过滤结果；如果 SkiaVk 路由无法启动，再按真实现场决定是否需要 EGL hook，而非预先改写图形二进制。
