# THYME-OS4 Candidate 13 Second Stage 取证准备报告

日期：2026-09-26
范围：本机已有 C13 启动证据、pstore 限制及下一次启动采集流程。仅进行主机侧只读调查、脚本修改和静态验证；本轮未刷写、启动或 RAM 引导设备。

## 结论

- 新增的 C13 日志中没有发现 APEX Bootstrap 之后的真实 fatal 或下一处启动错误。当前只能确认普通 Android First Stage、动态 SELinux 编译、enforcing Second Stage 和 APEX Bootstrap 已发生；记录最后时间约为启动后 3.749615 秒。
- 这条记录没有 panic、init fatal、Recovery 或重启标记。`aconfigd-system: 42 output lines suppressed due to ratelimiting` 是日志限流提示，不是进程崩溃证据。
- 现有材料不能区分：设备在最后一条可见日志后继续运行但没有写入 console、后续故障未进入 console、重启导致后续现场未保留，或其他日志留存边界。3.75 秒不是已证明的重启时间。
- 原版 C13 仍是下一次实验的首选，不生成诊断 Candidate，也不重建 `super`。用改进的“先观察、后启动、失败后取证”流程再取得一次高信息量现场；除非新现场仍缺少后续错误，再考虑针对性改变启动日志配置。

## 证据分级

### 直接观测

- `work/reports/20260925_CANDIDATE13_LOG_SALVAGE/run_20260926_002005/pstore/` 只有 `console-ramoops-0`，152,259 字节，SHA-256 为 `B3C1AED57D815DAF14B422623719FE1B6B0A9616D701FD876035926449324311`。内容只有一个可见 Linux 启动实例：一条 Linux version、一条 Kernel command line、一次 `init first stage started!` 和一次 `init second stage started!`。
- 该实例记录了 metadata ext4 检查/挂载、逻辑文件系统挂载、动态 SELinux policy compile、`enforcing=1`、Second Stage Init 和 APEX Bootstrap；最后时间戳为 `[3.749615]`。
- 当前 C13 观察目录 `work/reports/20260925_CANDIDATE13_STORAGE_SAFETY_AND_FIRST_FAILURE/observations/run_20260926_001542/` 的 USB/ADB/Fastboot CSV 从主机首次采样时刻开始。ADB 全程 absent，Fastboot 在观察开始后约 15.978 秒首次出现；logcat 输出与客户端 stderr 都是 0 字节。CSV 没有首次 `fastboot reboot` 的命令时间戳，也不能证明观察器早于启动命令已进入轮询。
- 用户观察到小米 Logo 与黑屏交替两轮，随后手动进入 Fastboot。这是现场观察，不证明中间是否尝试过其他启动实例或 Recovery。
- `oops.raw` 是从独立日志分区导出的 16 MiB 原始内容，含早于本次实验的历史记录；不能把其中旧 Android/HAL/vold 字符串归属为本次 C13。Standalone 自己的 `dmesg_diag_boot.txt` 记录的是诊断环境，不是 C13 内核日志。

### 对日志边界的解释

- 本次 C13 命令行使用 `ramoops_memreserve=4M`；同一启动记录报告 `record_size=0,ftrace_size=0`。本机对应的内核源码 `fs/pstore/ram.c` 将这段预留空间分配给 console 与 pmsg 区域；C13 导出中没有 `pmsg-ramoops-*`。
- 因 `record_size=0`，本配置没有独立的 dmesg crash-record 区。可见的 console pstore 是内核 console 环形记录，不等价于完整 Android logcat，也不能证明 Init 后续没有运行。
- 同一内核记录了 `mtdoops: mtd0 is too large (limit is 8 MiB)`；项目持久日志分区为 16 MiB。本机对应源码 `drivers/mtd/mtdoops.c` 的容量上限为 8 MiB，因此 mtdoops 后备没有接管该分区。该信息解释一种诊断能力缺口，不是启动失败根因；本轮没有修改或向该分区写入。
- 本次命令行包含 `androidboot.init_fatal_reboot_target=recovery` 与 `androidboot.init_fatal_panic=true`；若后续 Init fatal 实际发生，它们使 Recovery/异常重启成为可能机制，但保存记录没有相应 fatal 证据。记录还含 `pstore: Invalid compression size for deflate: 0`；因 console 文件仍能导出，不能据此解释其 3.75 秒尾部。
- 4 MiB ramoops 预留及当前 ring-buffer 设置无法单凭文件尾部说明为什么 console 在 3.75 秒停止。文件只有约 152 KiB，并非已观察到缓冲区填满。原因仍不确定，后续 Android logcat、Recovery ADB pstore 及失败后的 Standalone 导出应并行取证。

## 下一次实验取证流程

1. 经单独授权后，刷写原版 C13 六项镜像：`vbmeta_a`、`vbmeta_system_a`、`boot_a`、`vendor_boot_a`、`dtbo_a`、`super`。刷写结束保持 Fastboot；不自动擦除 `userdata`/`metadata`，也不写其他分区。
2. 在单独的观察器终端运行 `python tools/observe_candidate13_readonly.py --seconds 900`。只有看到 `[ARMED]` 且 ADB absent、目标 Fastboot 在线后，才准备启动。
3. 获得单独的首次启动授权后，使用 `tools/start_candidate13_observed_boot.ps1 -RunDir <实际 run 目录> -Execute`。脚本先校验新鲜 `observer_armed.json`、设备序列号、`product=thyme`、A 槽、Bootloader 解锁及 bootloader Fastboot 状态；然后只执行一次 `fastboot reboot`，并记录命令起止 UTC 时间。默认不带 `-Execute` 时不启动。
4. 观察器以 UTC 记录每轮 ADB/Fastboot 状态、USB 工具输出、状态变化和 logcat 连接时间。一旦 ADB device 或 Recovery 出现，立即流式保存 `logcat -b all`，抓取只读属性、cmdline、内核版本、dmesg、SELinux/ION/挂载快照并尝试复制可读 `/sys/fs/pstore`。不确认 Recovery 中任何清数据界面。
5. 用户屏幕观察可通过 `tools/record_candidate13_event.ps1 -RunDir <run目录> -Message 'Logo appeared'` 等方式写入同一 run 的 UTC 事件 CSV。未出现 ADB 时仍保留 USB/Fastboot 轮询时间线。
6. 若启动失败且设备重新处于 Fastboot，先检查已有主机/ADB 证据；只有取得单独授权后，再使用经 SHA-256 核验的 Standalone 镜像做一次 RAM 临时启动并只读导出。导出文件名中区分 C13 pstore 与 Standalone 自身 dmesg。任何恢复写入必须等必要证据保存后再按单独授权执行。

## 资产与验证

- 原版 C13 六镜像仍完整；执行 `tools/flash_candidate13.ps1` 默认 Dry-Run 后，六项字节数及 SHA-256 全部通过，计划目标仅为上述六分区。未写入设备。
- Standalone 镜像为 201,326,592 字节，SHA-256 `8A5803F09CBCB11056D8356F8D235C3C4450846244FA1B4033ABAAACB213E98B`；新的 salvage 脚本默认只做主机侧哈希核验。只有明确传入 `--execute-authorized-ram-boot` 才会尝试 `fastboot boot`，该参数本身不构成用户授权。
- Python 观察器与 salvage 脚本通过语法编译和 help 入口检查；两份 PowerShell 脚本通过 PowerShell Parser 静态解析。没有实际启动观察器、运行设备启动脚本或 Standalone RAM 启动脚本。
- 设备本轮只读 Fastboot 查询为目标 serial `[REDACTED_DEVICE_ID]`、`product=thyme`、`current-slot=a`、`unlocked=yes`、`is-userspace=no`；ADB 未枚举。最新持久化记录称 PixelOS A0′ 六镜像已恢复写入，但恢复后的 PixelOS 尚无正常启动验证，因此当前不能称其健康在线。

## 下一步与授权边界

- 不存在已定位的新启动错误，不改 C13 SELinux、fstab、super 或内核；当前不需要 C13.1，也不重复擦除数据。
- 下一次镜像：原版 C13。现有 `userdata` 与 `metadata` 已在前一轮各擦除一次；本轮无证据要求再次擦除。
- 开始实验前需单独授权 C13 六分区刷写。刷完后设备保持 Fastboot；首次 Android 启动需再单独授权。失败后若需要 Standalone RAM 启动/只读导出，也需单独授权。PixelOS 恢复资产仍在，但本轮不自动启动或恢复。
