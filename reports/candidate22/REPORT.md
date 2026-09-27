# THYME-OS4 Candidate 22：K40 Android 17 Vulkan UMD 配套实验

日期：2026-09-27（香港时间）
状态：主机构建、指定分区刷写及一次首次启动完成；Standalone 全量取证已完成。C22 未进入 HyperOS 启动画面、设置向导或桌面。

## 依据与目标

C21 的 pmsg 证明 Second Stage、APEX Bootstrap、`/data` 与 vold 初始化已推进。SurfaceFlinger 随后反复以 `Could not initialize Vulkan RenderEngine!` 在 `SkiaVkRenderEngine::createContexts()` fatal；相邻的 `graphicsengine` 另在 `vkEnumeratePhysicalDevices+4` 空指针崩溃，但进程不同，因果关系未确认。

对照 C21 实际使用的 Xiaomi 15 provider `vendor.img` 后，C21 Vulkan ICD 所需的部分 GSL API 不存在于配套 thyme `libgsl.so`。K40 成功 Android 17 包的 Vulkan UMD 提供这些接口；但直接覆盖同名 GSL/LLVM/Adreno Utils 会丢失旧 thyme EGL/GLES 依赖的导出符号。C22 因此只把 K40 UMD 配套限定给 Vulkan ICD，并保留原 EGL/GLES 栈。

## 实际修改

在 C1 provider vendor 的私有构建副本中：

- 将 `/vendor/lib64/hw/vulkan.adreno.so` 替换为缓存的 K40 OS4.0.0.8 Android 17 ICD。
- 增加 `libgsl_k40.so`、`libadreno_utils_k40.so`、`libllvm-glnext_k40.so` 与 K40 `libllvm-qgl.so`。新文件保持 root:root、0644 和 `u:object_r:same_process_hal_file:s0`。
- 只修改 K40 ICD/配套 UMD 副本的相关 `DT_NEEDED`，让 Vulkan 路径使用独立 SONAME；`libllvm-glnext_k40.so` 仍可按其运行时 `dlopen("libllvm-qgl.so")` 找到新增的 qgl 文件。
- 原 thyme `libgsl.so`、`libadreno_utils.so`、`libllvm-glnext.so`、EGL/GLES、Gralloc/HWC、内核和设备专属启动镜像保留。
- 重建 vendor AVB hashtree，并在 root `vbmeta.img` 中仅替换 vendor hashtree descriptor。`vbmeta_system.img` 未变。

C17 的 system_ext 中间镜像已不在当前 WSL 构建目录；C22 从 C21 已构建的 raw super 提取 `system_ext_a`，并将该分区原样用于 LP 重打包。其余 LP 几何和 A 槽分区 extent 沿用 C21。

## 主机验证与写入

- vendor ext4 `e2fsck -f -n` 通过；`avbtool verify_image` 确认 vendor footer 与 SHA-256 hashtree 有效。
- 新 root vbmeta 的 vendor digest 为 `743d0bfebb1dfd42ebf55d37321702a8529546396c72716676f28cc48987c857`；其余 root descriptors、flags=3、rollback index 与位置保持不变。`vbmeta_system.img` 哈希与 C21 相同。
- `lpdump` 验证了 A 槽逻辑分区和 `vendor_a` 的 1,510,998,016-byte extent；boot、vendor_boot、dtbo、vbmeta_system 与 C21 manifest 哈希一致。
- 受限刷写脚本仅写 `super` 和 `vbmeta_a`。`super` 10/10 sparse 块全部 `OKAY`，`vbmeta_a` 写入返回 `OKAY`。刷写后只读确认设备仍为 `thyme`、A 槽、Bootloader unlocked、Bootloader Fastboot、A 槽 `unbootable=no`，retry-count=3。
- 未执行启动、userdata/metadata 擦除、Bootloader 状态操作或其他分区写入。

| 镜像 | 大小 | SHA-256 | 分区 | 实际结果 |
|---|---:|---|---|---|
| `super.img` | 7,701,892,056 bytes | `6145D602D17321EFF1AD55A7AC10B9314AF9E7C23C0BD60D681115CD54B1330D` | `super` | 10/10 块写入成功 |
| `vbmeta.img` | 131,072 bytes | `66A53C2EC38247193CC86B7F5DE887556864413D1142C3C1994645DE1E3BAB10` | `vbmeta_a` | 写入成功 |

## C22 首次启动实机结果

- 观察器：`work/reports/20260927_CANDIDATE22_K40_VULKAN_UMD/observations/run_20260927_195701/`；标签 `C22-k40-vulkan-umd`。`fastboot reboot` 于 2026-09-27 11:57:19.246 UTC 返回成功；Fastboot 约 19 秒后消失，主机 USB 约 23 秒后消失，约 491 秒后重新枚举为 Fastboot。用户观察到米标持续亮屏，随后手动返回 Fastboot；ADB 从未上线。
- Standalone 全量副本：`work/reports/20260927_CANDIDATE22_K40_VULKAN_UMD/standalone/run_20260927_200710/`。诊断卷全部 8 个可访问文件和系统生成目录均已复制；逐文件大小与 SHA-256 对照零错误。源文件和本地原件保留。`dmesg_diag_boot.txt` 属于 Standalone；`oops.raw` 不含本轮 C22 标记，属于历史/诊断残留，不能作为 C22 故障日志。
- C22 pmsg 跨越 `01-20 03:58:18.399` 至 `04:05:56.089`。日志中有一次 Android First Stage 和一次 Second Stage；`/data` 挂载及 vold/密钥初始化推进。该 pmsg 中未出现 C21 的 `Could not initialize Vulkan RenderEngine!`、`no suitable EGLConfig found`、`vkEnumeratePhysicalDevices` 或 `graphicsengine` 文本。
- pmsg 有 89 次完全相同的 SurfaceFlinger fatal：`output buffer not gpu writeable`；对应栈包含 `SkiaRenderEngine::drawLayersInternal`、`RenderEngine::drawLayers`、`Cache::primeShaderCache` 和 `SkiaRenderEngine::primeCache`。首发于 `01-20 03:58:35.026`，之后 SurfaceFlinger 与 BootAnimation 反复退出。C22 console 只有一个 Linux version、一次 First Stage、一次 Second Stage，最后可见时间约 462.109 秒；没有证据显示 kernel panic。
- Android 17 AOSP `SurfaceFlinger.cpp` 读取 `service.sf.prime_shader_cache`（默认值为 `1`），非零时调用 `RenderEngine::primeCache()`；`Cache.cpp` 用包含 `HW_RENDER | HW_TEXTURE` 的 buffer 做预热，而 RenderEngine 会在缺少 `HW_RENDER` 时以该 abort message fatal。C22 的实际调用栈与这条代码路径一致。**已确认的直接阻塞是 shader-cache 预热输出 buffer 的 usage 检查；底层为何最终缺少 GPU_RENDER bit，当前仍未证实。**
- C22 pmsg 没有记录实际 Vulkan ICD/ANGLE/Adreno 的库路径或后端身份。因此日志证明 SurfaceFlinger 已越过 C21 的 RenderEngine 创建 fatal 并运行到 Skia `primeCache`，但不能据此声称 K40 Vulkan UMD 已被成功选中或初始化完成。
- 其他同时出现的 fingerprint SIGSEGV、netd abort 及 perf/HWC AVC 暂不作为本轮首要阻塞；尚无证据表明它们造成上述明确的 SurfaceFlinger fatal。

## C23 最小实验方向

保留 C22 全部图形及历史修复，在 system `build.prop` 增加 `service.sf.prime_shader_cache=0`，只跳过 SurfaceFlinger 的可选 shader cache 预热。此设置针对本轮栈中明确的触发路径，不修改 Vulkan/EGL/HWC/Gralloc/SELinux、内核或数据挂载。它是让启动继续向后暴露下一阶段并判断常规绘制是否也受相同 buffer usage 问题影响的诊断性绕过；不代表已修复底层 allocator/usage 不匹配。

官方上游依据：Android 17 `SurfaceFlinger.cpp` 的该属性读取与条件调用：[SurfaceFlinger.cpp](https://android.googlesource.com/platform/frameworks/native/+/f6923a1061775ca0e97979015aa018930f0a5661/services/surfaceflinger/SurfaceFlinger.cpp)；`Cache.cpp` 的预热 buffer usage：[Cache.cpp](https://android.googlesource.com/platform/frameworks/native/+/e22a90373cd92aa5429d1318a6d3005609e8ab9f/libs/renderengine/skia/Cache.cpp)；RenderEngine usage fatal：[RenderEngine.cpp](https://android.googlesource.com/platform/frameworks/native/+/8e9a856f72/libs/renderengine/RenderEngine.cpp)。上游说明用于解释日志路径，最终运行时判断仍以 C22 实机 pmsg 为准。

## 构建产物与工具

- 构建脚本：`tools/build_candidate22_k40_vulkan_umd.py`
- 受限刷写脚本：`tools/flash_candidate22_k40_vulkan_umd.ps1`
- 首启门控：`tools/start_candidate22_observed_boot.ps1`
- 六镜像清单：`work/stage_l_thyme_os4_candidate_22_k40_vk_umd_run5/images/BUILD_MANIFEST.json`
- 主机构建摘要：`work/stage_l_thyme_os4_candidate_22_k40_vk_umd_run5/BUILD_REPORT.md`
