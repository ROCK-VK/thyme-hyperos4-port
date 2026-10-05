# THYME-OS4



**Xiaomi 18 Pro Max (`madrid`) HyperOS 4 / Android 17 移植至 Xiaomi Mi 10S (`thyme`)**



> **Donor 已更正（2026-10-05）**：本项目此前的移植 donor 是 Xiaomi 15（`dada`）。
> 经 M00 静态审计确证，社区中**实测可在小米 10S 上启动 HyperOS 4** 的包来自
> **Xiaomi 18 Pro Max（`madrid`）**。项目最终目标自此正式定为
> **官方 madrid HyperOS 4.0.19.0.XEOCNXM → thyme**。
> C13–C47 保留为 `Legacy THYME Android-17 Compatibility Research Line`（历史真机故障数据库与
> thyme 适配知识仍有效），新的 madrid 主线改用 **M01 / M02 / M03 …** 编号。



这是一个实验性 Android 移植工程。仓库保存可审核的脚本、补丁、项目日志、结构审计报告与用户授权
公开的真机启动诊断与修复证据；**不提供 ROM 下载**。



## M01 Known-Good 首次真机实验（2026-10-05）— 当前阶段

M01-R1 将社区 Known-Good madrid OS4.0.15 → thyme 包的五分区安全子集写入 Xiaomi 10S，五项均返回 OKAY。首次启动停留在 Level 0：Mi Logo 与黑屏交替后回到 Fastboot，ADB 未出现。该实验没有完整复现社区包原始刷机矩阵，因此失败不否定 Known-Good 原包。

首启失败后已使用 Standalone RAM 诊断环境完整复制 THYME_DIAG 卷。pstore 挂载成功但记录为 0；没有本次 M01 的 console-ramoops、pmsg-ramoops 或其他 kernel log。Standalone 自身 dmesg 不能代替 Known-Good kernel 日志；R1 根因仍未确定。

- **[M01 失败现场与 M01-R2 预检报告](reports/m01_known_good_runtime/M01_FAILURE_SALVAGE_REPORT.md)** —— 记录取证完整性、日志归属、根因证据边界及只补刷 Known-Good vbmeta_a 的单变量计划。
- M01-R2 尚未刷写或启动。刷写前必须在 Bootloader Fastboot 重新确认设备状态；刷后停在 Fastboot，只有收到明确“开始启动 M01-R2”指令后才启动。
- 未上传 ROM、super、boot、raw 分区或专有二进制；公开内容仅为经过脱敏的结论摘要。

## M00 Madrid Intake（2026-10-05）— 已完成静态审计



本轮为**只读静态审计**，未刷写、未重启、未与设备交互。五项产出：



- **[成功包 donor 身份审计](reports/m00_madrid_intake_20261005/SUCCESS_PORT_DONOR_IDENTITY.md)** —— 结论 **A. Confirmed madrid**。
  决定性证据：社区包 `product_a:/etc/build.prop` 的 `ro.product.product.name=miproduct_madrid` 与
  `ro.product.build.fingerprint=Xiaomi/madrid/miproduct:17/…/OS4.0.15.0.XEOCNXM`；
  `mi_ext_a` 的 `ro.vendor.build.ab_ota_partitions` 与官方 madrid 4.0.19 **逐字符完全相同**（70 项 madrid 专属分区布局）。
  同时澄清：`ro.product.system.device=missi` 在**官方 madrid 包中同样存在**，`missi` 是平台/SSI 代号，
  不构成否证。

- **[成功包启动兼容架构审计](reports/m00_madrid_intake_20261005/THYME_SUCCESS_REFERENCE_ARCHITECTURE.md)** —— 该 port 靠**三层拼合**启动：
  A 层为 madrid/missi 的 `OS4.0.15.0.XEOCNXM`（与官方 4.0.19 的 `system/apex` **36 个中 35 个逐字节相同**）；
  B 层为 thyme 自己重建的 vendor/odm/mi_ext（**ext4**，官方 madrid 侧全是 EROFS）；
  C 层为社区 thyme 固件包（**不含任何 madrid 固件**）。
  启动键是 `boot` 里一个 **50.6 MB 的 TWRP/Magisk 派生自包含 ramdisk**（`ro.product.system.name=twrp_thyme`），
  因此 `vendor_boot` 的 ramdisk 只有 2,180 B。

- **[官方 madrid OS4.0.19 基线盘点](reports/m00_madrid_intake_20261005/MADRID_PAYLOAD_INVENTORY.md)** —— 66 个分区镜像 / 14.9424 GiB 全量哈希入库。
  两个关键结构事实：**该 OTA 内没有 `super.img`**（super 几何在 manifest，**18,790,481,920 B = 17.50 GiB**，9 个 EROFS 成员，
  `abl`/`devcfg` 缺席）；**madrid 身份是分裂的**（madrid 侧为 odm/product/mi_ext/dlkm，
  `system`/`system_ext`/`init_boot` 是 `missi`，`vendor` 是通用 `mivendor`）。

- **[三方结构地图](reports/m00_madrid_intake_20261005/THREE_WAY_STRUCTURE_MAP.md)** —— 社区成功包 / 官方 madrid 4.0.19 / Legacy C47 的
  A-Kernel·Boot、B-Vendor·ODM、C-System·Framework、D-Network·BPF、E-SELinux·init·VINTF、F-Firmware 六层对照。

- **[受控刷写矩阵与风险评估](reports/m00_madrid_intake_20261005/CONTROLLED_FLASH_MATRIX_AND_RISK.md)** —— 对应脚本
  [`tools/controlled_thyme_success_flash.ps1`](tools/controlled_thyme_success_flash.ps1)（**已生成、DRY-RUN 通过、未执行**）。



### 本轮推翻的两个假设（值得记录）

1. **「旧 4.19 内核没有 BPF 能力 ⇒ netd 必失败」不成立。**
   从各 boot 镜像内嵌 IKCONFIG 实解出的内核配置显示：Legacy C47 与社区成功包的内核**同属 4.19.325 谱系**，
   且**都已启用** `CONFIG_BPF_LSM=y`、`CONFIG_EROFS_FS=y`、`CONFIG_ANDROID_VENDOR_HOOKS=y`；
   而官方 thyme 的 4.19.157 **三者全部缺失**（因此回退官方 thyme 内核不可行）。
   原始 `.config` 见 [`evidence/m00_kernel_configs/`](evidence/m00_kernel_configs/)。

2. **「成功包靠打补丁让 netd 跑通」不成立。**
   社区包的 `libnetd_updatable.so`（103,648 B，SHA256 `2C811151…77AD`）与本项目 dada 参考副本
   `cmp` 结果 **IDENTICAL**，且反汇编确认 `0x11534` 与 `0x1a92b8` **两处均为未修补形态**。
   而 AOSP 源码 `BpfHandler.cpp` 显示该 gate 是**纯内核版本号比较**（`isAtLeast25Q2 && !isAtLeastKernelVersion(5,4,0)`），
   **不做任何 BPF 能力探测** —— 因此「换内核」永远无法通过它；唯一能解释社区包的，是
   **tethering CAPEX 未激活时 `netd` 根本不加载该库**（C44 真机日志中确有
   `netd: library "libnetd_updatable.so" not found`）。
   这一开放问题将由 M01 Known-Good 真机取证回答。



---



## Legacy 线当前状态（截至 2026-10-04，donor = dada）



- **C40 历史性突破**：单变量注入 `ro.media.xml_variant.codecs=_V1_0`，彻底攻克 Zygote `MediaProfiles` 崩溃（0 次复现），Real Zygote 成功进入主循环并 Fork 出 `system_server`，AMS/ATMS/PMS/DMS 等核心服务全面拉起并推进至 Phase 100。

- **C42 屏幕下界修复与动画点亮**：单变量将 vendor 屏幕配置首点亮度下界调整为 `0.000854597`，`DisplayDeviceConfig` 异常彻底归零，内置屏幕（1080x2340@90Hz）成功注册，SurfaceFlinger `setDisplayPowerMode` 生效（state=ON），`BootAnimation` (PID 2082) 首次成功拉起，系统历史性跨过 Phase 100 推进至 **Phase 200** 并成功解锁用户 0 加密存储（CE Storage）。

- **C43 外科手术修复、首启实测与 RAM 证据打捞**：
  * **修复实施**：针对 `netd` (`libnetd_updatable.so`) eBPF abort 实施严格 4 字节 NOP 绕过，双层 APEX v3 签名，6 重深度静态门禁 100% 全绿验收；
  * **首启物理表现**：受控刷入后首次开机，设备停留在第一屏（Mi Logo + powered by Android），未进入第二屏 BootAnimation；
  * **RAM 证据打捞**：通过 Standalone RAM 诊断微内核无损导出 1.57MB `console-ramoops-0` 与 1.46MB `pmsg-ramoops-0`；
  * **权威锁定根本原因**：`apexd` 在开机第 13.7 秒报错 `Failed to decompress CAPEX: Root digest ... does not match with expected root digest in com.android.tethering.capex`，由于外层 CAPEX manifest 遗留出厂旧 digest 未更新，导致 `apexd` 拒绝激活该 APEX；SurfaceFlinger 与 Zygote 因缺失 `libcom.android.tethering.connectivity_native.so` 循环崩溃，无法拉起开机动画。
- **C44 制包修复验证、首启实测与全新阻塞锁定**：
  * **修复验证**：动态提取 payload root digest (`4bdfe2f9...`) 注入外层 `originalApexDigest`，8 重运行时等价门禁全绿；首启 RAM 日志确证 `Root digest ... does not match` 错误 100% 彻底攻克（0 次复现），CAPEX 解压缩校验成功通过；
  * **首启实测**：受控首启设备停留在第一屏（Mi Logo + powered by Android），120s ADB 超时；用户手动切回 Fastboot 待命；
  * **RAM 证据打捞**：Standalone 微内核成功完整打捞 1.28MB `console-ramoops-0` 与 1.13MB `pmsg-ramoops-0`，保全全量诊断树；
  * **全新第一阻塞**：`apexd` 在 mount 解压后的 `/data/apex/decompressed/com.android.tethering@370400000.decompressed.apex` 时内核返回 `Invalid argument` (EINVAL)，导致 Tethering APEX 激活受阻，SurfaceFlinger 和 Zygote 因缺失 `libcom.android.tethering.connectivity_native.so` 循环崩溃；
- **C45 架构验证、首启实测与版本匹配阻塞定位**：
  * **修复验证**：查明 apksigner 默认重置对齐的工具陷阱并引入 `--alignment-preserved` 与 `zipalign -f 4096`；
  * **首启实测**：C44 的 `loop9 sector 0 I/O error`、`unable to read superblock` 彻底消除（0 次复现），内核成功挂载 ext4 文件系统 (`[13.903044] EXT4-fs (dm-11): mounted filesystem without journal`)；
  * **阻塞锁定**：apexd 报告 `Manifest inside filesystem does not match manifest outside it`，payload 内部编码为 `370399999`，外层为 `370400000`，版本差 1 导致激活失败。
- **C46 统一版本对齐、首启历史性突破与全新第一阻塞锁定**：
  * **修复验证**：将 outer、inner manifest 以及 `apex_payload.img` 内部 manifest 版本严格统一为 `370399999`，保持 4096 字节扇区对齐与 `--alignment-preserved` 签名；
  * **首启实测**：受控刷写 `super` 与 `vbmeta_system_a`，启动预算恢复至 7；首启 120 秒观测期内屏幕保持第一屏（Mi Logo + powered by Android）常亮；
  * **RAM 证据打捞**：切入 Fastboot 后，Standalone 微内核 100% 成功无损导出 `console-ramoops-0` (367KB)、`pmsg-ramoops-0` (2.09MB) 与 `dmesg_diag_boot.txt` (155KB)；
  * **历史性突破确认**：
    1. APEX 全量激活：`apexd` 成功激活全部 41 个 APEX 包（`Activated 41 packages. duration=2903ms`），`com.android.tethering` 彻底成功激活！
    2. C45 的 `Manifest inside filesystem does not match manifest outside it` 彻底消除（0 次复现）；
    3. SurfaceFlinger 与 Zygote 畅通无阻，无库缺失崩溃，Real Zygote 成功运行；
    4. `system_server` 历史首次成功深度运行，AMS、ATMS、PMS、PowerStatsService、AppOps 全面拉起，`artd` 成功执行应用编译；
  * **全新第一阻塞精准锁定**：`/system/bin/netd` 在 `Controllers::init()+336` 检测到 `BandwidthController::enableBandwidthControl()` 失败后硬编码调用 `exit(2)`。因官方 4.19 内核无 eBPF pin 规则导致 iptables-restore 失败，`netd` 循环崩溃（5 秒一次累计 300+ 次），`INetd` / `NetdService` 无法注册，SystemServer 的 `NetworkManagementService` 阻塞等待超时（60 秒）触发 Watchdog 重启。
- **C47 规划**：在 `/system/bin/netd` 的 `0x761c0` 处将 `cbnz w0, 0x762b0` 替换为 4 字节 `nop`（`0x1f 0x20 0x03 0xd5`），单变量旁路 exit(2) 退出逻辑，使 netd 正常常驻并向 ServiceManager 注册 `INetd`，解开 SystemServer 网络栈死锁。

- **Legacy 线现状与后续定位（2026-10-05 更新）**：C47 之后**不再延续 C 编号**。原因见上方 M00 章节：
  Legacy 线的 donor 是 `dada`（版本线 `XOCCNXM`），而社区已知可启动包的 donor 是 `madrid`（版本线 `XEOCNXM`），
  两者属于不同机型版本线。C1–C47 的全部真机故障数据、thyme 适配知识与工程基础设施继续有效并复用，
  但新实验统一走 madrid 主线（M01/M02/M03…）。

- [C46 首启突破与根因分析报告](reports/c46_candidate46_build_20261004/C46_FIRST_BOOT_AND_POSTMORTEM_REPORT.md) · [C46 构建与门禁报告](reports/c46_candidate46_build_20261004/C46_BUILD_AND_GATE_READINESS_REPORT.md) · [C45 首启与根因报告](reports/c45_candidate45_build_20261004/C45_FIRST_BOOT_AND_POSTMORTEM_REPORT.md) · [C45 构建与门禁报告](reports/c45_candidate45_build_20261004/C45_BUILD_AND_GATE_READINESS_REPORT.md) · [C44 首启与根因报告](reports/c44_candidate44_build_20261004/C44_FIRST_BOOT_AND_ROOTCAUSE_REPORT.md) · [C43 首启实测与根因分析报告](reports/c43_candidate43_build_20261004/C43_FIRST_BOOT_AND_ROOTCAUSE_REPORT.md) · [C42 首启与证据分析报告](reports/c42_candidate42_build_20261004/C42_FIRST_BOOT_AND_EVIDENCE_ANALYSIS_REPORT.md) · [C40 突破报告](reports/c40_candidate40_build_20261003/C40_FIRST_BOOT_AND_BREAKTHROUGH_REPORT.md) · [项目当前状态](logs/PROJECT_STATUS.md)



## 设备与来源



| 角色 | 设备/平台 | 用途 |

|---|---|---|

| 目标机 | Xiaomi Mi 10S，`thyme`，Snapdragon 870 | 保留目标机自身的内核、设备树、启动链和硬件适配边界 |

| **最终 OS 供体（2026-10-05 起）** | **Xiaomi 18 Pro Max，`madrid`，HyperOS 4 / Android 17，版本线 `XEOCNXM`** | **提供待移植的系统用户空间；最终目标为官方 `OS4.0.19.0.XEOCNXM`** |

| Known-Good 参照 | 社区 `Mi18pm HyperOS 4.0.15 for thyme` 包 | 提供**同机实测可启动**的 thyme 适配层与启动兼容栈参照（已确证其 donor 为 madrid） |

| Legacy OS 供体（已停用） | Xiaomi 15，`dada`，版本线 `XOCCNXM` | C13–C47 使用的旧 donor；结论与真机证据仍有效，但不再是最终目标 |

| 移植参考 | Redmi K40，`alioth`，Snapdragon 870 | 参考成功启动的移植方案和适配方式；不直接移植其硬件专属镜像或分区 |



K40 对照资料显示，成功包的 vendor_boot ramdisk 与原包不同，并增加了 EROFS first-stage fstab 项等适配。详细边界、尚未证明的来源关系及三方差异见 [K40 三方逆向分析](reports/k40/20260918_K40_THREE_WAY_PORT_REVERSE_ENGINEERING_1.md) 和[独立复核](reports/k40/20260918_K40_THREE_WAY_PORT_REVIEW_1.md)。这些内容用于指导 thyme 的适配，不意味着可以照搬 K40 内核、DT/DTBO、射频校准、firmware 或完整镜像。



## Candidate 历程摘要



- **C9**：清理重复 Property Contexts，解决 `persist.radio.imei` Duplicate Prefix 启动失败。

- **C10-WarmDtb**：加入温复位取证支持并建立 ramoops/Standalone 采集流程；温复位不保证所有故障日志都保留。

- **C11**：修复 `system_ext` EROFS 文件元数据和 SELinux xattr，使 APEX Bootstrap 得以继续。

- **C12**：实机确认 `/dev/ion` 使用 `ion_device:s0` 标签；Keymaster/Gatekeeper 的后续访问仍曾被拒绝。

- **C13**：在动态 system_ext SELinux policy 中增加 Keymaster/Gatekeeper 对 `ion_device` 的访问规则。主机侧编译与权限断言通过；真机 C13 日志已进入动态策略编译和 enforcing second stage，但未覆盖相关 HAL，因此 AVC 是否消失仍待验证。

- **C13.1**：主机侧构建过数据挂载保护变体，尚未实机验证；不是当前已验证版本。

- **C14**：绕过已证实与 Android 25Q2/kernel 4.19 不兼容的 BPF loader 重启门控；真机 pstore 证实越过该点，随后发现 SurfaceFlinger EGLConfig abort。

- **C15**：保留 C14 绕过并增加 ANGLE EGL 选择属性；实机进入 second stage 和 /data 挂载，但仍有 SurfaceFlinger EGLConfig abort，未进入启动动画。

- **C16**：图形 allocator 的 ion_device read 拒绝消失，但仍有 open AVC；SurfaceFlinger EGLConfig abort 继续出现。

- **C17**：依据 C16 的 open AVC 增加精确权限，已刷写 vbmeta_system_a 与 super。复验已确认进入 Second Stage，图形 allocator 的 open/read AVC 未复现；SurfaceFlinger EGLConfig abort 持续，尚未进入启动动画。

- **C18**：保留 C17 启动链和修复，将 EGL 路由改为 thyme vendor 配置的 native Adreno；其后 C19/C20 实验继续探索运行时后端。

- **C19**：保留 Adreno 路由并改为 RGBX_8888 EGL 请求；format=2 仍有 43 次 EGLConfig 失败。`reports/candidate19/REPORT.md` 与 `evidence/candidate19/` 保存报告和原始诊断证据。

- **C20**：将 EGL 路由统一为 ANGLE，保留 RGBX=2，并加入 linker 诊断；实机仍有 EGLConfig abort，实际 EGL 后端未知。完整 C20 原始证据见 [`evidence/candidate20/`](evidence/candidate20/) 和 [C20 报告](reports/candidate20/REPORT.md)。

- **C21**：K40 threaded SkiaVk 路由绕开 EGLConfig fatal；实机因 Vulkan RenderEngine 初始化 fatal 未进入启动动画。

- **C22**：以 K40 Android 17 Vulkan UMD 及隔离 GSL/LLVM/Adreno Utils 依赖配套替换 Vulkan ICD；实机越过 RenderEngine 创建 fatal，后在 Skia shader-cache 预热因输出 buffer usage 检查反复 abort。

- **C23**：仅关闭可选 SurfaceFlinger shader-cache 预热。首次尝试保存到 Recovery；后续启动推进到 `/data`/fscrypt 和 BootAnimation shown-timing 日志阶段，但两轮均未见用户实际进入 HyperOS 动画、Setup Wizard 或桌面。长窗口 pmsg 未复现 C22 的 shader-cache fatal，但运行时属性值未采样；静态 Logo 的新根因仍未知。最新报告和完整原始证据见上方链接。

- **C24**：基于 C23 的 framework/display 诊断变体；启动观察约 16 分 43 秒，用户看到第一屏小米 Logo + `powered by Android`，未见 HyperOS 第二屏。ADB 未上线，pmsg 无诊断服务标记。详见[首次启动报告](reports/candidate24/C24_FIRST_BOOT_EVIDENCE_20260928.md)和[完整原始证据](evidence/candidate24/framework_display/20260928_194944/)。





- **C25**：有界 AArch64 helper 同时向 logd 和 metadata 持久目录写样本；实机验证到 Zygote/zygote_secondary restarting、system_server PID 不存在，SurfaceFlinger 与 BootAnimation layer 存在，但物理 present 未证明。Zygote 退出原因待采集。见 [C25 报告](reports/candidate25/C25_FIRST_SCREEN_DIAGNOSTIC_BUILD_FLASH_20260928.md)及[本轮导出与主机观察证据](evidence/candidate25/run_20260928_234427_meta_ro/)。

- **C26**：基于 C25 新增持久 logcat 采集和 Zygote 重启状态/tail 诊断。真机 logcat 记录 netd 因 Android 25Q2+ 不支持 Linux 4.19 而 SIGABRT；之后 PID 1 向两个 Zygote 进程组发 SIGKILL。netd 是否导致 Zygote 首退未单独证实。

- **C27**：删除 netd 的两条 Zygote onrestart 回调以隔离重启链。首启到达 post-fs-data 后进入 Recovery，但 logger 输出为零字节，Zygote 修复效果及 Recovery 原因未知。

- **C28**：在 C27 基础上增加 init 持久 marker 和早期状态写入的受限 logger，保留 C27 启动行为。已构建并仅刷写 super、vbmeta_system_a；仍在 Fastboot，尚未启动。构建/刷写报告见 [C28 报告](reports/candidate28/FLASH_AND_HANDOFF_REPORT.md)，源码和清单见 [C28 tools](tools/candidate28_recovery_diag/) 与 [构建清单](reports/candidate28/BUILD_MANIFEST.json)。



- **C29**：在静止小米第一屏后发现 PID 1 / Zygote / netd 的 metadata marker，但原事件/logcat 为空，pstore 没有可归属 C29 的日志，首因未定。详见 [C29 报告](reports/C29_PID1_FATAL_ROOT_CAUSE_AND_FLASH_REPORT.md)。

- **C30**：pstore 证明 init 在约 32.922 秒经 sysrq 主动触发 kernel panic；/data、fscrypt、keystore2 有推进，netd 重复 SIGABRT；首个 canary 仍为 0 字节，Zygote/system_server 顺序未取得。完整 pstore 与主机观察见 [报告](reports/C30_FIRST_BOOT_AND_PSTORE_REPORT.md) 和 [本轮证据](evidence/candidate30/first-boot-20260930/run_20260930_115223/)。

- **C31**：Zygote critical-escalation 单变量实验与非关键化隔离；实测排除了 init 误判升级杀机的可能性。

- **C32**：一次性 Canary 探针及 Zygote 崩溃现场环境差异分析；Canary 成功生成 tombstone，而 Real Zygote 无法被 crash_dump helper 接管，指出底层环境差异。

- **C33–C36**：逆向探索 Zygote 崩溃转储通道；验证 Linker 环境、管道握手与 stdio/kmsg 追踪链路。

- **C37–C39**：Linker CFI / abortCaller 原位捕获与符号化逆向；C39-DIAG 182 次实机 100% 成功捕获 Abort Message，权威锁定 `libmedia.so` 中 `MediaProfiles.cpp:1743 CHECK((fp = fopen(xml, "r"))) failed.`（闭源库缺失高通 kona 平台 XML 变体分支）。

- **C40**：在 `system/build.prop` 注入 `ro.media.xml_variant.codecs=_V1_0`，单变量修复彻底攻克 Zygote 崩溃（0 次复现），Real Zygote 成功进入主循环并 Fork 出 `system_server`，系统跨越 Phase 100 推进至 DisplayDeviceConfig。

- **C41**：捕获全新阻断点：内置屏幕因最低亮度下界（`0.001709819`）不满足 HyperOS 4 框架下界（`0.000854597`）引发 `DisplayDeviceConfig.constrainNitsAndBacklightArrays` 致命异常与系统崩溃。

- **C42**：修改 vendor 屏幕配置下界至 `0.000854597`，`DisplayDeviceConfig` 异常彻底归零（0次复现），内置屏幕成功点亮供电（state=ON），`BootAnimation` (PID 2082) 首次拉起，系统越过 Phase 100 推进至 Phase 200 并解锁用户 0 加密存储；权威锁定新第一阻断点：netd eBPF 循环 abort 导致 Watchdog 67 秒杀死 system_server。

- **C44**：根据 AOSP `apex_compression_tool.py` 标准将提取的实际 payload `root_digest` (`4bdfe2f9...`) 注入外层 manifest 的 `originalApexDigest`，8 重运行时等价门禁全绿；首启 RAM 日志确证 `Root digest ... does not match` 错误 100% 彻底攻克（0 次复现）；Standalone 微内核打捞出 1.28MB console 与 1.13MB pmsg 证据，权威锁定全新第一阻塞：`apexd` 挂载解压产物报 `Invalid argument` (EINVAL)，导致 Tethering APEX 激活受阻。
- **C45**：三方定点比对确证 dada/K40 均保持 CAPEX 架构且 inner APEX 均为 4096 字节扇区对齐；查明 apksigner 默认重置对齐的工具陷阱并引入 `--alignment-preserved` 与 `zipalign -f 4096`；首启实测证实：C44 的 `loop9 sector 0 I/O error`、`unable to read superblock` 及 `apexd mount EINVAL` 彻底消除（0 次复现），内核成功挂载 ext4 文件系统 (`[13.903044] EXT4-fs (dm-11): mounted filesystem without journal`)；精准锁定全新第一阻塞：apexd 报告 `Manifest inside filesystem does not match manifest outside it`，debugfs 证实 payload 内部封装版本为 `370399999`（dada 官方基线版本），而容器外层编码为 `370400000`，版本差 1 导致 apexd 拒绝激活。
- **C46**：将 outer、inner manifest 及 `apex_payload.img` 内部版本统一为 `370399999`，保持 4096 字节扇区对齐；实测 `apexd` 成功激活全部 41 个 APEX 包，Tethering 成功激活，Manifest 不匹配彻底攻克；SystemServer 首次成功深度运行，AMS/ATMS/PMS 全面拉起；权威锁定新第一阻塞：`netd` 在 `Controllers::init()+336` 因带宽控制失败硬编码调用 `exit(2)` 导致循环崩溃及 Watchdog 超时。
- **C47**：规划在 `/system/bin/netd` 的 `0x761c0` 处将 `cbnz w0, 0x762b0` 替换为 4 字节 `nop`（`0x1f 0x20 0x03 0xd5`），单变量旁路 exit(2) 退出逻辑，使 netd 正常常驻并向 ServiceManager 注册 `INetd`，解开 SystemServer 网络栈死锁。




具体阶段和证据等级以项目状态文件及 Candidate 报告为准，旧报告的“计划/待验证”不会自动成为当前结论。



## 仓库内容



```text

docs/guides/       移植入门、准备计划、审核交接手册（部分内容是历史快照）

logs/              当前状态和按时间追加的执行记录

tools/             精选构建、预检、刷写和诊断脚本

patches/           可审阅的最小策略补丁

reports/           K40 对照、Candidate 分析报告、M00 madrid 结构审计报告

evidence/          C13–C25 Standalone 诊断卷及 USB/ADB/Fastboot 主机观察记录；
                   m00_kernel_configs/ 为各 boot 镜像内嵌 IKCONFIG 实解出的原始 .config 证据

scripts/           带明确文件白名单的本地增量同步脚本

```



建议阅读顺序：先看 [C24 首次启动取证报告](reports/candidate24/C24_FIRST_BOOT_EVIDENCE_20260928.md)、[C24 Framework/display 诊断准备报告](reports/candidate24/C23_FRAMEWORK_DISPLAY_C24_DIAGNOSTIC_20260928.md)、[C23 SurfaceFlinger 预热绕过报告](reports/candidate23/REPORT.md)、[C22 实机故障报告](reports/candidate22/REPORT.md) 和 [C21 K40 SkiaVk 路由报告](reports/candidate21/REPORT.md)，再按以下历史材料阅读：



1. [C20 ANGLE 路由与运行时诊断报告](reports/candidate20/REPORT.md)

2. [当前项目状态](logs/PROJECT_STATUS.md)

3. [C19 RGBX EGLConfig 实机报告](reports/candidate19/REPORT.md)

4. [C17 复验报告](reports/candidate17/20260926_CANDIDATE17_RETEST_REPORT.md)

5. [C17 首次取证结果](reports/candidate17/20260926_CANDIDATE17_FIRST_BOOT_REPORT.md)

6. [C16 首启与 C17 构建/刷写报告](reports/candidate17/20260926_CANDIDATE16_FAILURE_AND_CANDIDATE17_BUILD_FLASH.md)

7. [C15 首启与 C16 图形权限修复报告](reports/candidate16/20260926_CANDIDATE15_FIRST_BOOT_AND_CANDIDATE16_GRAPHICS_ALLOCATOR_FIX.md)

8. [C14 故障与 C15 EGL 诊断方案](reports/candidate15/20260926_CANDIDATE14_FAILURE_AND_CANDIDATE15_EGL_PLAN.md)

9. [C13 netbpfload 故障与 C14 构建](reports/candidate13/20260926_CANDIDATE13_NETBPFLOAD_FAILURE_AND_C14_BUILD.md)

10. [C13 首次启动证据摘要](reports/boot-logs/candidate13_netbpfload_failure_excerpt.txt)

11. [C13 Second Stage 取证准备](reports/candidate13/20260926_CANDIDATE13_SECOND_STAGE_CAPTURE_PREP.md)

12. [K40 三方移植分析](reports/k40/20260918_K40_THREE_WAY_PORT_REVERSE_ENGINEERING_1.md)

13. [C13–C24 原始启动诊断证据索引](evidence/README.md)

## 脚本与构建



`tools/` 中保留了历史 Candidate 构建/预检流程、C13 SELinux 审核、只读启动观察器、启动门控、Standalone 日志导出工具和 PixelOS A0′ 恢复脚本。C18–C23 构建脚本记录定点图形启动实验；C22 配套 K40 Android 17 Vulkan UMD，C23 跳过触发 C22 fatal 的可选 shader-cache 预热；C24 增加 Framework/display 启动诊断。Candidate 刷写脚本可能写入设备分区；启动脚本要求观察器 ARMED 和用户在场确认。脚本本身不构成设备操作许可。它们依赖本机 WSL 环境、外部 ROM 输入和原工程中的暂存资产。本仓库没有完整输入镜像，**不能仅凭 clone 一键复现完整 ROM 构建**。脚本来源及设备操作分类见 [`tools/README.md`](tools/README.md)。



后续更新公开副本时，先审核允许发布的本地变更，再运行文本与原始诊断证据同步器。原始证据同步器只递归处理明确列入 allowlist 的 Standalone 导出和 host-observation 目录，复制原始字节并生成逐文件 SHA-256 清单；可用 `-EvidenceCandidates C22` 只同步新增 Candidate，保留其他 Candidate 的 manifest 行而不重新遍历旧目录。识别到凭据、分区/固件镜像名或超大文件时会排除并记录原因：



```powershell

$env:THYME_OS4_SOURCE = 'C:\path\to\thyme-os4-local'

.\scripts\sync_from_local.ps1 -SourceRoot $env:THYME_OS4_SOURCE -EvidenceCandidates C22

git status --short

git diff --stat

# 人工审查完整 diff 与暂存文件清单后，再 Commit 和 Push

```



同步器不扫描整个工程。新增 Standalone 或 host-observation 目录时，应在 scripts/sync_raw_startup_evidence.ps1 中明确列入 allowlist。原始日志保持逐字节不变；evidence/RAW_EVIDENCE_MANIFEST.csv 记录发布路径、大小和 SHA-256，凭据特征排除项记录在 evidence/RAW_EVIDENCE_EXCLUSIONS.csv。本仓库不上传完整 ROM、固件包、分区镜像或 userdata/metadata 备份。原始日志可能包含设备序列号、CPUID、内核命令行和主机路径。



## 为什么不提供完整镜像



小米 15 原包、K40 成功移植包、PixelOS、展开后的 Android 系统树以及 Candidate 构建镜像都可能包含专有固件、厂商 HAL、应用或其他第三方内容。它们不属于本公开仓库的分发范围。这里不提供完整 ROM 或固件分发。按用户授权，evidence/ 保存 C13–C24 诊断日志和主机观察记录；C21 副本对设备序列号做了可追溯替换，C22–C24 公开诊断证据按逐文件 SHA-256 清单记录；misc、persist、modemst、EFS/NV、校准与设备身份分区备份，以及 userdata/metadata 分区镜像仍不公开。



仓库不附加统一开源许可证。项目代码与随附报告的权利状态应由各自作者/来源确定；不对小米固件、第三方 ROM 或厂商二进制授予任何许可证。



## 安全与免责声明



这是实验性 Android 移植工程。修改启动链或刷写分区可能导致设备无法启动、数据丢失或需要额外恢复。`flash_*.ps1` 和 `restore_*.ps1` 属于可能写入设备分区的脚本；运行前必须读懂目标分区、镜像来源、槽位和设备检查。公开仓库没有附带这些脚本需要的镜像。不要刷写或覆盖 `persist`、`modemst`、EFS/NV、射频校准、设备身份、用户数据或其他未授权分区；Bootloader 必须保持解锁。



本项目没有承诺日常可用，也不保证相机、音频、指纹、NFC、电话、加密或其他功能正常。刷写操作由操作者自行评估和承担风险。
