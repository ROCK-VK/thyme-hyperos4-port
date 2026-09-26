# THYME-OS4 Candidate 14 启动故障与 Candidate 15 EGL 诊断方案

日期：2026-09-26

## 结论

C14 已越过 C13 中由 `bpfloader-failed` 触发的暖重启点。本轮保存到的首要显示故障是 SurfaceFlinger 因没有可用 EGLConfig 而反复中止。现有证据不证明 C14 完成 Android 开机，也不证明系统未曾继续推进到更多服务。

下一次主机侧准备采用 C15：保留 C14 已实机验证有效的 BPF 启动绕过，仅增加 Android 17 已支持的 `persist.graphics.egl=angle`，验证 Android 系统 ANGLE EGL 路径能否让 SurfaceFlinger 创建 EGLConfig。C14 的 Vulkan 辅助进程崩溃使该试验存在失败风险，但不足以排除 ANGLE，因此保留为高信息量的单项诊断。没有刷写、启动、擦除或恢复设备。

## C14 证据与证据边界

主机观察器在 UTC 07:24:57.151 确认为 Fastboot 在线、ADB 离线并进入 ARMED；一次已授权的 `fastboot reboot` 于 07:25:13.699 开始并成功返回。Fastboot 于 07:25:14.145 离线，07:27:19.187 再次枚举。用户在 07:28:42.350 报告小米 Logo 常亮后手动进入 Fastboot。记录不能精确标定用户按键动作发生时刻；没有 ADB 上线。

本轮 Standalone 只读取证目录：

`work/reports/20260926_CANDIDATE14_FIRST_BOOT/standalone/run_20260926_153413/`

本轮 Standalone 已导出并校验 THYME_DIAG 卷中全部 6 个可访问文件。完整 misc 分区不在本轮读取范围内。实际存在的 C14 Android pstore 文件为：

| 文件 | 字节数 | SHA-256 |
|---|---:|---|
| `pstore/console-ramoops-0` | 574,020 | `11F5A76044EA676C4E98052B4AF0839AD150D1F45E095A31FB46833F17BE0D13` |
| `pstore/pmsg-ramoops-0` | 336,612 | `06D110FB4AE2AA14CBA5657F3FEF3F9F9717B09709E64378D7A412D4427E6AF7` |

原始 pmsg、console、oops 与 Standalone dmesg 留在本地；不会上传公开仓库。`oops.raw` 为 16 MiB 混合/历史内容，不能归属于 C14。`dmesg_diag_boot.txt` 和 `diag_status.log` 属于 Standalone 自身。

### 启动链判断

- console-ramoops 中只有一个可见的 Linux 版本、kernel command line、first-stage 和 second-stage 实例。Android init first stage 在 1.788557 秒启动，second stage 在 3.044160 秒启动；console 记录延伸到约 115.817 秒。
- pmsg 的设备内部时间戳从 23:26:13.211 延续至 23:28:03.891。该设备时钟为 1970 年基准，不与主机 UTC 混用。
- 保存的 C14 console/pmsg 中没有 `NetBpfLoad` 或 `bpfloader-failed`；与 C13 已证实重启点相比，C14 已真实越过该失败门控。此结论只表示本次记录没有再出现该重启，不代表 BPF 已适配或网络可用。
- 日志确认 vold 的 `/data` F2FS 挂载及 fscrypt key 操作继续发生。ADB 始终离线，因此没有属性、完整 logcat 或屏幕状态读取；没有证据确认 `sys.boot_completed=1`、启动动画、设置向导或桌面。

### 明确故障与次级错误

1. **SurfaceFlinger：首要显示阻塞证据。** pmsg 中统计到 20 次 SurfaceFlinger abort，重复的 abort message 为 `no suitable EGLConfig found, giving up ... Client API: OpenGL_ES`。第一次记录约为 23:26:30.734。它直接说明当前 EGL 初始化没有给 SurfaceFlinger 提供所需配置，是小米 Logo 后未观察到正常 Android 画面的最强可行动证据。
2. **graphicsengine：Vulkan 相关次级崩溃。** 约 23:26:30.193，MIUI `MiVulkanPipelineCacheBuilder` 所在线程因空指针 SIGSEGV；堆栈进入 `libvulkan.so` 的 `vkEnumeratePhysicalDevices`。这使 ANGLE Vulkan 后端成功的把握降低，但不能单凭该 MIUI 辅助进程崩溃证明所有 Vulkan 调用都会失败。
3. **netd：重复崩溃，根因未确定。** pmsg 中有 14 个 netd fatal/tombstone 记录，调用栈落在 `libnetd_updatable_init.cfi+576`。未取得明确 Abort message，不能确认它是缺失 BPF map、供体库不兼容或其他原因。C14 绕过 BPF loader 后启动 netd 与时间相关，但因果关系没有被证明。现有记录没有证据表明 netd 崩溃导致 init 重启或阻止图形界面，因此本轮不混入未经证实的 netd 改动。

## C15 选择与 K40 参考

C14 的系统 EGL loader 是 Android 17 构建。其实际二进制包含 `persist.graphics.egl` 分派属性；Android 17 AOSP `Loader.cpp` 也实现了该属性并将 `angle` 选项加载到系统 ANGLE 库路径：[AOSP Android 17 Loader.cpp](https://android.googlesource.com/platform/frameworks/native/%2B/android-17.0.0_r1/opengl/libs/EGL/Loader.cpp)。本项目 C14 property contexts 已将该属性映射至可写 graphics 配置属性类型。因而设置 `persist.graphics.egl=angle` 是针对“系统 EGL loader 选择/加载 native Adreno EGL 路径后找不到可用 EGLConfig”这一实际错误的直接、可回退诊断。

K40 成功包使用 Adreno 路径，但其 Qualcomm Adreno UMD 与 thyme C14 不同；现有差异记录显示 K40 `libGLESv2_adreno.so` 为 `V@0805.0`，C14 为 `V@0530.57`。K40 的 `eglSubDriverAndroid.so` 也依赖其 QTI gralloc/mapper/display 组件，不能单独或整组盲拷到 thyme。K40 的 `debug.egl.hw=0` 不被当前 Android 17 系统 EGL loader 用作驱动选择条件；C14 system build.prop 已有 `persist.sys.force_sw_gles=1`，但仍触发当前 SurfaceFlinger EGLConfig abort。因此本次不重复加旧属性，也不移植不匹配的 K40 显示栈。

## C15 主机侧修改与构建

C15 以已上机的 C14 run5 为构建基线：

- 唯一新增系统属性：`system/build.prop` 中的 `persist.graphics.egl=angle`。
- 继承 C14 BPF loader 绕过；不重新打开 C13 的 bpfloader 故障路径。
- 保留 C13 SELinux / ION 规则、fstab、APEX、存储加密配置和 thyme 硬件底层。
- 重建 system EROFS、对应 `vbmeta_system` hashtree descriptor 和 `super.img`；不重建 boot、vendor_boot、dtbo 或顶层 vbmeta。
- 独立工作目录：`work/stage_e_thyme_os4_candidate_15_angle_egl_run1/`。C14 成品未覆盖。

最终镜像仅准备写入以下两个目标：

| 分区 | 镜像大小 | SHA-256 |
|---|---:|---|
| `vbmeta_system_a` | 131,072 | `634EB12F681ECFFFF5E07CEF633377F5C16903E32901AFE7B6EF56FE4D5A4190` |
| `super` | 7,684,274,964 | `4CD34B53A7E47E25522C191AC748B8EE91348091C9B0F31FF59EC677CF8C9B56` |

匹配关系：C15 `vbmeta_system` 包含 product/system/system_ext 三项 hashtree descriptor；system descriptor 的 image size 为 958,156,800、root digest 为 `86f3a4bcebf5c0f49b419f1fb642b2899d47961e5543c4dced3c9c63b4ab5f51`，对应本轮 C15 system；system_ext 与 product descriptor 沿用 C14。生成后的 LP 表仍包含 `system_a`、`system_ext_a`、`product_a`、`vendor_a` 等所需逻辑分区。

| 继承镜像 | 字节数 | SHA-256 |
|---|---:|---|
| `boot.img` | 201,326,592 | `E5A016056D5C93C7A886980A7C062617EC44DC06A48417D7DD0F4476708A6368` |
| `vendor_boot.img` | 100,663,296 | `02333B82BA936F1BAAB1ECAB744632C70F8FC16688A206C7041EF319F112A137` |
| `dtbo.img` | 33,554,432 | `50E1AC0EDCBD333778217AA6FE8D972F6FF85ADD0DAE8A015A6642C2172DD886` |
| `vbmeta.img` | 131,072 | `013335BCA9B312E0BEFF737D30903A9B0A1EF829BA19A7BD5802BF83C04F40E9` |

基本检查通过：system EROFS `fsck.erofs` 成功；最终 build.prop 回读到唯一 `persist.graphics.egl=angle`；LP dump 含必需分区；AVB descriptor 存在且 system digest 匹配 C15 system；C15 六项镜像 manifest 已生成；PowerShell 刷写脚本解析通过，默认 Dry-Run 对两个实际写入镜像的大小和 SHA-256 通过。

**未验证事项：** C15 尚未真机刷写或启动；ANGLE 是否能使用当前 Vulkan 底层、SurfaceFlinger 是否稳定、设置向导/桌面是否出现，均待真机验证。

## 下一次实验

候选使用 C15，写入 `vbmeta_system_a` 和 `super`；保留当前 C14 boot、vendor_boot、dtbo、vbmeta，不清除 userdata/metadata。现有专用脚本为 `tools/flash_candidate15_angle_egl.ps1`，默认 Dry-Run，仅显式 `-Execute` 时执行写入；完成后保持 Fastboot，不自动启动。首次启动前先 ARMED observer，用户确认可观察后再单独启动。失败后保留 Standalone 取证，区分 C15 EGL 结果、Vulkan/ANGLE 后端错误、BPF/netd 次级状态；不得把 Standalone 自身日志当作 Android 启动日志。

本轮已完成主机侧准备，尚未获得 C15 刷写或首次启动授权。当前设备在本轮 Standalone 导出时枚举为 `THYME_DIAG` USB 存储卷；此后未再次查询设备状态。PixelOS A0′ 未恢复或验证在线。
