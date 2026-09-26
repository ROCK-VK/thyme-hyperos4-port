# THYME-OS4 项目当前状态

## 目标

将 Xiaomi 15（dada）的 HyperOS 4 / Android 17 用户空间移植到 Xiaomi Mi 10S（thyme）。当前优先突破图形初始化，进入 HyperOS 启动画面、设置向导或桌面；外围功能不作为开机前置条件。

## 当前设备与刷写版本

- 当前 Candidate 19 RGBX 实验镜像已写入 `super` 和 `vbmeta_system_a`；C18 的 boot、vendor_boot、dtbo、vbmeta_a 及其他硬件底层保持不变。刷后没有重启，手机目前保持 Bootloader Fastboot。
- 刷写后只读复核：唯一设备 `[REDACTED_DEVICE_ID]`、`product=thyme`、A 槽、unlocked=yes、is-userspace=no；A 槽 `unbootable=no/successful=no/retry=6`。没有执行清数据、切槽、misc/BCB 修改或回锁。
- C19 尚未首次启动，当前图形效果待真机验证。下一步必须等用户现场确认后，先启动带 `C19-rgbx-format` 标签的观察器并确认 ARMED，再执行一次启动。
- C18 上一轮已通过 pstore 证明进入 First/Second Stage、动态策略/APEX、vold/Keymaster 和 `/data` 初始化；SurfaceFlinger 有 61 次 `no suitable EGLConfig found`（`format: 1`），graphicsengine 另在 `vkEnumeratePhysicalDevices+4` SIGSEGV 一次，因果未证。实际 Adreno/ANGLE 库仍未由运行时映射证明。报告：`work/reports/20260926_C18_NATIVE_ADRENO/C18_RETEST_REPORT.md`；完整取证目录：`work/reports/20260926_C18_NATIVE_ADRENO/standalone/run_20260926_234120/`。

## 历史 C17 实机证据

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

## Candidate 18 构建及复验

- 报告：work/reports/20260926_CANDIDATE18_NATIVE_ADRENO/REPORT.md。
- C17 的实际 EGL 后端未确定：system build.prop 指向 ANGLE，实际 Android 17 libEGL 含相应路由，但 pmsg 没有 ANGLE 加载或实际 driver 身份记录。
- C18 仅修改 system EGL 路由：默认 persist.graphics.egl=adreno；在 ro.persistent_properties.ready=true 后再次设为 adreno，避免旧 /data 持久 ANGLE 属性覆盖本次路由。目标 thyme vendor 声明 ro.hardware.egl=adreno/ro.hardware.vulkan=adreno，并有原生 Adreno EGL/GLES 库。K40 成功包只作为 adreno 路由参考，未复制其硬件库。
- C18 保留 C17 其余修复和硬件栈；无 SELinux 扩权、无 Vulkan 库替换、无 userdata/metadata 擦除。
- 构建目录：work/stage_h_thyme_os4_candidate_18_native_adreno_run1/images/。写入镜像：super.img 7,684,274,964 bytes，SHA-256 EEA7DD2378DDF84BF1BAF0DC86445025AFDAED3E0CE20DE75654D11D0AA35132；vbmeta_system.img 131,072 bytes，SHA-256 932CFBE646D588AF3B61C3A8D075C2AAD37C5DC6F4906C5200D6B6BEFF65DE73。
- EROFS 检查通过；从 super 提取的 system_a.img 与 C18 system 镜像逐字节一致；vbmeta_system system descriptor 匹配新 root digest，product/system_ext descriptors 继承 C17；LP 布局与 C17 一致。Python 编译、PowerShell AST 和刷写 Dry-Run 通过。
- Observer 属性快照已补充 persist.graphics.egl、ro.hardware.egl、ro.hardware.vulkan、ro.board.platform。C18 复验确认进入图形用户空间并反复 EGLConfig abort；C18 native Adreno 实际加载路径仍未知。
- C19 的唯一配置变化是 `system/build.prop` 的 `ro.surface_flinger.default_composition_pixel_format=2`（RGBX_8888），实验依据为 C18 的 EGLConfig 错误参数 `format: 1`；这只是可证伪的兼容性实验，不代表根因已确认。
- C19 构建器 `tools/build_candidate19_rgbx_egl.py` 已成功生成六镜像清单。system EROFS 检查通过，属性已从最终镜像回读；vbmeta_system 的 system descriptor 与新 system 匹配，product/system_ext 描述符和 LP A 槽布局符合 C18 基线。首次构建曾因 Windows 终端编码中断，随后从保留暂存树成功恢复，未覆盖 C18 原件。
- 刷写工具 `tools/flash_candidate19_rgbx_egl.ps1` 默认 Dry-Run，执行范围仅 `super`、`vbmeta_system_a`；`tools/start_candidate19_observed_boot.ps1` 要求新鲜的 C19 Observer ARMED、正确设备和用户现场确认。Python AST、PowerShell AST、Dry-Run 和最终写入镜像哈希检查均通过。
- 本轮两分区刷写均成功：`super.img` 7,684,274,964 bytes，SHA-256 `436B4322842C649C674C9B76AE057894EE0B2AC74EB74A0098FD278CC3E634DD`；`vbmeta_system.img` 131,072 bytes，SHA-256 `1E75E1733BBDFE4CF43D898120F202A5761168CD021B0A160784667EFFB5E652`。super 十个 sparse chunk 全部返回 OKAY。未重启、未清 userdata/metadata。

## 公开诊断证据

- 用户于 2026-09-26 明确授权将 C13–C17 已保存的 Standalone 原始日志和主机观察记录上传到现有 Public GitHub 仓库；旧的“raw pstore/oops 只留本地”限制已被此授权替代。
- C13–C17 首批归档包含 8 个 Standalone 导出目录和 6 个 host-observation 目录，共 118 个原始文件、140,935,707 字节；逐文件大小和 SHA-256 已验证，凭据模式排除数为 0，缺失 allowlist 目录为 0。
- 本地原始证据未修改。完整 ROM/固件、系统与 userdata/metadata 分区镜像、misc/校准/设备身份分区备份不公开。
- 公开同步脚本位于公开仓库 scripts/sync_raw_startup_evidence.ps1，并由 scripts/sync_from_local.ps1 调用；新的 Standalone/观察目录仍须明确加入 allowlist。
- C13–C18 原始证据已推送到 Public 仓库 main。C18 首轮证据提交为 `73fcce153ec54fbcbb06bb713baf7a8ddc780897`；本次 retest 增量将 C13–C18 原始文件累计更新至 156 个、177,313,846 bytes。公开同步器报告凭据/策略排除数 0、缺失目录 0。
- 匿名 GitHub API 确认仓库 Public、默认分支 main；远端 C18 pmsg 可匿名下载，字节数与 SHA-256 均匹配公开 manifest。C19 报告、六镜像构建清单、构建/刷写/启动门控脚本已公开；完整系统镜像未上传。
- 最新公开内容提交：`0dbd63b71c5c0a0c6b7bbcfe9e66c799ee69c396`。此前 C13–C17 文件校验记录见提交 `3147a6fd8c0ff1d8c46f1cc49a510d0d0a3790c5`；C18 初次实验提交为 `d9a56e34b63b27c07b3c04a5d0fdebcf68ea948e`。

## 下一步

- 等用户确认在场后，以 `C19-rgbx-format` 启动只读观察器，确认 ARMED，再运行启动门控执行一次 `fastboot reboot`。
- 观察 SurfaceFlinger 是否以 `format: 2` 重新选择 EGLConfig、EGL abort 是否消失，以及是否出现 bootanimation、设置向导或桌面；若失败，保留现场并完成 Standalone 全量取证后再分析。
- 不清除 userdata/metadata。C18 的 EGLConfig 阻塞已明确，不复验 C17、不重建内核、不替换整套 GPU 栈，也不把 Vulkan SIGSEGV 的因果关系写成已证事实。
