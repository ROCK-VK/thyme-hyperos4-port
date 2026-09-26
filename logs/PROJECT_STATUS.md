# THYME-OS4 项目当前状态

## 目标

将 Xiaomi 15（dada）的 HyperOS 4 / Android 17 用户空间移植到 Xiaomi Mi 10S（thyme）。当前优先突破图形初始化，进入 HyperOS 启动画面、设置向导或桌面；外围功能不作为开机前置条件。

## 当前设备与刷写版本

- 最近一次持久分区刷写仍为 C17：仅 vbmeta_system_a 与 super；其余引导镜像沿用 C13 基线。C17 后未刷写其他 Candidate，也未清除 userdata/metadata。
- C17 首启复验已执行一次受控 Fastboot reboot。观察器记录命令成功、USB/Fastboot 离线，约 148 秒后 Fastboot 重新出现；用户确认是手动返回 Fastboot。
- 故障后按既有授权 RAM 启动 Standalone 并只读导出。最近一次主机查询中设备处于 Standalone USB Mass Storage，THYME_DIAG 卷已挂载；ADB、Fastboot 均未枚举。PixelOS 尚未恢复或启动。
- Bootloader 仍保持解锁。未写 persist、modemst、EFS/NV、misc/BCB、校准或设备身份分区；未执行回锁。
- C17 后未再次擦除 userdata/metadata。C17 本轮确认 metadata 加密状态可用，/data F2FS 挂载成功。

## 最新 C17 实机证据

报告：work/reports/20260926_CANDIDATE17_RETEST/REPORT.md。主机观察目录：work/reports/20260925_CANDIDATE13_STORAGE_SAFETY_AND_FIRST_FAILURE/observations/C17_revalidation/run_20260926_202822/。本轮 Standalone 完整副本：work/reports/20260926_CANDIDATE17_RETEST/standalone/run_20260926_203340/。

- Observer 已 ARMED；fastboot reboot 返回退出码 0 / Rebooting OKAY。ADB 全程未上线，用户看到小米 Logo 后手动进入 Fastboot。
- C17 pstore 有一个正常 Android/A 槽启动实例：first-stage 与 second-stage Init 均出现；metadata、system/system_ext/product 等逻辑挂载、APEX Bootstrap（4 个包）和 enforcing 第二阶段成功。
- SELinux 采用动态策略编译，最终进入 enforcing=1。
- vold 使用已有 metadata encryption key；/data F2FS 挂载成功，并记录 enablefilecrypto 与 keymaster earlyBootEnded 完成。
- C16 的 hal_graphics_allocator_default -> ion_device { open } AVC 与该域 { read } AVC 在本轮 console/pmsg 中均未出现；支持 C17 权限修复生效，但不是对 HAL 全调用路径的完整验证。
- SurfaceFlinger 仍有 24 次 no suitable EGLConfig found abort；pmsg 另有 graphicsengine 在 vkEnumeratePhysicalDevices+4 的一次 SIGSEGV。二者关联尚未证明。
- 未发现 ANGLE 实际加载证据；未取得 bootanimation、设置向导、桌面或 sys.boot_completed=1 证据。没有新证据支持 C18 镜像改动，C18 未构建。
- 另有 hal_camera_default 对 ion_device 的 read AVC，以及 graphicsengine 对 vendor_default_prop 的 read AVC；不得据此扩大权限，先查明属性访问和实际故障关联。
- Standalone 卷内全部 7 个可访问文件已复制；Manifest 中源/副本大小与 SHA-256 全部相符，复制错误为 0。dmesg_diag_boot.txt 属于 Standalone；oops.raw 与 C14–C16 相同，是旧数据，不作 C17 新崩溃证据。原始卷副本和 pstore 仅本地保存，不公开。

## 已验证历史基线

- C13：正常 Android First/Second Stage、动态 enforcing 策略、APEX 和 /data 已实机证明；之后的 netbpfload 重启由 C14 绕过。
- C14：BPF 绕过有效，启动到后续图形阶段；SurfaceFlinger EGLConfig abort。
- C15：加入 ANGLE 路由属性，但没有证明运行时实际选择 ANGLE；EGLConfig 故障仍在。
- C16：graphics allocator 的 ion_device read AVC 消失，后续出现 open AVC。
- C17：加入 allocator open 权限；本轮图形 allocator AVC 未复现，但 EGLConfig 阻塞仍在。

## 下一步

1. 暂不重复启动 C17，也不盲目构建 C18。
2. 定点检查 EGL Loader 实际后端、ANGLE 是否加载、EGLConfig/native visual 与 thyme Gralloc/HWC 格式匹配；将 Vulkan SIGSEGV 作为相关但未证因果的现象。
3. 对 graphicsengine -> vendor_default_prop { read } 查明属性名及实际调用路径后再决定是否修改。
4. 保留当前 C17 镜像与原始日志；确定最小证据支持的修复后再构建。下一次刷写和新 Candidate 启动遵守当轮授权及用户现场确认要求。
5. 取证完成后如需恢复 PixelOS，先确认设备模式并沿用项目恢复流程；不得覆盖本轮证据。
