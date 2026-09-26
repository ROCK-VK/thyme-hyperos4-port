# THYME-OS4 Candidate 20 ANGLE 路由与运行时诊断准备

## 目标与结论

C20 基于已刷入并实机验证启动至 SurfaceFlinger 的 C19，集中验证 Android 17 system ANGLE 路由是否能改变 `no suitable EGLConfig found`。本轮保留 C19 的 RGBX_8888 请求和所有已验证启动修复，没有替换 GPU/Vulkan/HWC/Gralloc 库、扩展 SELinux 或清除数据。

C20 已完成主机构建、针对性静态验证及 `super`、`vbmeta_system_a` 刷写。刷后设备只读状态为 Bootloader Fastboot、`thyme`、A 槽、Bootloader 解锁、A 槽 `unbootable=no`；尚未启动 C20，等待用户现场确认。

## C19 诊断缺口与 C20 依据

- C19 的 pmsg 证明 SurfaceFlinger 以 `format: 2` 请求 EGLConfig，43 次相同配置选择路径均失败；此前没有实际 ANGLE/Adreno 驱动身份记录。
- C19 实际 system `libEGL.so` 含 ANGLE 路由、`persist.graphics.egl` 属性名和请求 ANGLE 失败时使用的 fatal 文本。检查其字符串未找到成功路径的 `ALOGV` 文本，因此只设置 `log.tag.libEGL=VERBOSE` 不会可靠地产生库路径记录；C20 未采用这一无效门路。
- C19 system 中已有 64 位 system ANGLE EGL/GLES 库。没有证据要求替换图形库。
- C19 的 `system/build.prop` 默认设置和 `system/etc/init/surfaceflinger.rc` 中 `ro.persistent_properties.ready=true` 后的动作都强制 Adreno。C20 将两处一致改为 ANGLE，避免 `/data` 中的旧持久属性在加载后重新覆盖路由。
- 实际 C19 `com.android.runtime` APEX payload 内的 AArch64 `linker64` 含 `debug.ld.app.`、`debug.ld.all` 及 `dlopen` 成功/失败日志实现。C20 为 SurfaceFlinger 与 graphicsengine 设置按进程过滤的 dlopen/dlerror 诊断，并设置 `log.tag.linker=DEBUG`。是否产生日志仍受进程 dumpability 等运行时条件影响；无日志不能单独证明库未加载。

## C20 变更

1. `system/build.prop`：`persist.graphics.egl=angle`；保留 `ro.surface_flinger.default_composition_pixel_format=2`；增加：
   - `debug.ld.app.surfaceflinger=dlerror,dlopen`
   - `debug.ld.app.graphicsengine=dlerror,dlopen`
   - `log.tag.linker=DEBUG`
2. `system/etc/init/surfaceflinger.rc`：保留持久属性加载后的覆盖动作，但将值改为 `angle`，删除冲突的 Adreno 覆盖。
3. 只读观察器：在 ADB 可用时按 PID 保存 SurfaceFlinger 与 graphicsengine 的 `/proc/<pid>/maps`，并记录上述运行时属性；不能读取时保留失败记录。

以上是当前图形故障链上的最小修复/诊断集合。没有改变启动内核、vendor_boot、DTBO、SELinux、Vulkan/Adreno 驱动文件、fstab、加密或用户数据。

## 构建与静态验证

- Candidate：`Candidate 20 ANGLE EGL route and runtime diagnostics`
- 基线：C19 RGBX EGLConfig 实验；复用 C19 system tree、当前 thyme 硬件栈、system_ext 与分区配置。
- 新构建目录：`work/stage_j_thyme_os4_candidate_20_angle_route_diag_run1/images/`
- `fsck.erofs` 通过；从最终 EROFS 回读确认 `persist.graphics.egl=angle`、RGBX=2、三项 linker 诊断属性均存在，且没有 Adreno 属性。
- 从最终 EROFS 回读 `surfaceflinger.rc`：持久属性就绪动作是 `setprop persist.graphics.egl angle`，没有残留 Adreno 动作。
- `vbmeta_system` 的 system hashtree descriptor 与新 system 匹配；product/system_ext 描述符沿用 C19，构建器对此进行了断言。
- `lpdump` 确认预期 A 槽逻辑分区与 super 布局；用 `lpunpack` 提取的 `system_a.img` 与 C20 `system_c20.img` 大小相同且逐字节一致。
- Python 与 PowerShell AST 检查通过；刷写脚本只允许 `super`、`vbmeta_system_a`，不包含 reboot/wipe/lock 命令。

## 实际刷写结果

只写入以下目标，命令均返回成功：

| 分区 | 镜像大小 | SHA-256 |
|---|---:|---|
| `super` | 7,684,274,964 bytes | `9DAE08D2288E1F590DD803FDBDA79230A64136B2C3F529AB82E0D0B8F7946334` |
| `vbmeta_system_a` | 131,072 bytes | `E45FCEEC95592764E23DB54114DC6235A4AA6057EA0BB5C5518F10135E85B662` |

`super` 的 10 个 sparse 写入块全部返回 OKAY。刷后 Fastboot 查询仍为唯一设备 `[REDACTED_DEVICE_ID]`、`product=thyme`、A 槽、`unlocked=yes`、`is-userspace=no`、`slot-unbootable:a=no`、`slot-successful:a=no`、`slot-retry-count:a=5`；报告的 `super` 与 `vbmeta_system_a` 分区容量分别为 `0x220000000` 和 `0x20000`。没有重启、擦除、切槽、BCB 操作、其他分区写入或 Bootloader 状态更改。

## 下次实验判定

尚未取得 C20 运行时结果。下次启动前运行已更新的只读观察器并等待 `C20-angle-route-diag` ARMED，再由用户确认现场后启动一次。重点看：运行时 `persist.graphics.egl`；linker 记录或 ADB 进程映射中的实际 ANGLE/Adreno 库；`Failed to load ANGLE` 或动态加载错误；SurfaceFlinger EGLConfig 是否继续以 format=2 失败；graphicsengine Vulkan 崩溃是否仍然出现；是否进入 HyperOS 启动画面、设置向导或桌面。

如果 ADB 未上线且 linker trace 不可用，依据 pstore 中是否出现 ANGLE load fatal 和后续 EGL 错误作有限判断，并明确记录“实际后端未知”，不得把属性文本或 absence of logs 宣称为实际加载证明。

## 产物与公开范围

- 构建清单：`work/stage_j_thyme_os4_candidate_20_angle_route_diag_run1/images/BUILD_MANIFEST.json`
- 构建器：`tools/build_candidate20_angle_diag.py`
- 刷写脚本：`tools/flash_candidate20_angle_diag.ps1`
- 启动门控：`tools/start_candidate20_observed_boot.ps1`
- 观察器：`tools/observe_candidate13_readonly.py`

本报告不包含 ROM、分区镜像、APEX 提取内容或设备备份。C20 尚未完成真机启动或图形验收。
