# THYME-OS4 Candidate 18 原生 Adreno 复验报告

## 实验结果

- 启动观察器以 `C18-native-adreno` 标记 ARMED；`fastboot reboot` 返回成功。启动前设备为唯一目标 `[REDACTED_DEVICE_ID]`、`product=thyme`、A 槽、Bootloader 已解锁、非 userspace Fastboot。
- ADB 全程未上线，logcat 文件为空。用户看到小米 Logo 常亮，之后由用户手动切回 Fastboot。主机时间线记录 Fastboot 在启动命令后约 348 秒重新出现；该时间线与用户说明一致，不是系统自动重启的证据。
- 启动前 A 槽 `unbootable=no / successful=no / retry=7`；随后只读查询为 `no / no / 6`。这表明本次启动尝试消耗了一次 retry 且未被 Bootloader 标记成功；它不说明 Android 的失败原因。
- C18 Standalone 导出目录：`work/reports/20260926_C18_NATIVE_ADRENO/standalone/run_20260926_234120/`。THYME_DIAG 全部 8 个文件、共 19,305,370 bytes，与源清单中的长度和 SHA-256 全部匹配。原始 `console-ramoops-0` 与 `pmsg-ramoops-0` 均保留；`oops.raw` 与之前 C15–C18 的历史残留同哈希，不作为本次崩溃证据；`dmesg_diag_boot.txt` 只属于 Standalone。

## C18 Android 启动证据

- 原始 console 只有一个 Linux 启动头，内核为 `4.19.325-perf-g45b9b954f074`，启动参数包含 A 槽；First Stage 与 Second Stage Init 均有记录，没有 Kernel panic。
- pmsg 有 8,395 个带时间戳记录，覆盖约 316.715 秒；console 延伸至内核 uptime 321.675839 秒。日志显示 Android 用户空间长期运行，不是只停留在 Bootloader 或 First Stage。
- 实际日志继续记录动态 SELinux policy 加载、APEX、vold、Keymaster/Keystore2 和 `/data` F2FS 挂载及 fscrypt key 安装。`/dev/ion` 的历史 `ion_device` AVC 本轮未出现。
- SurfaceFlinger 有 61 次 `SIGABRT`，并有 61 条 `no suitable EGLConfig found, giving up`。首个错误约在设备日志时间 07:35:28.300；最后一个约在 07:40:26.550。错误来自 `SkiaGLRenderEngine::chooseEglConfig`，重复调用栈指向同一 C18 `libsurfaceflinger.so` Build ID `e0f3e10243eec30f1b2a5c49a656e6db`。
- 报错的参数为 `format: 1`，并报告 `EGL_VENDOR=Android`、`EGL_VERSION=1.4 Android META-EGL`。Android EGL 的公开实现说明 `Android META-EGL` 是 framework wrapper 信息，不能据此确认实际加载了 Adreno 或 ANGLE；本轮 pmsg 也没有 `Adreno`、`ANGLE` 或 `ion_device` 字符串。因此 C18 预设的 native Adreno 路由仍未被运行时直接证明。
- `graphicsengine` 在首个 SurfaceFlinger EGL abort 前约 0.532 秒发生一次 SIGSEGV，栈指向 `/system/lib64/libvulkan.so (vkEnumeratePhysicalDevices+4)`。这是独立进程；时间相邻并不能证明它导致 EGLConfig 失败。之后 EGLConfig abort 持续重现而没有再次记录该 Vulkan 崩溃。
- 同期有 62 次 netd abort、指纹服务 SIGSEGV 与少量 audio.service SIGSEGV；当前没有证据显示它们阻止 Init/APEX/vold 继续运行。pmsg 未见 `bootanimation`、设置向导、桌面或 `sys.boot_completed=1` 已设置的证据（Keystore2 仅记录在监视该属性）。

## EGLConfig 错误的具体含义与边界

Android 17 上游 `SkiaGLRenderEngine` 的选择逻辑先按 ES3、再按 ES2 请求带颜色位、window/pbuffer、recordable 和 framebuffer-target 要求的配置；再失败时会查询简化配置，并按 `EGL_NATIVE_VISUAL_ID` 与传入 `format` 匹配。错误只会在这些尝试最终没有合格配置时触发。`format=1` 对应 `RGBA_8888`。

本轮因此将问题收敛到“当前 EGL 实现不能为 SurfaceFlinger 的 `RGBA_8888` 请求提供合格配置”这一接口兼容点。日志没有枚举 EGL 实际返回的配置，也没有映射表证明后端库，所以尚不能在以下原因中定因：Adreno 驱动未加载/初始化、驱动没有 native visual ID 1、严格属性组合与驱动配置不兼容，或 Xiaomi 二进制与上游选择逻辑存在差异。

上游参考（用于解释接口，不代表 Xiaomi 二进制与 AOSP 完全相同）：

- [Android EGL Loader](https://android.googlesource.com/platform/frameworks/native/+/android-17.0.0_r1/opengl/libs/EGL/Loader.cpp)
- [SkiaGLRenderEngine EGLConfig 选择代码](https://android.googlesource.com/platform/frameworks/native/+/e1d797219097be512bb4a9d844eb7beb2fff7926/libs/renderengine/skia/SkiaGLRenderEngine.cpp)
- [Android PixelFormat 定义：RGBA_8888=1，RGBX_8888=2](https://android.googlesource.com/platform/hardware/interfaces/+/refs/heads/master/graphics/common/aidl/android/hardware/graphics/common/PixelFormat.aidl)
- [SurfaceFlinger 默认组合像素格式属性](https://android.googlesource.com/platform/frameworks/native/+/1de74a7c7cd27ced6cc34f8259df62221243f7d3/services/surfaceflinger/sysprop/SurfaceFlingerProperties.sysprop)

## 下一步 Candidate 19 选择

不撤销 C18 的 Adreno 路由，也不替换 GPU/Vulkan/HWC 库。下一版采用一个直接由错误参数支持的最小实验：在 C18 基线上新增只读系统属性 `ro.surface_flinger.default_composition_pixel_format=2`，让 SurfaceFlinger 以 `RGBX_8888` 请求 EGL 配置。若日志中的 format 随之变为 2 且 RenderEngine 初始化成功，可验证 C18 的 RGBA_8888 native-visual 兼容性假说；若仍失败，则按新的 format 和实际日志决定是否需要 EGL 配置枚举诊断，不盲目放宽权限或更换整套驱动。

此属性会改变 SurfaceFlinger 对默认合成像素格式的期望，可能影响 HWC/Gralloc 配合；它是可回退的显示格式实验，不改内核、SELinux、vold、userdata/metadata 或硬件身份分区。此处记录的是待构建/待实机验证的实验，不是已确认根因或已完成修复。

## 本轮设备边界

- 本轮没有 Candidate 分区刷写、数据擦除、BCB/misc 修改或 Bootloader 状态改变。
- 2026-09-27 的只读 Fastboot 查询仍为唯一 `[REDACTED_DEVICE_ID]`、thyme、A 槽、unlocked=yes、非 userspace Fastboot；A 槽 `unbootable=no / successful=no / retry=6`。
- PixelOS A0′ 本轮未启动验证；设备当前仍是 Fastboot，C18 仍为本次实验写入状态。
