# THYME-OS4 Candidate 17 有效复验报告

日期：2026-09-26（Asia/Hong_Kong）

## 结论

C17 复验实际进入 Android 正常 First Stage、Second Stage 和后续图形启动流程。启动观察器记录到 Fastboot reboot 成功、Fastboot/USB 断开及用户手动返回 Fastboot；ADB 全程未上线。用户观察到小米 Logo 常亮并手动进入 Fastboot。

这次 pstore 没有记录 `hal_graphics_allocator_default` 对 `ion_device` 的 `open` 或 `read` AVC；这支持 C17 权限补充起效，但不能替代对 HAL 调用路径的完整运行时检查。SurfaceFlinger 仍因 `no suitable EGLConfig found` 反复中止。`graphicsengine` 另有一次在 `vkEnumeratePhysicalDevices+4` 的 SIGSEGV。没有证据证明 ANGLE 实际被选中，也没有启动动画、设置向导、桌面或 `sys.boot_completed=1` 的实机证据。

当前没有足够证据证明某条新 AVC 是 EGL 故障根因，也没有构建 C18。

## 主机观察时间线

- 观察目录：`work/reports/20260925_CANDIDATE13_STORAGE_SAFETY_AND_FIRST_FAILURE/observations/C17_revalidation/run_20260926_202822/`。
- 观察器标签为 `C17-retest`。ARMED 记录确认 USB PnP present、ADB absent、Bootloader Fastboot；启动脚本再次确认唯一 Fastboot 设备、`product=thyme`、A 槽、Bootloader 解锁、非 userspace Fastboot。
- `fastboot -s [REDACTED_DEVICE_ID] reboot` 于 `2026-09-26 12:30:01.471 UTC` 发出，退出码 0，返回 `Rebooting OKAY`。
- Fastboot 约在命令发出后立即从主机消失，USB PnP 随后消失；ADB 没有上线。Fastboot 约 148 秒后重新出现，用户确认是手动进入 Fastboot。观察器记录了用户的屏幕观察和操作。
- 主机时间线：`usb_adb_fastboot_timeline.csv`、`host_fastboot_commands.csv`、`host_events.jsonl`、`operator_actions.csv`。启动过程中没有取得 ADB logcat 或实时属性快照。

## Standalone 取证完整性

- 使用已核验 Standalone 镜像进行一次 `fastboot boot` RAM 临时启动；启动时间为 `2026-09-26 12:33:41 UTC`。该操作没有刷写持久分区。
- 动态识别到唯一 `THYME_DIAG` 卷。全部 7 个可访问文件和目录项均复制至本报告同目录下的 `standalone/run_20260926_203340/THYME_DIAG/`，源与副本的文件大小、SHA-256 逐项相同，复制错误为 0。
- 文件包括 `diag_status.log`、Standalone 自身 `dmesg_diag_boot.txt`、`oops.raw`、其 SHA 文件、`pstore/console-ramoops-0`、`pstore/pmsg-ramoops-0` 和卷内系统目录文件。`dmesg_diag_boot.txt` 是 Standalone 内核日志，不是 C17 日志。
- C17 console：652,006 字节，SHA-256 `31D9AC57CB669B8B0DEFEB7A82B9700D4BD2E539BAB415433A5E667DD7C2073E`。
- C17 pmsg：438,731 字节，SHA-256 `717C2AD1A70DAD5381EA8D4A6C00D962E08B154CB3416F89041CBABAC59BC152`。
- 本轮 `oops.raw` 仍为 16 MiB，SHA-256 与 C14–C16 取证相同；不能将其作为本轮新 panic 证据。
- 原始 pstore、oops 和整卷副本只保存在本机，不公开上传。

## C17 Android 启动证据

### First Stage、Second Stage 与策略

- console 仅有一个 C17 Linux kernel 启动实例和一条启动命令行，设备型号为 thyme，槽位为 A，使用正常 Android 启动路径。
- `init first stage started` 出现在 kernel uptime `2.071914s`；`init second stage started` 出现在 `3.220124s`。
- metadata ext4 检查及挂载成功；system、system_ext、product 等逻辑文件系统挂载成功。APEX Bootstrap 激活 4 个包。
- platform policy hash 与 ODM 的 precompiled hash 不同，Init 记录 `Compiling SELinux policy`；随后进入 `enforcing=1`，并加载 system、system_ext、product、vendor 和 odm file contexts。由此可确认本次走动态策略编译并进入 enforcing Second Stage。

### `/data` 与 Keymaster

- vold 记录 metadata encryption key 已存在并被使用；`fscrypt_mount_metadata_encrypted` 报告 `encrypt: 0 format: 0`。
- F2FS `/data` 挂载返回成功：`/dev/block/mapper/userdata` 挂载到 `/data`，耗时约 131 ms。随后执行 `enablefilecrypto` 和 `keymaster earlyBootEnded`，均有完成记录。
- 日志没有 `QSEECom_start_app failed` 字符串；这不等同于 Keymaster/Gatekeeper 全功能验收通过。

### SELinux 与图形启动

- console 和 pmsg 均没有 `hal_graphics_allocator_default` 或 `ion_device` 的记录，也没有图形分配器对 `ion_device` 的 `open` AVC。此前 C16 的具体 open 拒绝本轮未复现。
- console 仍记录 `hal_camera_default` 对 `ion_device` 的独立 `{ read }` AVC；该域与本轮修复的 graphics allocator 域不同。
- console 还记录 `graphicsengine` 对 `vendor_default_prop` 的 `{ read }` AVC。日志没有给出被拒绝的属性名，不能确认它是否与 Vulkan 崩溃相关；没有据此扩大 SELinux 权限。
- pmsg 包含 24 条 SurfaceFlinger `no suitable EGLConfig found` abort；堆栈指向 `SkiaGLRenderEngine::chooseEglConfig`。最早记录约为设备时钟 `04:31:16.156`，最后一条约为 `04:33:10.622`。
- pmsg 记录一次 `graphicsengine` SIGSEGV，栈顶为 `libvulkan.so vkEnumeratePhysicalDevices+4`，其调用者为 `MiVulkanPipelineCacheBuilder`。
- pmsg 未出现 ANGLE 加载标记、bootanimation/bootanim 记录或 `sys.boot_completed=1` 的实际设置记录。`Android META-EGL` 字样不能证明底层选择的是 ANGLE。

## 工程判断与下一步

1. C17 本轮首次取得有效的 Android 用户空间取证。C13/C16/C17 已确认能够走到 Second Stage；本轮 `/data`、vold 和 APEX 均继续正常推进。
2. C17 没有复现图形分配器 `ion_device open` AVC，权限修复有实机证据支持；SurfaceFlinger EGLConfig 阻塞仍然存在，未进入 HyperOS 启动画面或桌面。
3. 不再重复刷写或盲目重试 C17。下一轮重点是确定 EGL Loader 实际后端、ANGLE 是否装载、可用 EGLConfig 与 thyme Gralloc/HWC 的格式对应关系；同时将 Vulkan 枚举崩溃作为相关但尚未证明因果的故障记录。
4. 对 `graphicsengine -> vendor_default_prop { read }` AVC，只能按实际属性访问路径查明属性名后再决定是否修复；当前不添加通用或宽泛 allow。
5. 尚未形成有证据支撑的 C18 镜像改动，因此本轮不构建 C18。相机、音频、netd 和其他非启动关键故障暂不作为桌面前置条件。
6. C17 后没有清除 userdata/metadata、修改其他持久分区、恢复 PixelOS 或回锁 Bootloader。当前主机枚举到 `THYME_DIAG` USB 卷，ADB/Fastboot 不在线；PixelOS 不应报告为已启动或健康在线。
