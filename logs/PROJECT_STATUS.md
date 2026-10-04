# THYME-OS4 项目当前状态

更新时间：2026-10-04 22:45 HKT

## 项目目标与阶段

将 Xiaomi 15（`dada`）HyperOS 4 / Android 17 移植到 Xiaomi 10S（`thyme` / Snapdragon 870）。  
当前阶段：**Candidate 46 实机首启与 Standalone RAM 取证全量完成（0 拷贝错误）；实现历史性里程碑级重大突破：apexd 成功激活全部 41 个 APEX 容器包（`com.android.tethering` 彻底成功激活）；SurfaceFlinger 与 Zygote 彻底摆脱原生库缺失崩溃；SystemServer 历史首次深度启动（ActivityManagerService, ActivityTaskManagerService, PackageManagerService, AppOps, PowerStats 全面启动运行，artd 后台编译）；新第一阻塞精准锁定：`/system/bin/netd` 在 `Controllers::init()+336` 因 `BandwidthController::enableBandwidthControl()` 注入带 BPF 扩展的 iptables 规则失败硬编码调用 `exit(2)` 陷入无限循环退出**。

## 核心有效事实与突破证据

1. **C46 历史性重大突破：APEX 激活、Zygote、SurfaceFlinger 与 SystemServer 全面推进**：
   - **APEX 全量激活**：`[13.771829] apexd: Activated 41 packages. duration=2903ms`，`[15.096176] apexd-snapshotde: Marking APEXd as ready`；
   - **C45 Manifest 不匹配彻底消除**：0 次复现，Tethering 预装 CAPEX 顺利解压并成功验证激活；
   - **SurfaceFlinger 与 Zygote 畅通**：不再发生 `libcom.android.tethering.connectivity_native.so` 缺失 SIGABRT，Zygote 正常启动（pid=1065, secondary pid=1066）；
   - **SystemServer 深度运行**：SystemServer 成功拉起并执行核心服务：`ActivityManagerService$Lifecycle`、`ActivityTaskManagerService$Lifecycle`、`PackageManagerService`、`AppOps`、`PowerStatsService`、`IntentFirewall`、`BatteryStatsImpl`，且 `artd` 成功执行 Binder 事务编译应用包！

2. **新第一阻塞精准锁定：netd 在 Controllers::init() 硬编码 exit(2)**：
   - **崩溃栈证据**：`#06 pc 00000000000762d4 /system/bin/netd (android::net::Controllers::init()+336)` -> `#05 pc exit+40`；
   - **反汇编确证根因**：`netd` 的 `Controllers::init()` 在 `0x761bc` 调用 `BandwidthController::enableBandwidthControl()`，后者尝试通过 `iptables-restore` 插入带 `-m bpf --object-pinned /sys/fs/bpf/netd_shared/prog_netd_skfilter_...` 的带宽控制规则；
   - **失败链条**：由于官方 4.19 内核无定制 BPF 支持，对应 BPF 对象文件未被 pin 到该路径，内核模块 `xt_bpf` 拒绝该规则导致 `iptables-restore` 失败；`enableBandwidthControl()` 返回非零值；`Controllers::init()` 检测到返回值非零，在 `0x762d0` 打印 `Failed to initialize BandwidthController` 并直接执行 `exit(2)`；
   - **系统级连锁反应**：init 不断重启 netd（每 5 秒退出一次，累计崩溃 300+ 次），导致 `INetd` / `NetdService` 始终无法在 ServiceManager 注册；SystemServer 的 `NetworkManagementService` 阻塞等待 netd，最终在 60 秒后触发 Watchdog。

3. **历史有效资产 100% 保持有效**：
   - C40 media codecs variant (`ro.media.xml_variant.codecs=_V1_0`) 保持有效；
   - C42 DisplayDeviceConfig 最低亮度修复 (`0.000854597`) 保持有效；
   - C43 netd 4 字节 NOP 兼容性补丁保持有效；
   - C44 originalApexDigest 动态注入逻辑保持有效；
   - C45 4096 字节扇区对齐与内核 Direct I/O loop 挂载修复保持有效；
   - C46 统一 Manifest 版本号 `370399999` 保持有效。

## 当前设备物理状态

- **设备**：Xiaomi 10S (`[REDACTED_DEVICE_ID]`)
- **当前状态**：手机当前运行 Standalone Diag RAM 诊断系统（挂载 `G:\` 虚拟磁盘，证据已完全打捞并持久化归档），需长按电源 + 音量下重启进入 Bootloader Fastboot
- **当前槽位**：A 槽 (`current-slot: a`)
- **宿主空间门禁**：C 盘 81+ GiB, D 盘 172+ GiB, E 盘 317+ GiB（全绿，远超 50 GiB）
- **Docker/WSL 数据**：100% 零触碰

## 已排除的错误方向与红线纪律

- 严禁清除 `userdata` / `metadata`；
- 严禁修改内核（Kernel）；
- 严禁 Bootloader relock；
- 严禁将 Tethering APEX 改为非压缩格式；
- 严禁在外部 manifest 中使用不一致的版本号（`370400000` 或 `370400128`）；
- 固定闭环纪律：查完日志后先进行 GitHub 增量上传和修改 readme，严禁在同步前草率修改下一个 Candidate。

## 下一步最优先任务

1. 完成 GitHub 增量同步与 push（闭环 C46 证据与文档）；
2. 规划 Candidate 47：在 `/system/bin/netd` 中将 `Controllers::init()` 中调用 `enableBandwidthControl()` 后的条件跳转 `cbnz w0, 0x762b0`（跳转到 exit(2)）安全 NOP（4 字节 NOP），使 netd 即使在带宽控制 iptables 规则失败时不退出的稳定常驻，成功注册 INetd 救活 NetworkManagementService！
