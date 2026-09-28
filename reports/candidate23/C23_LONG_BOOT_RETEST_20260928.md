# C23 完整开机窗口复验报告

日期：2026-09-28（香港时间）  
候选：`C23-long-boot-retest`  
实验性质：对已刷入的 C23 进行一次受控启动观察；未刷写或构建镜像。

## 结论

C23 在本轮运行至少约 11 分 52 秒后，仍没有出现 HyperOS 启动画面、设置向导或桌面。用户确认整个观察期间手机只显示静态小米 Logo。主机 ADB 始终未上线；用户手动进入 Fastboot 后，观察器在 2026-09-28 15:59:07 HKT 首次重新检测到 Fastboot。

本次 pmsg 证明 Android 用户空间持续运行到约 11 分 38 秒，`/data` 挂载和 fscrypt 初始化成功，并出现 BootAnimation 的 shown-timing 日志。但日志不等于屏幕实际显示动画：现场仍是静态小米 Logo。没有 `sys.boot_completed=1`、`service.bootanim.exit`、SystemUI、SetupWizard 或 Launcher 的直接记录，也没有取得能够确定框架停在哪项服务的 fatal。

此前 EGLConfig、Vulkan RenderEngine 创建、`output buffer not gpu writeable` 等图形 fatal 本轮均未出现。结果与 C23 的 shader-cache prime 绕过相符，但运行时属性值没有被采样，因此不能单独证明属性生效或因果关系。当前没有足够证据构建 C24。

## 启动与设备时间线

- 15:45:04：观察器 `C23-long-boot-retest` ARMED。
- 启动前：唯一设备 `1384e684`；`product=thyme`、A 槽、Bootloader 解锁、Bootloader Fastboot（非 userspace）；A/B 均 `unbootable=no`、`successful=no`；A retry=6、B retry=7。
- 15:47:14.282：执行唯一一次 `fastboot reboot`；15:47:14.325 返回 `OKAY`。
- 启动后 USB 设备短暂消失；ADB 全程 absent；主机在 15:59:07.109 首次再次检测到 Fastboot，约为启动命令后 11 分 52.8 秒。用户确认是在静态小米 Logo 下手动进入 Fastboot；时间线本身不用于推断 Fastboot 是自动进入还是按键进入。
- 用户观察：整个等待期间始终为静态小米 Logo。未见 Recovery，也未见 HyperOS 动画/设置向导/桌面。
- 启动后 A 槽 retry 从 6 降到 5；`unbootable=no`、`successful=no`。B 槽状态仍为 `unbootable=no / successful=no / retry=7`。
- 最终只读复核（16:19:25 HKT）：设备仍在 `thyme` Bootloader Fastboot，A 槽、解锁、非 userspace Fastboot。

## pstore 与用户空间证据

完整 Standalone 导出目录：`standalone/run_20260928_160036/THYME_DIAG/`。诊断卷 8 个文件共 20,433,856 bytes；复制错误为 0，源/副本每项大小与 SHA-256 均一致。

| 文件 | 归属与观察 |
|---|---|
| `pstore/console-ramoops-0` | 2,097,140 bytes。保留内容从内核 uptime 120.114755s 到 702.552956s，未见 panic、Oops 或重启调用栈。该文件未包含更早启动段；具体丢失机制不能仅凭当前文件确定。 |
| `pstore/pmsg-ramoops-0` | 1,401,451 bytes；日志时间戳从设备时钟 `01-20 23:48:24.409` 到 `01-21 00:00:02.292`，间隔约 697.883s。设备时间基准不可靠，使用时间差而非绝对日期。内容与本轮启动时间线和本轮进程序列相符。 |
| `dmesg_diag_boot.txt` | Standalone 诊断系统自身 dmesg，不作为 C23 内核日志。 |
| `oops.raw` | 16 MiB，SHA-256 `7D1E254BBEB4803D79FDF96F673EF4DC9C7D0EAE68DF3019C2384B3439E4BB66`；与此前历史残留相同，不归属本次 C23。 |
| `diag_status.log`、校验文件及 `System Volume Information/*` | Standalone/诊断卷元数据；全部保留并纳入清单。 |

这次 console 文件从 uptime 120 秒开始，因此不能用它证明 First Stage/Second Stage 的具体起始日志；前一轮 C23-retest 已独立证明这些阶段推进。本轮 pmsg 记录：

- vold 对 F2FS `/data` 执行 fsck 后挂载成功，随后进行 system-wide fscrypt key 初始化并创建密钥；keystore2 也启动。
- `BootAnimationShownTiming start time: 40943ms` 出现一次。此日志仅说明 BootAnimation 代码记录了 shown timing，不证明屏幕呈现了 HyperOS 动画。
- keystore2 仅记录等待 `sys.boot_completed=1`；未发现属性已变为 1 的记录。没有 `service.bootanim.exit` 或 SystemUI/SetupWizard/Launcher/ActivityManager 的直接启动记录。日志没有证明这些组件绝对未启动，但无法据此确认它们启动或成功运行。
- 本轮没有出现 C19 的 `no suitable EGLConfig found`、C21 的 `Could not initialize Vulkan RenderEngine`、C22 的 `output buffer not gpu writeable` 或 `service.sf.prime_shader_cache` 相关错误文本。运行时属性没有直接采样。
- 明确可见的重复崩溃包括：`netd` SIGABRT 138 次（栈落在 `libnetd_updatable_init.cfi+576`）、指纹 HAL SIGSEGV 137 次（多次 fault address `0xd0`），以及 `audio.service` SIGSEGV 74 次（fault address `0x0`）。这些问题真实存在，但本轮没有证据证明它们导致静态 Logo。
- `UltraFrameworkComponentFactoryImpl` 的 `ClassNotFoundException` 共 23 次，堆栈经过 `android.view.SurfaceControl.<clinit>`。当前证据没有关联到致命退出或启动界面停滞原因，暂列为待验证线索，不据此直接补包或改框架。
- SurfaceFlinger 域出现对 Qualcomm IPerf 和 Xiaomi HWC Extension 服务的 `find` AVC；没有证据证明这些 AVC 阻止显示。

## 决策与下一步

- C23 已完成完整窗口复验；本轮从 reboot 到 Fastboot 首次被主机检测超过 11 分钟，不是上一轮约 2 分钟时的提前人工中断。
- 本轮没有取得第二屏；C23 的启动验收仍未完成。
- 暂不构建 C24。现有日志显示启动推进到 BootAnimation 相关用户空间阶段，但没有可据以修复的明确致命错误；不能把重复的网络/指纹/音频崩溃或 `UltraFrameworkComponentFactoryImpl` 缺失直接认定为根因。
- 下一次主机侧诊断应只定点查明为何没有 `bootanim.exit`/`sys.boot_completed` 和框架界面证据，并核对 `UltraFrameworkComponentFactoryImpl` 对应类/配置是否是可选路径。若需参考 K40，只提取成功包中与该具体框架/启动服务路径对应的少量文件；当前缓存的 K40 图形切片没有包含 framework JAR，不能声称已经完成这项比较。
- 目前设备保持 Fastboot；不执行 C24、PixelOS 恢复、清数据、BCB 或分区写操作。

## 证据路径

- 主机观察：[完整启动观察目录](../../evidence/candidate23/host-observations/long_boot_retest/run_20260928_154458/)（命令、ARMED、启动前/后槽位、USB/ADB/Fastboot 时间线、空 logcat 文件及最终只读状态）。
- Standalone 全量副本：[完整导出目录](../../evidence/candidate23/standalone/long_boot_retest/run_20260928_160036/)（THYME_DIAG 原始文件、来源记录、文件清单、SHA-256、导出时间线）。逐项来源和公开哈希见[本轮公开清单](../../evidence/candidate23/long_boot_retest/PUBLIC_EVIDENCE_MANIFEST.csv)及[累积清单](../../evidence/RAW_EVIDENCE_MANIFEST.csv)。
- Standalone 镜像：201,326,592 bytes；SHA-256 `8A5803F09CBCB11056D8356F8D235C3C4450846244FA1B4033ABAAACB213E98B`；仅 RAM 临时启动。

安全边界：本轮仅执行一次 C23 `fastboot reboot`、一次已授权的 Standalone RAM `fastboot boot`、只读查询和完整文件导出；未刷写分区、擦除 userdata/metadata、修改 BCB/boot-control、恢复 PixelOS 或回锁 Bootloader。
