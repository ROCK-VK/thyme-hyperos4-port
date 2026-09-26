# THYME-OS4 Candidate 16 启动结果与 Candidate 17 构建刷写

日期：2026-09-26（Asia/Hong_Kong）

## 结论

Candidate 16 没有到达 HyperOS 启动画面。C16 实际进入 Android first stage、second stage、SELinux 动态策略编译和 enforcing；BPF 重启点仍被绕过。新的图形分配器 `ion_device { open }` 拒绝发生在首次 EGLConfig abort 前约 2.2 秒。C16 还出现一次 `graphicsengine` Vulkan 枚举路径空指针崩溃。

针对 C16 的直接 AVC，Candidate 17 只把图形分配器现有权限从 `read` 扩为 `open read`。C17 主机构建和两项镜像写入已完成，设备保持 Bootloader Fastboot；尚未执行 C17 首次启动。

## C16 取证

### 设备与文件保存

- 用户观察到小米 Logo 常亮，随后手动进入 Fastboot；启动观察器记录一次 Fastboot reboot，ADB 未上线。
- Standalone RAM 诊断卷通过动态识别的 `THYME_DIAG` 挂载点完整复制。8 个源文件/目录与备份副本的相对路径集合、字节数和 SHA-256 均独立复核一致，详见 `work/reports/20260926_CANDIDATE16_FIRST_BOOT/standalone/run_20260926_191835/`。
- C16 的 `console-ramoops-0` 和 `pmsg-ramoops-0` 用于本轮 Android 分析。Standalone `dmesg_diag_boot.txt` 是诊断内核日志。C16 的 `oops.raw` 与 C15 文件 SHA-256 相同，不能作为 C16 新故障归属证据。
- 主机观察记录在 `work/reports/20260926_CANDIDATE16_FIRST_BOOT/observations/run_20260926_191130/`。Fastboot 在启动后离线并再次出现；用户报告手动操作的时刻不是按键的精确时间。ADB 未上线，没有实时 logcat。

### 已证实的启动阶段

| 证据 | 结果 |
|---|---|
| 可见 kernel 启动实例 | 1 个 |
| First-stage init | 1.878667 秒 |
| SELinux 策略 | 1.973806 秒开始动态编译；3.085901 秒 enforcing=1 |
| Second-stage init | 3.095433 秒 |
| BPF 失败标记 | 未见 `NetBpfLoad` 或 `bpfloader-failed` |
| /data | pmsg 有 vold `Mounted /data` 记录；未清数据 |
| 启动画面 | 未见 bootanimation、设置向导或桌面 |
| Zygote/system_server | 没有它们已启动的证据；pmsg 中 `system_server artifacts on /system` 是 odrefresh 文本 |

本轮没有捕获 Keymaster/Gatekeeper 对 `ion_device` 的 AVC 或 `QSEECom_start_app failed`。这不能证明 Keymaster/Gatekeeper 功能已验收。

### 图形错误

- C16 中图形分配器对 `ion_device { read }` 的拒绝不再出现；但有一条 enforcing AVC：`hal_graphics_allocator_default` 对 `/dev/ion` 缺少 `{ open }`。相机域仍有独立的 `{ read }` AVC，本次不处理。
- 用 C16 kernel console 与 pmsg 中同一 SELinux 服务上下文日志作时钟对齐后，`open` AVC 的 kernel uptime 为 18.507 秒，早于第一条 SurfaceFlinger EGLConfig abort 约 2.2 秒。该时间关系支持先修复权限缺口，但尚不能证明它是 EGLConfig 故障的唯一原因。
- pmsg 记录 31 次 SurfaceFlinger `no suitable EGLConfig found` / SIGABRT；第一次位于设备记录时间 `03:13:32.420`，调用栈包含 `SkiaGLRenderEngine::chooseEglConfig`。
- 同一启动还有一次 `graphicsengine` 在 `vkEnumeratePhysicalDevices+4` 的空指针 SIGSEGV。它与 EGLConfig 失败都是真实错误，但二者因果关系未证实。反复 netd SIGABRT 也被记录；目前没有证据证明其是当前启动画面的直接阻塞，所以未纳入 C17。
- C16 pstore 未直接证明 ANGLE 在设备运行时实际加载。`persist.graphics.egl=angle` 和 system ANGLE 库存在于镜像，但 `Android META-EGL` 字样不能识别底层驱动：Android EGL 包装层在 AOSP 源码中固定使用这些 vendor/version 字符串；Android 17 Loader 则把 `persist.graphics.egl` 作为驱动后缀尝试加载相应库。[AOSP Android 17 Loader.cpp](https://android.googlesource.com/platform/frameworks/native/%2B/android-17.0.0_r1/opengl/libs/EGL/Loader.cpp)；[AOSP egl_display.cpp](https://android.googlesource.com/platform/frameworks/native/%2B/android-17.0.0_r1/opengl/libs/EGL/egl_display.cpp)。

现存 K40 技术报告没有提供可与 C16 对齐的 EGLConfig/ANGLE 运行时修复证据；C17 没有复制 K40 的 kernel、vendor 或显示专属二进制。

## Candidate 17 改动与验证

C17 以 C16 为输入，`system_ext_sepolicy.cil` 唯一权限差异为：

```cil
(allow hal_graphics_allocator_default ion_device (chr_file (open read)))
```

保留 C14 BPF bypass、C15 `persist.graphics.egl=angle`、C16 的 `read` 权限和 C13 Keymaster/Gatekeeper 规则。未改 SELinux enforcing、内核、加密、fstab、HAL 或其他系统组件；不清 `userdata`/`metadata`。

主机侧检查结果：

- 实际 C17 system_ext CIL 经过 `secilc -N` 合并编译，`sesearch` 对 console 中实测的 `hal_graphics_allocator_default` 域返回 `allow ... { open read }`。`-N` 会禁用 neverallow 检查，故该结果不代表 neverallow 独立通过。
- 新 EROFS `fsck.erofs` 通过；从最终 EROFS 回读策略规则、既有 Keymaster/Gatekeeper 规则和 `/dev/ion -> ion_device:s0` 标签均正确。
- 新 `system_ext` AVB hashtree descriptor 匹配新镜像，大小 `808,103,936` 字节、root digest `5afb51507c2a1738cfec735eebf261908764c3f343d12ea90d8b96b42f5906ff`。`vbmeta_system` 中 product/system 描述符与 C16 相同，仅 system_ext 描述符更新。
- `lpdump` 验证 C17 super 的 thyme LP 布局仍包括 `mi_ext_a/b`、`odm_a/b`、`product_a/b`、`system_a/b`、`system_ext_a/b`、`vendor_a/b`；构建使用 C16 同一组其余逻辑镜像。
- 第一次打包因检查脚本使用 dump.erofs 列举模式而未读取 file_contexts 正文，构建在该处停止。修正为内容读取模式后重跑，最终 EROFS、AVB、LP 和镜像生成均完成；失败尝试未涉及设备操作或覆盖 C16。

刷写镜像：

| 分区 | 字节数 | SHA-256 |
|---|---:|---|
| `vbmeta_system_a` | 131,072 | `19E7003D4FF6753C4516E5C7038FB7DC4DA3C2BE3FDE3AC4E24133972AC0FC1E` |
| `super` | 7,684,274,964 | `1AAD17205684A7DEA7C5E6E510992942697E96AEAEB6CA35F45280105E890FA6` |

构建清单及完整六镜像继承摘要在 `work/stage_g_thyme_os4_candidate_17_graphics_allocator_open_run1/images/BUILD_MANIFEST.json`；本次只刷写上表两项。构建脚本为 `tools/build_candidate17_graphics_allocator_open.py`，受限刷写脚本为 `tools/flash_candidate17_graphics_allocator_open.ps1`，默认 Dry-Run。

## 实际刷写与当前状态

刷前 Fastboot 只读预检为 serial `[REDACTED_DEVICE_ID]`、`product=thyme`、A 槽、`unlocked=yes`、`is-userspace=no`。`vbmeta_system_a` 发送和写入均返回 `OKAY`。`super` sparse 1/10 至 10/10 均返回 `OKAY`，Fastboot 总耗时 `200.546s`。刷后设备再次被确认仍是 Bootloader Fastboot、thyme、A 槽且解锁；ADB 不在线、无残留 fastboot 写入进程。

只写入 `vbmeta_system_a` 和 `super`。没有 reboot、userdata/metadata 擦除、其他分区写入、PixelOS 恢复或 Bootloader 状态改变。Candidate 17 首次启动尚未授权/执行，必须等用户在场确认。

## 下一步验收

刷写已完成，设备保持 Fastboot。首次启动前先以 C17 标签运行只读观察器并确认 ARMED，再等用户在场指令后执行一次 Fastboot reboot。重点记录：图形分配器 open AVC 是否消失、EGLConfig abort 是否变化、graphicsengine Vulkan SIGSEGV 是否复现、是否进入 zygote/bootanimation/设置向导或桌面。失败后用户手动回 Fastboot，再按 Standalone 全卷导出流程取证；不自动恢复 PixelOS，也不无理由清数据。
