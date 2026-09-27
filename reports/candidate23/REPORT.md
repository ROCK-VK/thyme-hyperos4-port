# THYME-OS4 Candidate 23：SurfaceFlinger shader-cache prime 绕过实验

日期：2026-09-27（香港时间）
状态：主机构建、两分区刷写完成；设备保持 Bootloader Fastboot，C23 首次启动等待用户现场确认。

## C22 依据

C22 pmsg 于 2026-09-27 首启后保存了 89 次相同 SurfaceFlinger fatal：`output buffer not gpu writeable`。首个时间戳为 `01-20 03:58:35.026`，栈明确经过 `SkiaRenderEngine::drawLayersInternal`、`RenderEngine::drawLayers`、`Cache::primeShaderCache` 和 `SkiaRenderEngine::primeCache`。BootAnimation 随 SurfaceFlinger 退出而反复退出。First/Second Stage、APEX、`/data` 与 vold 初始化均有推进。

C22 pmsg 中未检出 C21 的 Vulkan RenderEngine fatal、EGLConfig 错误、`vkEnumeratePhysicalDevices` 或 `graphicsengine` 文本。因此可以确认 SurfaceFlinger 越过了 C21 的 RenderEngine 创建 fatal 并进入 shader-cache 预热；日志没有标明实际 Vulkan ICD/后端，不能声称 K40 UMD 已成功初始化。buffer 的 `HW_RENDER` usage 最终缺失的底层原因尚未定位。

证据目录：

- 主机观察：`work/reports/20260927_CANDIDATE22_K40_VULKAN_UMD/observations/run_20260927_195701/`
- Standalone 全量副本：`work/reports/20260927_CANDIDATE22_K40_VULKAN_UMD/standalone/run_20260927_200710/`
- C22 原始文件 8/8 已完整复制；源与副本文件大小及 SHA-256 全部一致。`dmesg_diag_boot.txt` 是 Standalone 自身日志；`oops.raw` 不含 C22 特征，属于历史/诊断残留。

## C23 改动与验证

唯一系统改动是在 `/system/build.prop` 增加：

```properties
service.sf.prime_shader_cache=0
```

Android 17 上游 SurfaceFlinger 在该属性为非零时调用 `primeCache()`；C23 将其关闭，以跳过实机栈已经确认的可选启动 shader 预热。该改动用于观察 SurfaceFlinger 是否能进入常规显示初始化，以及普通绘制是否仍会触发同一 buffer usage fatal；**这只是诊断性绕过，不代表底层 gralloc/GraphicBuffer usage 不匹配已修复。**

其余 C22 Vulkan UMD/vendor、C21 SkiaVk RenderEngine 配置、C13–C22 已验证修复、thyme 内核与硬件栈均保留。没有改 SELinux、EGL/GLES、HWC/Gralloc、Vulkan 库、fstab、userdata 或 metadata。

主机检查通过：

- 由保留的 C1 `system/fs_config` 和当前 C21 system tree 按 C14/C15 的既有派生规则重建 fs_config；不依赖已清理的临时 C15 scratch 文件。
- C23 system EROFS `fsck.erofs` 通过；从最终 EROFS 回读 `build.prop`，新增属性及继承的 C20/C21 图形属性均恰好出现一次。
- system AVB hashtree 更新；`vbmeta_system` 仅替换 system descriptor，product/system_ext descriptor、AVB header 标志和索引保留。
- 使用 C22 的 Vulkan vendor image 及相同 A 槽逻辑分区输入重建 super；`lpdump` 检查目标分区和 system/system_ext/vendor extent。
- C22 继承的 boot、vendor_boot、dtbo、root vbmeta 与 vbmeta_system 基线按 C22 manifest 核对。构建阶段没有重新计算 C22 7.7 GB super 哈希。

构建结果：`work/stage_m_thyme_os4_candidate_23_sf_prime_skip_run4/`；六镜像清单：`images/BUILD_MANIFEST.json`。首版构建批次因旧 scratch fs_config 缺失而停止；后续两个主机批次修正 AVB parser 返回值解包错误；所有失败批次均保留且未连接设备。最终 run4 构建完成。

| 镜像 | 大小 | SHA-256 | 本轮写入 |
|---|---:|---|---|
| `boot.img` | 201,326,592 | `E5A016056D5C93C7A886980A7C062617EC44DC06A48417D7DD0F4476708A6368` | 否，继承 |
| `vendor_boot.img` | 100,663,296 | `02333B82BA936F1BAAB1ECAB744632C70F8FC16688A206C7041EF319F112A137` | 否，继承 |
| `dtbo.img` | 33,554,432 | `50E1AC0EDCBD333778217AA6FE8D972F6FF85ADD0DAE8A015A6642C2172DD886` | 否，继承 |
| `vbmeta.img` | 131,072 | `66A53C2EC38247193CC86B7F5DE887556864413D1142C3C1994645DE1E3BAB10` | 否，C22 root vbmeta 保持 |
| `vbmeta_system.img` | 131,072 | `B0FFDFD7FD492F17ABD6FDC0F3577C6F9C1976C8087B6A21E77191FA1A624F46` | `vbmeta_system_a` |
| `super.img` | 7,701,892,056 | `F0E252E232D12AEB8E84D9A56B77B39744D6972FD8E695618A10E89168209A15` | `super` |

## 刷写与设备状态

2026-09-27 20:35（香港时间）受限脚本先核验镜像大小/SHA-256，再只读预检唯一设备 `[REDACTED_DEVICE_ID]`、`product=thyme`、A 槽、unlocked、Bootloader Fastboot、A 槽 `unbootable=no`。随后仅写入 `super` 与 `vbmeta_system_a`：super 10/10 sparse 块全部 `OKAY`，vbmeta_system 写入 `OKAY`。刷后 Fastboot 复查确认仍为 `thyme`、A 槽、unlocked、`is-userspace=no`、A 槽可启动、retry-count=2。

本轮没有执行 `fastboot reboot`、userdata/metadata 擦除、slot 切换、misc/BCB 修改或其他分区写入；没有回锁 Bootloader。C23 尚未启动，实机效果待现场观察。

下一步：用户确认在场后，先运行 C23 观察器并确认 ARMED，再通过 `tools/start_candidate23_observed_boot.ps1` 执行一次受控首次启动。观察 primeCache 是否跳过、SurfaceFlinger 是否稳定、是否进入 bootanimation/设置向导/桌面，以及常规输出 buffer 是否触发同类 fatal。失败后先按既有授权完整保存 Standalone 诊断卷，再分析。
