# C23 BootAnimation 后 Framework/UI 与显示断点调查；C24 诊断构建

日期：2026-09-28（香港时间）

## 结论

C23 pmsg 覆盖约 697.883 秒。它记录 `/data`/fscrypt 初始化、keystore2 持续等待 `sys.boot_completed=1`，以及 BootAnimation PID 的后续代码和 `BootAnimationShownTiming start time: 40943ms`。用户在约 11 分 52 秒观察窗口中始终看到静态小米 Logo，ADB 未上线。

现有证据无法确认 system_server 最后运行到哪个阶段，也没有 ActivityManager/WindowManager、WMS enable-screen、SystemUI、SetupWizard、Launcher、`service.bootanim.exit`、`sys.boot_completed=1`、HWC validate/present 或物理显示更新的直接记录。BootAnimation 的 shown-timing 不是屏幕显示动画的证据。因此，Framework/UI 未完成与 Android 已运行但显示链没有更新面板，当前仍不能区分；没有证据表明 Android 已成功向物理 display present 一帧。

`netd` SIGABRT、指纹 HAL/audio.service SIGSEGV 与 23 次 `UltraFrameworkComponentFactoryImpl` ClassNotFoundException 有真实记录，但没有证据将它们连接到 system_server ready、WMS enable-screen 或显示 present 阻塞。该类也未在所扫描的 K40 OS4 成功包 system/system_ext JAR 中找到；K40 成功系统没有它会降低其为必要组件的可能性，但没有完整证明 thyme 的 fallback 行为。

## K40 OS4 Android 17 定点对照

比较了 Redmi K40 OS4.0.0.8 Android 17 成功包、对应 Xiaomi 15 OS4.0.0.8 供体和 C23 的必要 Framework/UI/boot-animation 文件；排除了 OS3.1/Android 16 缓存，没有解包完整 ROM。

- `framework.jar`、`framework-res.apk`、`miui-framework.jar`、`miui-services.jar` 三方一致；没有发现可直接复用的通用 Framework/WindowManager 修复。
- K40 `services.jar` 与 `MiuiSystemUI.apk` 有差异，但看到的差异主要为 K40 定制服务和目标 UI 功能；未发现与本次 boot-ready 或 thyme 物理显示提交直接对应的改动。
- K40 设备 overlays 为目标设备专属；`bootanim.rc` 三方一致。没有复制 K40 内核、vendor、HWC、overlay 或硬件固件。

本次因此没有进行猜测性 Framework/HWC 修复。

## C24 诊断实现

C24 从 C23 继承现有启动和图形配置，只新增一个 system init 诊断服务：`post-fs-data` 后运行 15 分钟，每 10 秒记录 `sys.boot_completed`、`service.bootanim.exit`、bootanim/SurfaceFlinger/zygote/vold/netd 状态、关键进程 PID、EGL 路由及 composition format；约每分钟有界采样 WindowManager、ActivityManager、SurfaceFlinger/display、layer list、BootAnimation latency 与 HOME 解析。输出走 Android logd/pmsg，不写入持久分区。

该诊断服务的真实运行和 pmsg 留存尚未验证；周期性 binder dumps 可能轻微改变启动时序。它不改 SELinux enforcing、GPU 路由、HWC/vendor、内核、fstab、加密或用户数据。只有首次 C24 启动证据才能验证这些采样实际可用。

构建时首次尝试因 EROFS AVB descriptor data extent 增加 4096 bytes 与复用检查冲突而停止，未访问设备。第二次构建按新的 system hashtree extent 更新 system descriptor；其他 descriptor/AVB 元数据保持，LP 布局通过检查。主机侧 EROFS、AVB、LP、脚本语法、镜像内容与 SELinux xattr 检查通过。完整构建详情见 [build report](BUILD_REPORT.md) 与 [manifest](BUILD_MANIFEST.json)。

## 刷写及当前状态

已顺序写入 `super` 与 `vbmeta_system_a`，Fastboot sparse/write 返回成功。其余 boot、vendor_boot、dtbo、vbmeta_a 未改写。C24 尚未启动，不能视为开机修复或实机诊断验证。启动前先使只读观察器 ARMED，并等待用户在设备旁确认。

| 目标分区 | 镜像大小 | SHA-256 |
|---|---:|---|
| `super` | 7,701,896,152 bytes | `2B84BD93ADFA85FC851A17937B7F96AB4176F01F3E3D00FFC2DB78766BA2CDD8` |
| `vbmeta_system_a` | 131,072 bytes | `1A67C4A2E22DA746E184B146D7DD65059D00FB501EE3642DA1BD2AEFCE706D08` |

本轮没有清除 userdata/metadata、切槽、修改 misc/BCB、恢复 PixelOS、写入设备身份/校准分区或回锁 Bootloader。公开仓库没有包含 ROM、固件或分区镜像。
