# THYME-OS4 项目当前状态

## 目标与当前阶段

将 Xiaomi 15（dada）的 HyperOS 4 / Android 17 用户空间移植到 Xiaomi Mi 10S（thyme）。当前优先让设备越过米标，进入 HyperOS 启动画面、设置向导或桌面。非开机关键功能暂缓。

当前阶段：C26 Zygote 首因诊断版已构建并刷写，尚未启动。C25 的 55 个连续样本证明 zygote/zygote_secondary 长时间处于 `restarting`，system_server/zygote64 不存在；退出首因未保存。C26 保留 C25 诊断并新增 logcat 持久采集和 Zygote 属性/进程转换记录，目标是在首次启动后捕获真实退出错误。

## 当前设备与刷入状态

- C26 刷写前只读查询确认唯一 thyme、A 槽、Bootloader 解锁、非 userspace Fastboot；A 槽 `unbootable=no`、`successful=no`、`retry=2`。刷写脚本结束后再次确认设备仍在 Bootloader Fastboot，未启动。
- C26 仅刷写 `super` 与 `vbmeta_system_a`。`super` 10/10 sparse chunks 均成功，写入耗时约 194 秒；`vbmeta_system_a` 发送与写入均成功。未进行分区回读，故只记录 Fastboot 写入命令成功。
- C26 `super.img`：7,703,583,704 bytes，SHA-256 `601FF7548F658442B9F17176FB2AC391791E1453660E55A41D8B292E1E290E62`；`vbmeta_system.img`：131,072 bytes，SHA-256 `194000046E3FA288322D4D9D01B65559042DBCB27E3E354C986796888ABA40A3`。
- C26 继承 C25 引导镜像、thyme 硬件栈和持久诊断；未执行 reboot、userdata/metadata 擦除、set_active、BCB/misc 操作、PixelOS 恢复或其他分区写入，未回锁 Bootloader。PixelOS 未恢复。设备端分区未回读，实际启动状态尚未验证。

## C25 持久化首屏诊断

- 构建：work/stage_o_thyme_os4_candidate_25_first_screen_diag_20260928_run5/images/；报告：work/reports/20260928_C25_FIRST_SCREEN_DIAG/C25_FIRST_SCREEN_DIAGNOSTIC_BUILD_FLASH_20260928.md。
- C24 的 logd-only shell sampler 被 AArch64 原生有界 helper 替代；显式使用现有 shell SELinux domain，启动标记和样本写入 logd 及 /metadata/thyme_os4_diag 持久文件，逐条 fdatasync。
- 属性/PID 每 15 秒、Framework/display dumpsys 约每 60 秒，单条查询 4 秒超时；15 分钟配置，单文件 512 KiB、总目录 8 MiB 上限。实机证明 post-fs-data 触发、文件打开并保存 56 个样本；未到 900 秒截止，无 COMPLETE。
- Standalone 独立镜像增加 `--export-c25-metadata`：sysfs 唯一识别 metadata、校验设备号/容量，以 ext4 `ro,noload` 挂载并仅复制诊断子树。run2 因 mount 表用精确 token `norecovery` 而安全停止，未读取 metadata。run3 修正校验后实机匹配 `/dev/sda18`（uevent major/minor 259:2，节点 stat 十六进制 103:2）、16 MiB；挂载为 `ext4,ro,relatime,norecovery`，只读导出两文件且 0 mismatch。run3 镜像 201,326,592 bytes，SHA-256 `EB6E47DBEBFB6469EC0178D17F793538A6C0A41FA09DB4DBC5C04034B2AB65E0`。
- C25 首轮 Standalone 全卷副本位于 `work/reports/20260928_C25_FIRST_SCREEN_DIAG/standalone/run_20260928_233210/THYME_DIAG/`，可访问文件 5 个、4,197,876 bytes，源/副本 SHA-256 5/5 一致。run3 全卷副本位于 `standalone/run_20260928_234427_meta_ro/THYME_DIAG/`，8 个文件、4,272,050 bytes、2 个目录，大小/SHA 8/8 一致；无 pstore 文件。完整 `misc.raw` 与其散列只保存在本地，不公开上传。
- C25 没有调整 GPU/HWC、内核、fstab、加密路径或硬件分区，也没有新增 IMiHwcExtension 宽泛 SELinux allow。K40 定点资料未提供可直接套用且能证明修复本机现象的通用 Framework/HWC 修复。

## C26 Zygote 首因诊断版

- 构建目录：`work/stage_c26_zygote_diag_20260929_run2/images/`；构建/刷写报告：`work/reports/20260929_C26_ZYGOTE_FIRST_EXIT/C26_BUILD_FLASH_STATUS.md`。
- K40 Android 17 成功包、Xiaomi 15 供体与 C25 的 Zygote rc、app_process32/64、`libandroid_runtime.so`、classpath PB、ART/runtime APEX 定点比较逐字节一致；未发现可复用的 K40 Zygote/ART 修复，因此 C26 是诊断增量，不混入无证据系统修复。
- 新 helper 在 `post-fs-data` 后启动 logd 全 buffer 轮转采集（最多 4×1 MiB），并用 Bionic property-wait 监视 zygote、zygote_secondary 等状态；检测重启时记录可见进程信息并截取最多 8 次 crash/system/main 尾部。C25 sampler 保留；未改 SELinux CIL、GPU/HWC、ART、内核、fstab、属性或加密路径。
- 构建器报告 EROFS 内容检查、system AVB footer 验证、vbmeta_system 更新、LP/Super 构建和逻辑输入校验完成；待刷镜像大小/SHA 与构建清单一致。helper 为 Android AArch64 PIE，源码通过 `-Wall -Wextra -Werror` 编译。
- 尚未验证：C26 诊断服务能否在真机启动、logcat 是否成功持久化、Zygote 首次退出原因及是否进入后续启动阶段。

## C25 实机诊断结论（历史基线）

- `/metadata/thyme_os4_diag` 中的 `C25_INIT_TRIGGER.txt` 证明 init post-fs-data 触发；helper 日志 `START ... file=open` 证明进程启动并成功打开持久文件。共保存 56 个样本（第 1 个在 uptime 15.310s 时服务尚未完全就绪；其后 55 个样本约每 15s）。最后样本 uptime 842.681s、helper elapsed 827.404s；没有 `COMPLETE` 标记，故不能说采样完整跑满设定的 900 秒。
- 后续 55 个样本一致：`init.svc.zygote=restarting`、`zygote_secondary=restarting`、`init.svc.netd=restarting`；system_server、zygote64、SystemUI、HOME、SetupWizard PID 均为 none；SurfaceFlinger 和 bootanimation PID 分别为 1467、2227，状态 running；`service.bootanim.exit=0`，`sys.boot_completed` 报为 empty/unreadable。Window、Activity、Display dumpsys 持续返回 service-not-found；SurfaceFlinger dumpsys 和 BootAnimation layer 可读取。
- SurfaceFlinger 识别 HWC display 0、`PresentFences=true` 并列出 BootAnimation layer，但没有成功 present/fence 完成或用户实际收到该 layer 的证据。用户观察为中央小米 Logo + `powered by Android` 第一屏；不能据此确认 HyperOS 第二屏，也不能断言物理显示链根因。
- 已有 C23/C24 pmsg 同样反复出现 `ZygotePid: -1`，且没有 `AndroidRuntime`/`ZygoteInit` 明确错误文本；这些旧日志不够说明 init zygote 状态，也未给出退出根因。C25 首次明确的持续状态证据把下一问题定位到 zygote 重启环，不代表根因已找到。
- C25 的 logcat 缺失由 C26 诊断增量针对处理；C26 的真实服务启动和数据留存仍待实机验证。
- 磁盘门禁：2026-09-29 01:01 HKT 实测 C/D/E 可用空间为 76.95/119.53/176.11 GiB；C 低于 80 GiB，暂不进行重型构建。E 盘 C13.1 未上机 stage（44.42 GiB）仍保留；此前精确递归删除被执行策略拒绝，本轮未绕过。D 盘 Ubuntu VHDX 164.64 GiB，此前压缩因占用失败，本轮未重试。Docker 未访问或修改。
- run3 取证后用户报告已返回 Bootloader Fastboot；但主机 `fastboot devices` 未枚举到设备。需要先恢复 USB Fastboot 枚举，再进行设备查询或操作。
## C21 当前实现

基于 C20 system tree，仅新增 K40 OS4 配置中与 SurfaceFlinger/HWUI Vulkan 路由直接相关的三项：

- `debug.renderengine.vulkan=true`
- `debug.renderengine.backend=skiavkthreaded`
- `debug.hwui.renderer=skiavk`

保留 C20 `persist.graphics.egl=angle`、持久属性加载后的 ANGLE init 动作、`ro.surface_flinger.default_composition_pixel_format=2`（RGBX）及此前已验证的启动修复。保留 thyme 内核和硬件栈；未复制 K40 vendor、Vulkan、Gralloc、HWC、DTBO 或固件。

K40 产品配置另有 `ro.hwui.use_vulkan=true`；C21 未改 product，thyme vendor build.prop 对该 ro 属性为空，C21 用 `debug.hwui.renderer=skiavk` 直接覆盖 HWUI 渲染选择。

## C20 图形现场与 K40 对照结论

- C20 pmsg 证明 SurfaceFlinger 使用 `SkiaGLRenderEngine`，在 `chooseEglConfig()` 对 `format=2` 反复失败 47 次。
- 同一 fatal 输出的 EGL vendor/version 是 `Android` / `1.4 Android META-EGL`。这只确认 EGL 前端身份，不能证明底层实际是 ANGLE 还是 Adreno；现有记录也不能区分配置数量为零与属性过滤后没有匹配。
- C20 linker 诊断没有产生有效加载路径记录；ADB 未上线，不能取得 SurfaceFlinger `/proc/<pid>/maps`。
- 缓存的 K40 包为 OS4.0.0.8 Android 17 移植，关键 system EGL/SurfaceFlinger/RenderEngine 文件与 Xiaomi 15 供体和 C20 字节一致。K40 的直接相关差异是 product 中显式选择 `skiavkthreaded` 和 Vulkan HWUI，而非替换 system EGL Loader。
- C20 另有 Xiaomi `graphicsengine` 在 `vkEnumeratePhysicalDevices+4` 空指针崩溃。这是 Vulkan 风险，但尚无证据证明它与 SurfaceFlinger EGLConfig 错误有因果；thyme 与 K40 Vulkan vendor 二进制不同。

## C21 构建与首次启动结果

- 构建目录：`work/stage_k_thyme_os4_candidate_21_k40_vk_renderengine_run1/images/`。
- 报告：`work/reports/20260927_CANDIDATE21_K40_VULKAN_RENDERENGINE/REPORT.md`。
- 清单：`.../images/BUILD_MANIFEST.json`，记录六项镜像大小和 SHA-256。
- 最终 system EROFS fsck、属性回读、AVB system descriptor 更新、product/system_ext descriptor 保持及 LP 布局检查通过。
- `super.img`：7,684,274,964 bytes，SHA-256 `C8BF3F895639C648D947E201E9E12EFCB7CCA33B63B0EAA807AE4672939EC2DF`；Fastboot 10/10 sparse 块均 `OKAY`。
- `vbmeta_system.img`：131,072 bytes，SHA-256 `E3A2807CE59CFAF93BEF7E08EE45A1D055DE1264FFEA8F6E8EED06893892AC74`；写入成功。
- C21 只用于“SurfaceFlinger 是否能绕开失败的 EGL/SkiaGL 路径并初始化 SkiaVk”实验。其实机 Vulkan 初始化结果见下节。

## C21 首次启动实机结果

- Standalone 原始取证目录：`work/reports/20260927_CANDIDATE21_K40_VULKAN_RENDERENGINE/standalone/run_20260927_170631/`。THYME_DIAG 的 8 个文件（含 console、pmsg、oops、Standalone dmesg、状态及系统生成文件）均已复制；大小及 SHA-256 对照零错误。Standalone dmesg 属于诊断系统；`oops.raw` 为 2026-06-17 历史记录，不归属 C21。本轮 Android 用户空间证据来自 pmsg。
- C21 pmsg 证明 First/Second Stage、APEX Bootstrap、`/data`、vold/密钥初始化推进；没有 `bootanimation` 或桌面证据。C21 实际进入 SkiaVk：SurfaceFlinger 反复 fatal，abort message 为 `Could not initialize Vulkan RenderEngine!`，栈位于 `SkiaVkRenderEngine::createContexts()+944`。pmsg 中未再出现 C20 的 `no suitable EGLConfig found`。
- 首次 SurfaceFlinger fatal 前约 0.08 秒，`graphicsengine` 在 `vkEnumeratePhysicalDevices+4` 发生 SIGSEGV，fault address 为 null，调用方为 `MiVulkanPipelineCacheBuilder`。时序相邻但进程独立，因果关系尚未证明。C21 约有 80 次 SurfaceFlinger Vulkan 初始化 fatal；`netd` 等崩溃是并发问题，尚无证据为本次首要阻塞。
- C21 console 延伸约 417 秒，无 kernel panic；pmsg 约记录到 6 分 50 秒。终止显示阶段原因未由这次日志完全确定。观察结果是米标常亮，未见 HyperOS 动画、设置向导或桌面。
- 修正资产版本认定：C21 构建实际复用 `/path/to/thyme-os4-build/thyme_xiaomi15_os4_first_boot_candidate_1/provider_images/vendor.img`。从该实际输入只读提取的 Vulkan ICD 为 2,232,960 bytes（SHA-256 `7d78c17c97c2e49d2b0cbc9046f04fb8d77e928445ce9f58e9c12b74888186ae`）；它与 `work/port_v0_candidate/vendor` 展开树中的 1,900,664-byte 文件不同。后续 ABI 判断以 C21 实际 vendor 镜像为准。
- C21 实际 `libgsl.so` 没有 K40 Android 17 Vulkan UMD 所需的若干 GSL API（如 `gsl_device_getfeatures`、`gsl_memory_alloc_pure_64`、`gsl_timeline_create` 等）。K40 的 `libgsl.so` 也有额外 `libdmabufheap.so` 依赖，而 C21 system 中存在该库。直接覆盖同名 `libgsl.so`、`libllvm-glnext.so`、`libadreno_utils.so` 会丢失旧 thyme EGL/GLES 驱动使用的导出符号，因此 C22 方案采用带独立 SONAME 的 K40 Vulkan 配套副本，仅让 Vulkan ICD 指向它们，保留现有 EGL/GLES 支持库。
## C22 K40 Vulkan UMD 配套实验

- 报告：`work/reports/20260927_CANDIDATE22_K40_VULKAN_UMD/REPORT.md`；构建清单及镜像：`work/stage_l_thyme_os4_candidate_22_k40_vk_umd_run5/images/`。
- 基于 C21 实际故障，C22 以缓存的 K40 OS4.0.0.8 Android 17 Vulkan UMD 替换 vendor 的 `vulkan.adreno.so`，并增加独立 SONAME 的 `libgsl_k40.so`、`libadreno_utils_k40.so`、`libllvm-glnext_k40.so` 与 K40 `libllvm-qgl.so`。K40 ICD 及其 UMD 依赖已改为引用隔离 SONAME；原 thyme `libgsl.so`、`libadreno_utils.so`、`libllvm-glnext.so`、EGL/GLES、Gralloc/HWC 均保留。
- 只修改工作副本中的 C1 `vendor.img`；ext4 文件 owner 为 root:root、mode 0644，SELinux xattr 为 `same_process_hal_file`。只更新 root `vbmeta.img` 的 vendor hashtree descriptor；descriptor digest 从 C21 `b41125…f6591` 更新为 C22 `743d0b…c857`，其余 root descriptors、header flags/rollback index 及 `vbmeta_system.img` 保持不变。
- C17 构建中间镜像已不存在；为保留 C21 的实际 `system_ext_a`，从 C21 已构建的 raw super 中提取该逻辑分区后原样用于 C22。LP geometry 和 A 槽分区 extent 与 C21 一致。
- 主机验证：vendor `e2fsck -f -n` 通过；`avbtool verify_image` 验证 vendor footer 与 SHA-256 hashtree 成功；根 vbmeta descriptor 断言和 lpdump 通过；四项继承镜像（boot、vendor_boot、dtbo、vbmeta_system）与 C21 manifest 哈希一致；刷写脚本 PowerShell parser 检查通过。
- C22 `super.img`：7,701,892,056 bytes，SHA-256 `6145D602D17321EFF1AD55A7AC10B9314AF9E7C23C0BD60D681115CD54B1330D`；`vbmeta.img`（写入 `vbmeta_a`）：131,072 bytes，SHA-256 `66A53C2EC38247193CC86B7F5DE887556864413D1142C3C1994645DE1E3BAB10`。
- 2026-09-27 已顺序刷入 `super` 和 `vbmeta_a`；super 的 10/10 sparse 块及 vbmeta 写入均返回 `OKAY`。之后 C22 完成一次实机首启实验；未清 userdata/metadata、未回锁或写其他分区。
- 观察记录：`work/reports/20260927_CANDIDATE22_K40_VULKAN_UMD/observations/run_20260927_195701/`；Standalone 全量副本：`work/reports/20260927_CANDIDATE22_K40_VULKAN_UMD/standalone/run_20260927_200710/`。诊断卷全部 8 个可访问文件的大小和 SHA-256 核验通过。
- 新阻塞：C22 pmsg 有 89 次 SurfaceFlinger `output buffer not gpu writeable` fatal，栈落在 Skia `Cache::primeShaderCache` / `SkiaRenderEngine::primeCache`；BootAnimation 随 SurfaceFlinger 反复退出。First/Second Stage、APEX 与 `/data` 初始化推进。日志未出现 C21 Vulkan RenderEngine fatal、EGLConfig 错误或 graphicsengine Vulkan SIGSEGV 文本。console 延伸至约 462.109 秒，无 kernel panic 证据。
- 结论边界：C22 已越过 C21 RenderEngine 创建 fatal 并运行到 shader-cache 预热；pmsg 未给出实际 Vulkan ICD/后端身份，不能宣称 K40 UMD 已成功初始化。buffer 最终缺少 `HW_RENDER` usage 的底层原因仍待验证。
- C23 方案：只在 system `build.prop` 设 `service.sf.prime_shader_cache=0`，跳过已由实机调用栈确认的可选预热路径；保留 C22 UMD、C21 RenderEngine 路由及其他已验证修复。此为诊断性绕过，不代表底层 buffer usage 问题已解决。
- C22 开发期间的失败批次 WSL 目录 `c22_k40_vulkan_umd_20260927_run1` 至 `run4` 仍保留，合计约 21.5 GiB（目录表观大小），均非可刷镜像且无设备写入；未纳入此前核准的旧 Candidate 清理白名单。最新 D 盘可用空间约 138.44 GiB，未触发低于 50 GiB 的清理阈值。

## C23 SurfaceFlinger shader-cache prime 绕过实验

- C22 pmsg 实机记录 89 次 `output buffer not gpu writeable` SurfaceFlinger fatal；栈位于 Skia `Cache::primeShaderCache` / `SkiaRenderEngine::primeCache`。C22 原始 Standalone 副本 8/8 文件大小与 SHA-256 校验通过。日志没有给出实际 Vulkan ICD/后端身份；buffer usage 的底层原因未知。
- C23 唯一系统改动：system `build.prop` 增加 `service.sf.prime_shader_cache=0`，跳过可选 shader cache 预热。它是诊断性绕过，不证明 gralloc/GraphicBuffer usage 问题已解决。保留 C22 K40 Vulkan UMD 与全部既有修复。
- 报告：`work/reports/20260927_CANDIDATE23_SF_PRIME_SKIP/REPORT.md`；构建：`work/stage_m_thyme_os4_candidate_23_sf_prime_skip_run4/images/`。EROFS、属性回读、system AVB、vbmeta_system 描述符保留、LP 布局检查通过。
- 2026-09-27 已仅刷 `super` 与 `vbmeta_system_a`；super 10/10 sparse 块、vbmeta_system 写入成功。刷后只读确认 thyme/A/unlocked，A 槽可启动，retry-count=2。之后已完成一次受控启动尝试并进入 Recovery；完整结果见下文。
- 六镜像 SHA-256 清单位于 `.../images/BUILD_MANIFEST.json`。本轮未擦 userdata/metadata、未改其他分区、未回锁。

### C23 首次启动与 Recovery 取证

- 观察器目录：`work/reports/20260927_CANDIDATE23_SF_PRIME_SKIP/observations/run_20260927_211900/`；Standalone 全量导出：`work/reports/20260927_CANDIDATE23_SF_PRIME_SKIP/standalone/run_20260927_212336/`。
- 可见的 console-ramoops 只有一个内核实例：First Stage 于 1.905 秒开始并明确记录 `First stage mount skipped (recovery mode)`；Second Stage 于 2.002 秒开始；Recovery 于 3.976 秒开始。Recovery 记录 `Boot command: bootonce-bootloader`，随后于 4.159 秒清除 BCB。该命令不是清数据命令；记录只描述 Recovery 已经启动后的状态，不能单独证明它是进入 Recovery 的原因。
- console 中未见 `prompt_and_wipe_data`、`--wipe_data`、SurfaceFlinger、`prime_shader_cache` 或 C23 图形初始化记录。Recovery 的 `system_ext_a/product_a` 逻辑设备不可用发生在 First Stage 跳过挂载之后；Recovery 的 AVB `VerificationDisabled` 日志也不能当作 C23 普通启动失败原因。
- `THYME_DIAG` 上 7 个可访问文件、17,117,150 bytes 已完整复制；源/副本 SHA-256 校验零错误。没有 pmsg 文件；`dmesg_diag_boot.txt` 属于 Standalone；`oops.raw` 与 C22 完全相同，是历史残留，不归属 C23。
- 启动命令后的 ADB 仅为 `unauthorized`，logcat 文件为空。因此没有证据证明 HyperOS C23 普通用户空间进入了图形阶段，也不能排除首次普通启动的日志已被 Recovery 启动覆盖。C23 是否触发 Recovery、触发前是否短暂运行普通系统，仍未确定。


### C23-retest（2026-09-28）

- 报告：work/reports/20260927_CANDIDATE23_RECOVERY_RETEST/C23_RETEST_20260928.md。观察记录：observations/run_20260928_150900/；Standalone 全量导出：standalone/run_20260928_151306/。
- First Stage 约 2.048s、Second Stage 约 3.212s；SELinux enforcing、APEX、vold 与 F2FS /data/fscrypt 初始化推进。console 单实例延伸约 126s；pmsg 约两分钟。
- pmsg 有 BootAnimationShownTiming start time: 42129ms，但现场只确认看到静态小米 Logo；无 Setup Wizard、桌面或直接 sys.boot_completed=1 证据。pmsg 未出现 C22 output buffer not gpu writeable、SurfaceFlinger EGLConfig 或 Vulkan RenderEngine fatal；service.sf.prime_shader_cache=0 运行时值仍未确认。
- 重复 netd SIGABRT 与指纹服务 SIGSEGV 被记录，但尚无证据表明其阻止启动界面。oops.raw 与 C13–C22 历史摘要相同，属于旧持久内容；Standalone dmesg 是诊断系统自身日志。
- 8 个 THYME_DIAG 文件、17,805,353 bytes 全部复制，0 错误，源/副本大小和 SHA-256 一致。本轮本地原件保留；经用户授权的 C23 retest 原始诊断和主机观察增量已公开同步，逐文件来源、大小和 SHA-256 见公开 evidence/RAW_EVIDENCE_MANIFEST.csv。

### C23 完整启动窗口复验（2026-09-28）

- 报告：`work/reports/20260928_C23_LONG_BOOT_RETEST/REPORT.md`。观察目录：`observations/run_20260928_154458/`；Standalone 全量副本：`standalone/run_20260928_160036/`。
- 观察器先 ARMED，再执行唯一一次 `fastboot reboot`。用户确认全程只有静态小米 Logo；主机 Fastboot 在命令后约 11 分 52.8 秒重新出现，用户说明是手动进入。ADB 始终未上线。
- pmsg 跨约 697.883 秒，记录 F2FS `/data` 挂载、fscrypt 初始化与一次 `BootAnimationShownTiming start time: 40943ms`。现场没有 HyperOS 动画/设置向导/桌面；未见 `sys.boot_completed=1`、`service.bootanim.exit` 或 SystemUI/SetupWizard/Launcher 直接记录。
- 本轮未出现 EGLConfig、Vulkan RenderEngine、C22 output-buffer fatal 文本；shader-cache 属性运行时值未采样，不能确认它是本轮变化原因。真实记录到 netd 138 次 SIGABRT、指纹 HAL 137 次 SIGSEGV、audio.service 74 次 SIGSEGV，以及 23 次 `UltraFrameworkComponentFactoryImpl` ClassNotFoundException；它们与界面停滞的因果未确认。
- Standalone 诊断卷 8 文件共 20,433,856 bytes，零复制错误，源/副本 SHA-256 一致；console 从 uptime 120.114755s 至 702.552956s，未见 panic；oops.raw 是历史残留，Standalone dmesg 属于诊断系统。
- 启动后 A retry 6→5；A/B 均 `unbootable=no / successful=no`，B retry=7。最终只读状态为 thyme/A、解锁、Bootloader Fastboot。未刷写、清除数据、切槽、写 BCB、恢复 PixelOS 或回锁。
- 结论（截至 C23 复验报告时）：完整窗口未取得第二屏，也没有足够证据锁定根因。后续调查与 C24 状态见下节。

### C23 Framework/UI 与物理显示断点调查、C24 诊断包（2026-09-28）

- 调查报告：`work/reports/20260928_C23_FRAMEWORK_DISPLAY_C24/C23_FRAMEWORK_DISPLAY_C24_DIAGNOSTIC_20260928.md`。
- C23 pmsg 1,401,451 bytes、11,775 条时间戳记录，跨度约 697.883 秒。能确认 `/data` F2FS/fscrypt 初始化、keystore2 等待 `sys.boot_completed=1` 至约 680 秒、SurfaceFlinger 域活动，以及 BootAnimation PID 2030 后续输出 placeholder 和 `BootAnimationShownTiming start time: 40943ms`。pmsg 没有 Zygote/system_server 阶段、ActivityManager/WMS、SystemUI/SetupWizard/Launcher、bootanim exit、WMS enable-screen 或 HWC present 结果。用户报告全窗口静态米标；ADB 未上线。故真实断点仍不能区分 Framework 未 ready 与显示链未呈现。
- netd SIGABRT、指纹 HAL/audio.service SIGSEGV 及 `UltraFrameworkComponentFactoryImpl` CNFE 确实反复出现，但没有直接证据证明它们阻塞 system_server、WMS 或屏幕更新。K40 OS4.0.0.8 Android 17 对照中，C23/K40/供体的核心 framework JAR 相同；差异集中于 K40 服务与目标专属 UI/overlay，未发现通用 boot-ready/HWC 修复。`bootanim.rc` 三方一致；K40 的 32 帧 BootAnimation 与 C23 实际 5 帧动画是可供后续评估的资源差异，不证明物理显示/框架故障原因，也未复制到 C24。
- 因证据不足以选择修复，准备诊断型 C24：仅在 system 导入一个 `post-fs-data` 诊断服务，15 分钟内每 10 秒采样完成属性/关键 PID、约每分钟有界采样 WindowManager、ActivityManager、SurfaceFlinger、display/HOME 信息，输出至 logd/pmsg。没有更改 SELinux、GPU 路由、HWC/vendor、内核、fstab、加密或数据分区。该方式是否能运行并保留日志待 C24 实机验证。
- C24 构建目录：`work/stage_n_thyme_os4_candidate_24_framework_display_diag_run2/`；脚本：`tools/build_candidate24_framework_display_diag.py`、`tools/flash_candidate24_framework_display_diag.ps1`、`tools/candidate24_bootdiag/`。run1 因 EROFS AVB descriptor data extent 增长 4096 bytes 与复用断言冲突而停止；无设备访问。run2 按实际 hashtree extent 更新 descriptor 后构建。
- 主机验证：新增 EROFS fsck/readback、system AVB hashtree、vbmeta_system 描述符、LP extent、脚本语法和 `system_file` xattr 检查通过。C24 `super.img` 7,701,896,152 bytes，SHA-256 `2B84BD93ADFA85FC851A17937B7F96AB4176F01F3E3D00FFC2DB78766BA2CDD8`；`vbmeta_system.img` 131,072 bytes，SHA-256 `1A67C4A2E22DA746E184B146D7DD65059D00FB501EE3642DA1BD2AEFCE706D08`。
- 本轮顺序刷写仅 `super` 和 `vbmeta_system_a`；super 的 10/10 sparse transfer/write 与 vbmeta_system send/write 返回 `OKAY`。没有刷 boot/vendor_boot/dtbo/vbmeta_a。
- C24 已在观察器运行期间启动一次，2026-09-28 19:49:44.233 HKT `fastboot reboot` 返回 OKAY。用户约 16 分 43 秒持续看到第一屏小米 Logo + `powered by Android`，未见 HyperOS 第二屏；ADB 未上线，随后用户手动进入 Fastboot。没有自动启动 Recovery 的证据。
- C24 Standalone 全量导出见 `work/reports/20260928_C24_FRAMEWORK_DISPLAY_DIAG/standalone/run_20260928_200722/`；8 个文件、20,977,071 bytes，校验 0 错误。C24 诊断服务没有可验证标记；本轮没有读取到 Framework/HWC 状态。PixelOS 未恢复。

## 已有实机验证基线

- C13：First/Second Stage、APEX、vold 与 `/data` 初始化推进成功；后续 BPF 内核版本门槛由 C14 绕过。
- C14：BPF 绕过实机有效，启动推进到图形阶段。
- C16/C17：graphics allocator 的 `ion_device` read/open AVC 定点修复；C17 复验未见该 AVC。
- C19/C20：Second Stage/APEX/vold/`/data` 初始化继续成功；SurfaceFlinger EGLConfig 失败持续，未进入 HyperOS 动画、设置向导或桌面。
- C21：Second Stage、APEX、vold 和 `/data` 推进；SurfaceFlinger 的 SkiaVk RenderEngine 创建 fatal，未出现启动动画。
- C22：越过 C21 的 RenderEngine 创建 fatal 并进入 Skia shader-cache 预热；output buffer GPU write usage 检查反复 fatal，未出现 HyperOS 启动画面、设置向导或桌面。

## 磁盘空间与清理状态
- 2026-09-29 01:01 HKT 主机余量：C=76.95 GiB、D=119.53 GiB、E=176.11 GiB。C 低于 80 GiB 重型工作门槛；本轮未构建。
- [LOCAL_PROJECT_ROOT] 分层盘点得到约 311,277,118,023 bytes（289.90 GiB）逻辑文件量，其中 work 247,804,377,446 bytes（230.79 GiB）。计数跳过 reparse point，但含硬链接重复路径；不能直接视作可回收的物理空间。
- C 盘已知项目临时目录 [LOCAL_USER_PATH] 目前为空；未发现可观的 C 盘项目清理项。
- Ubuntu /path/to/thyme-os4-build 当前 93,921,775,616 bytes（约 87.47 GiB）；D 盘 Ubuntu VHDX 逻辑长度 176,781,524,992 bytes（164.64 GiB）。本轮删除一份已逐字节散列证实的重复 K40 super.raw（SHA-256 7fa58150d67eef64f924c264a7b69df6604772c85417399f9141042260a663df，9,126,805,504 bytes），保留另一份及 K40 提取内容。Ubuntu df 已用量相应下降；fstrim / 报告 905.1 GiB trimmed，但 Windows D 可用空间未增加，VHDX 长度未变。
- E 盘 work/stage_c_thyme_os4_candidate_13_1_data_guard 仍有 44.42 GiB；其递归删除在此前被执行环境拒绝，本轮未重试、未绕过。diagnostic_candidates 中 M26（K40 提取件）、M29（已失败并曾上机的候选）与 Pixel A17 native control 输出保留；M29 的 11 个生成镜像约 8.45 GB 曾尝试清理，但执行环境拒绝该删除，本轮未改用其他工具绕过。Pixel native super 是救援资产，M26 提取件被后续技术报告引用。C20→C25 阶段目录与当前构建脚本链保持不动。
- C20→C26 构建链中的阶段目录由现有 Candidate 构建脚本逐版引用，当前先保留；原始供体、PixelOS 救援资产、取证、日志、报告和 K40 图形提取缓存保留。
- 本轮 Docker 未访问或修改；未停止 WSL、未压缩 VHDX。此前 VHDX 压缩因文件占用失败，未重试。
- 后续清理仅使用明确项目路径；任何 WSL 操作限定 Ubuntu，不触及 Docker。C 低于 80 GiB 时暂停重型构建。
- C26 构建前/刷写前实测 C/D/E 可用空间为 76.76/119.52/176.11 GiB；本轮沿用已定向到 E 与 Ubuntu WSL 的构建流程，没有清理任何目录，Docker 相关资产未访问。

## 下一步

1. 设备当前保持 Bootloader Fastboot；等待用户在手机旁确认可观察后再启动 C26。
2. 启动前运行只读观察器并确认 ARMED，再通过 `tools/start_candidate26_observed_boot.ps1` 执行唯一一次 reboot。
3. 若 ADB 不上线，待用户手动返回 Fastboot 后使用既有 Standalone 流程完整备份 THYME_DIAG 与 `/metadata/thyme_os4_diag`，先核验副本再分析 C26 logcat 和 Zygote 首次退出原因。
4. 最近 Windows C/D/E 实测余量为 75.91/119.52/168.62 GiB。C 低于 80 GiB 重型构建门槛；本轮 C26 已构建，未清理磁盘。Docker 与其 WSL 资产未访问、未修改。
## 关键工具与项目路径

- C21 构建：`tools/build_candidate21_k40_vk_renderengine.py`
- C21 刷写：`tools/flash_candidate21_k40_vk_renderengine.ps1`（仅 `super`、`vbmeta_system_a`，不自动启动）
- C21 启动门控：`tools/start_candidate21_observed_boot.ps1`
- C22 构建：`tools/build_candidate22_k40_vulkan_umd.py`（仅主机构建）
- C22 刷写：`tools/flash_candidate22_k40_vulkan_umd.ps1`（仅 `super`、`vbmeta_a`，不自动启动）
- C22 启动门控：`tools/start_candidate22_observed_boot.ps1`（要求新鲜 ARMED 记录和用户在场确认）
- C23 构建：`tools/build_candidate23_sf_prime_skip.py`（基于 C22，只设置 `service.sf.prime_shader_cache=0`）
- C23 刷写：`tools/flash_candidate23_sf_prime_skip.ps1`（仅 `super`、`vbmeta_system_a`，不自动启动）
- C23 启动门控：`tools/start_candidate23_observed_boot.ps1`（要求新鲜 ARMED 记录和用户现场确认）
- C24 诊断构建：`tools/build_candidate24_framework_display_diag.py`；诊断服务：`tools/candidate24_bootdiag/`；刷写脚本：`tools/flash_candidate24_framework_display_diag.ps1`（仅 `super`、`vbmeta_system_a`，不自动启动）
- C25 构建与刷写：tools/build_candidate25_first_screen_diag.py、tools/flash_candidate25_first_screen_diag.ps1（仅 super、vbmeta_system_a，不自动启动）；诊断 helper：tools/candidate25_bootdiag/；Standalone 只读 metadata 导出：tools/build_standalone_diag.py --export-c25-metadata
- C25 启动门控：tools/start_candidate25_observed_boot.ps1；观察器参数 --candidate C25-first-screen-diag，输出目录 work/reports/20260928_C25_FIRST_SCREEN_DIAG/observations（需新鲜 ARMED 记录及用户现场确认）
- C26 构建/刷写：tools/build_candidate26_zygote_diag.py、tools/flash_candidate26_zygote_diag.ps1（仅 `super`、`vbmeta_system_a`，刷后不启动）；启动门控：tools/start_candidate26_observed_boot.ps1
- 只读观察器：`tools/observe_candidate13_readonly.py`
- 项目环境：Windows 11 + WSL Ubuntu；C21 使用既有 WSL 构建树及已缓存 EROFS/LP/AVB 工具。
- 公开项目：https://github.com/ROCK-VK/thyme-hyperos4-port
- C26 诊断构建/刷写资料已于 2026-09-29 同步至 Public 仓库 main；该增量 Commit：https://github.com/ROCK-VK/thyme-hyperos4-port/commit/949ee593ab5504e5e291bd3922394590262e4ff4。远端 main、README、C26 报告与 helper 源码已匿名访问验证；未上传 ROM、分区镜像或编译后的 helper 二进制。
