# THYME-OS4 Candidate 23：SurfaceFlinger shader-cache prime 绕过实验

日期：2026-09-27（香港时间）  
状态：主机构建、两分区刷写及一次首次启动尝试完成；观察到 Recovery 分支，C23 HyperOS 图形阶段尚未验证。最新设备只读状态见文末。

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

本轮刷写阶段没有执行 `fastboot reboot`、userdata/metadata 擦除、slot 切换、misc/BCB 修改或其他分区写入；没有回锁 Bootloader。后续已单独完成一次经用户现场确认的 C23 启动尝试，结果见下一节。

## C23 首次启动与 Recovery 取证结果

日期：2026-09-27（香港时间）

### 启动观察

- 观察器：`work/reports/20260927_CANDIDATE23_SF_PRIME_SKIP/observations/run_20260927_211900/`。启动前已 `ARMED`；保存的预启动状态为 A 槽、`slot-unbootable=no`、`slot-successful=no`、`retry-count=2`。启动门控记录一次 `fastboot reboot`，命令返回码 0。
- Fastboot 在启动后约 16 秒消失，USB 约 20 秒消失。约 56 秒 ADB 状态为 `unauthorized`，约 61 秒主机识别到 Android Composite ADB Interface；因未授权，不能执行有效 logcat。约 229 秒 ADB/USB 消失，约 232 秒 Fastboot 重新出现。用户报告屏幕进入 PixelOS Recovery；没有启动动画、设置向导或桌面证据。
- `logcat_all_monotonic.txt` 与 `logcat_client_stderr.txt` 均为 0 字节；主机 USB/ADB/Fastboot 时间线完整到 Standalone THYME_DIAG 卷出现。

### Standalone 全量导出

导出目录：`work/reports/20260927_CANDIDATE23_SF_PRIME_SKIP/standalone/run_20260927_212336/`。

Standalone 镜像 SHA-256 为 `8A5803F09CBCB11056D8356F8D235C3C4450846244FA1B4033ABAAACB213E98B`。动态识别到唯一 `THYME_DIAG` FAT32 卷 `F:\`，未依赖固定盘符。全部 7 个可访问文件（共 17,117,150 bytes）复制成功，零复制错误，源端与主机副本逐文件 SHA-256 一致。目录包含 `diag_status.log`、Standalone `dmesg_diag_boot.txt`、16 MiB `oops.raw` 及其校验文件、两项 `System Volume Information` 文件和 `pstore/console-ramoops-0`。本轮未发现 `pmsg-ramoops-0` 或其他 pstore 项。`oops.raw` 与 C22 保存件逐字节同 SHA-256，是历史残留；Standalone dmesg 只描述诊断系统。

### 可确认的 Recovery 路径与边界

- C23 可见 console 中只有一个 Linux 4.19.325 内核实例。Init First Stage 于 1.905 秒开始，紧接着明确输出 `First stage mount skipped (recovery mode)`；Second Stage 于 2.002 秒开始，Recovery 于 3.976 秒开始。因此本份保存的启动实例从 Init 阶段起就是 Recovery 分支，不是 C23 正常 first-stage mount 的记录。
- Recovery 于 3.214 秒输出 `Boot command: bootonce-bootloader`，并于 4.159 秒记录 `Clearing BCB`。这不是 wipe 指令；它能证明 Recovery 读取到该启动命令并随后清除了 BCB，但不能单独证明 Bootloader 为何选中 Recovery，也不能证明启动前 BCB 的内容或第一次启动曾否进入普通 Android。
- 同一 Recovery 分支中的 AVB digest `VerificationDisabled`、`system_ext_a/product_a` 逻辑设备未创建，发生在 Recovery first-stage 跳过挂载之后。它们是本份 Recovery 日志里的后续状态，不能据此认定为 C23 普通系统进入 Recovery 的根因。Recovery 记录未出现 `prompt_and_wipe_data` 或 `--wipe_data`。
- 没有 SurfaceFlinger、Skia、Vulkan、shader-cache prime 的 C23 用户空间记录。故本次不能判断 C23 新属性是否生效，也不能判断 C22 的 buffer-usage fatal 是否被绕过。ADB `unauthorized` 和 Recovery 画面均不足以证明普通 HyperOS 用户空间阶段。
- 证据不足以区分：启动器直接请求 Recovery；C23 普通启动先失败、暖重启后进入 Recovery且此前 pstore 被覆盖；或其他 boot-control/运行时分支。当前最有把握结论仅是“可见 console 属于 Recovery 启动实例，Recovery 进入原因未知”。

### 当前判断与下一步

不构建 C24，也不重复 C23 启动。先在后续受控启动前定点保存 Bootloader 启动模式/槽位信息，并在需要时单独只读核查 BCB；不得擦除或改写 misc。确认 C23 普通启动确实能进入 HyperOS 后，再评估 `service.sf.prime_shader_cache=0` 是否跳过预热以及常规图形合成能否继续。此报告不宣称 C23 修复成功，也不将 Recovery 自身日志当作普通启动错误。

取证导出时，Windows 主机识别到 Standalone `THYME_DIAG` USB 存储卷。随后用户手动切回 Bootloader Fastboot；最新只读查询确认唯一设备 `[REDACTED_DEVICE_ID]`、`product=thyme`、A 槽、`unlocked=yes`、`is-userspace=no`、`slot-unbootable:a=no`、`slot-successful:a=no`、`slot-retry-count:a=1`。启动前重试计数为 2，本次后减为 1。没有恢复 PixelOS、刷写新分区、清除 userdata/metadata、修改 BCB 或回锁。
