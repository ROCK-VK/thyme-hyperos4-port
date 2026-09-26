# THYME-OS4 项目当前状态

## 目标

将 Xiaomi 15（dada）的 HyperOS 4 / Android 17 用户空间移植到 Xiaomi Mi 10S（thyme）。当前优先突破图形初始化，进入 HyperOS 启动画面、设置向导或桌面；外围功能不作为开机前置条件。

## 当前设备与刷写版本

- C18 已刷写到 `super`、`vbmeta_system_a` 并执行一次首次启动。用户观察到小米 Logo 亮约十几秒后黑屏，随后设备自动返回 Fastboot；未看到 HyperOS 启动画面、设置向导或桌面。ADB 未上线，Android 日志未取得。
- C18 观察器运行目录：`work/reports/20260926_CANDIDATE18_NATIVE_ADRENO/observations/run_20260926_215459/`。记录显示启动命令于 21:55:33（UTC+8）返回成功，Fastboot 约 34 秒后消失、约 69 秒后重新出现。
- 随后的两次 Standalone RAM 启动均在镜像传输后被 Bootloader 拒绝：`Failed to load/authenticate boot image: Load Error`。本地镜像仍通过原大小与 SHA-256 检查；未出现 THYME_DIAG 卷，故没有 C18 pstore/Standalone 文件副本。尝试记录在 `work/reports/20260926_C18_NATIVE_ADRENO/standalone/run_20260926_215725/` 与 `run_20260926_220042/`。
- 最新只读 Fastboot 状态：设备 `[REDACTED_DEVICE_ID]`、product=thyme、A 槽、unlocked=yes、is-userspace=no；`slot-unbootable:a=yes`、`slot-successful:a=no`、`slot-retry-count:a=0`。这些槽位标志没有启动前基线，原因未知。当前未恢复 PixelOS。
- Bootloader 仍解锁。未写入 persist、modemst、EFS/NV、misc/BCB、校准或身份分区；本轮未清除 userdata/metadata，也未进行任何 Candidate 后续刷写。

## 最新 C17 实机证据

报告：work/reports/20260926_CANDIDATE17_RETEST/REPORT.md。主机观察目录：work/reports/20260925_CANDIDATE13_STORAGE_SAFETY_AND_FIRST_FAILURE/observations/C17_revalidation/run_20260926_202822/。本轮 Standalone 完整副本：work/reports/20260926_CANDIDATE17_RETEST/standalone/run_20260926_203340/。

- Observer 已 ARMED；fastboot reboot 返回退出码 0 / Rebooting OKAY。ADB 全程未上线，用户看到小米 Logo 后手动进入 Fastboot。
- C17 pstore 有一个正常 Android/A 槽启动实例：first-stage 与 second-stage Init 均出现；metadata、system/system_ext/product 等逻辑挂载、APEX Bootstrap（4 个包）和 enforcing 第二阶段成功。
- SELinux 采用动态策略编译，最终进入 enforcing=1。
- vold 使用已有 metadata encryption key；/data F2FS 挂载成功，并记录 enablefilecrypto 与 keymaster earlyBootEnded 完成。
- C16 的 hal_graphics_allocator_default -> ion_device { open } AVC 与该域 { read } AVC 在本轮 console/pmsg 中均未出现；支持 C17 权限修复生效，但不是对 HAL 全调用路径的完整验证。
- SurfaceFlinger 仍有 24 次 no suitable EGLConfig found abort；pmsg 另有 graphicsengine 在 vkEnumeratePhysicalDevices+4 的一次 SIGSEGV。二者关联尚未证明。
- 未发现 ANGLE 实际加载证据；未取得 bootanimation、设置向导、桌面或 sys.boot_completed=1 证据。C17 的 24 次 EGLConfig abort 具有重复的 chooseEglConfig/Create 调用路径；graphicsengine 的 Vulkan 枚举 SIGSEGV 早约 0.6 秒，但属于独立进程，因果未证。
- 另有 hal_camera_default 对 ion_device 的 read AVC，以及 graphicsengine 对 vendor_default_prop 的 read AVC；不得据此扩大权限，先查明属性访问和实际故障关联。
- Standalone 卷内全部 7 个可访问文件已复制；Manifest 中源/副本大小与 SHA-256 全部相符，复制错误为 0。dmesg_diag_boot.txt 属于 Standalone；oops.raw 与 C14–C16 相同，是旧数据，不作 C17 新崩溃证据。C13–C17 的 Standalone 原始卷副本与主机观察记录已按用户授权逐字节同步到公开仓库 evidence/；本地原件保持未修改。

## 已验证历史基线

- C13：正常 Android First/Second Stage、动态 enforcing 策略、APEX 和 /data 已实机证明；之后的 netbpfload 重启由 C14 绕过。
- C14：BPF 绕过有效，启动到后续图形阶段；SurfaceFlinger EGLConfig abort。
- C15：加入 ANGLE 路由属性，但没有证明运行时实际选择 ANGLE；EGLConfig 故障仍在。
- C16：graphics allocator 的 ion_device read AVC 消失，后续出现 open AVC。
- C17：加入 allocator open 权限；本轮图形 allocator AVC 未复现，但 EGLConfig 阻塞仍在。

## Candidate 18 当前构建

- 报告：work/reports/20260926_CANDIDATE18_NATIVE_ADRENO/REPORT.md。
- C17 的实际 EGL 后端未确定：system build.prop 指向 ANGLE，实际 Android 17 libEGL 含相应路由，但 pmsg 没有 ANGLE 加载或实际 driver 身份记录。
- C18 仅修改 system EGL 路由：默认 persist.graphics.egl=adreno；在 ro.persistent_properties.ready=true 后再次设为 adreno，避免旧 /data 持久 ANGLE 属性覆盖本次路由。目标 thyme vendor 声明 ro.hardware.egl=adreno/ro.hardware.vulkan=adreno，并有原生 Adreno EGL/GLES 库。K40 成功包只作为 adreno 路由参考，未复制其硬件库。
- C18 保留 C17 其余修复和硬件栈；无 SELinux 扩权、无 Vulkan 库替换、无 userdata/metadata 擦除。
- 构建目录：work/stage_h_thyme_os4_candidate_18_native_adreno_run1/images/。写入镜像：super.img 7,684,274,964 bytes，SHA-256 EEA7DD2378DDF84BF1BAF0DC86445025AFDAED3E0CE20DE75654D11D0AA35132；vbmeta_system.img 131,072 bytes，SHA-256 932CFBE646D588AF3B61C3A8D075C2AAD37C5DC6F4906C5200D6B6BEFF65DE73。
- EROFS 检查通过；从 super 提取的 system_a.img 与 C18 system 镜像逐字节一致；vbmeta_system system descriptor 匹配新 root digest，product/system_ext descriptors 继承 C17；LP 布局与 C17 一致。Python 编译、PowerShell AST 和刷写 Dry-Run 通过。
- Observer 属性快照已补充 persist.graphics.egl、ro.hardware.egl、ro.hardware.vulkan、ro.board.platform。C18 已启动一次但未获得 ADB 或设备 pstore；native Adreno 路由是否生效、EGLConfig 是否变化均未验证。当前阻塞优先是已知 Standalone 镜像被 Bootloader 拒绝加载。

## 公开诊断证据

- 用户于 2026-09-26 明确授权将 C13–C17 已保存的 Standalone 原始日志和主机观察记录上传到现有 Public GitHub 仓库；旧的“raw pstore/oops 只留本地”限制已被此授权替代。
- 首批归档包含 8 个 Standalone 导出目录和 6 个 host-observation 目录，共 118 个原始文件、140,935,707 字节；逐文件大小和 SHA-256 已验证，凭据模式排除数为 0，缺失 allowlist 目录为 0。
- 本地原始证据未修改。完整 ROM/固件、系统与 userdata/metadata 分区镜像、misc/校准/设备身份分区备份不公开。
- 公开同步脚本位于公开仓库 scripts/sync_raw_startup_evidence.ps1，并由 scripts/sync_from_local.ps1 调用；新的 Standalone/观察目录仍须明确加入 allowlist。
- 原始证据已推送到 Public 仓库 main，提交 3147a6fd8c0ff1d8c46f1cc49a510d0d0a3790c5；匿名 API 确认 public，4 个跨 Candidate 原始文件 HTTP 200 且远端 SHA-256 与本地清单一致。
- C18 报告、构建清单、构建/受限刷写/启动门控脚本、属性观察器更新、README 和状态日志已公开；报告/清单均匿名 HTTP 200。C18 增量提交 d9a56e34b63b27c07b3c04a5d0fdebcf68ea948e；该提交不含 ROM/分区镜像。
## 下一步

1. 历史实测解释了当前 Standalone `fastboot boot` `Load Error`：A 槽 `slot-unbootable=yes` 时曾出现相同错误；`fastboot set_active a` 重置槽状态后 RAM 诊断镜像成功加载。该记录解释取证阻塞，不解释 C18 本身的启动故障。
2. `fastboot set_active a` 会改变持久 A/B boot-control 元数据。本轮尚未执行，需先取得用户对此项状态修改的明确授权；授权后只重置 A 槽并立即启动 Standalone RAM 诊断，导出后不自动启动 Android。
3. 在取得 C18 pstore 前，不构建 C19，也不凭黑屏修改 EGL/HWC/Gralloc 或扩大 SELinux 权限。当前设备保持 A 槽 Bootloader Fastboot；不清数据、不切 B 槽、不回锁。
