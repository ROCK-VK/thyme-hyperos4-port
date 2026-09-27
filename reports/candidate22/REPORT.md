# THYME-OS4 Candidate 22：K40 Android 17 Vulkan UMD 配套实验

日期：2026-09-27（香港时间）
状态：主机构建与指定分区刷写完成；设备保持 Bootloader Fastboot，C22 首次启动待用户现场确认。

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

## 首次启动验收目标

C22 尚无实机运行结果。首次启动要验证 SurfaceFlinger 是否越过 C21 的 SkiaVk 初始化 fatal，并观察是否出现 bootanimation、设置向导或桌面；同时记录 Vulkan ICD 装载、初始化结果，以及 graphicsengine 的独立 Vulkan 崩溃是否继续出现。K40 UMD 与 thyme 4.19/KGSL 的运行时兼容性仍待验证。

用户现场准备后，先启动只读观察器并确认 ARMED，再调用 `tools/start_candidate22_observed_boot.ps1`。未取得现场确认前不启动。失败后先按已授权 Standalone 流程全量保存原始诊断卷，再分析日志。

## 构建产物与工具

- 构建脚本：[build_candidate22_k40_vulkan_umd.py](../../tools/build_candidate22_k40_vulkan_umd.py)
- 受限刷写脚本：[flash_candidate22_k40_vulkan_umd.ps1](../../tools/flash_candidate22_k40_vulkan_umd.ps1)
- 首启门控：[start_candidate22_observed_boot.ps1](../../tools/start_candidate22_observed_boot.ps1)
- 六镜像清单：[构建清单](BUILD_MANIFEST.json)
- 主机构建摘要：[主机构建摘要](BUILD_REPORT.md)
