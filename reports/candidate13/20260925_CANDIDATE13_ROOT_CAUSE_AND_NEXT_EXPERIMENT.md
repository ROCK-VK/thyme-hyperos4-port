# THYME-OS4 Candidate 13 启动异常根因调查与下一次诊断实验方案

日期：2026-09-25  
范围：只读分析 C13 pstore、Standalone/主机时间线、C12 对照、Candidate 镜像与 fstab；改进主机只读观察脚本。  
设备操作：本轮没有刷写、重启、Fastboot RAM 启动、BCB/misc 或其他分区写入。

## 结论摘要

当前最有证据支持的链路是：**Candidate 13 某次普通 Init 很可能在第二阶段执行 `mount_all`，`fs_mgr_mount_all` 返回了要求转入 Recovery 的结果；该 ROM 的 Init 随后为 Recovery 准备了 `--prompt_and_wipe_data --reason=fs_mgr_mount_all`。之后保存下来的唯一内核/init 实例已经处于 Recovery 模式。**

这是强推断，不是被保存的首次普通启动日志。pstore 中没有保留 `mount_all` 的调用、挂载失败对象或前序普通启动实例；启动前 BCB 也未采集。因此不能据此断定一定是 `/data`、`/metadata`、vold、AVB 或 SELinux 中的哪一项失败，也不能排除旧 Recovery 请求或其他运行时启动上下文。

没有发现足以解释“选择 Recovery”的静态 C13 镜像错误。C12/C13 引导镜像相同，C13 的 `super` 布局不变，已核验的 system_ext 内容差异只有策略 CIL，`vbmeta_system` 对应更新后的 system_ext hashtree。**不重建 Candidate 13；下一步保持 C13 镜像不变，改进首次启动观察和失败后取证。**

## 1. 证据分级与事件链

### 已直接证明

- C13 原始 `console-ramoops-0` 只有一个可见 Linux/init 启动实例：一个 Linux version、一个内核命令行、一组 first-stage/second-stage init；该文件中的 uptime 未归零。没有第二组内核启动头或 init first-stage 头。
- 该实例在 2.065457 秒首先明确记录 `First stage mount skipped (recovery mode)`。这证明**被保存的这次实例**已进入 Recovery 分支；它不说明设备此前从未跑过普通 Android。
- 在这一行之前的已保存 Linux/init 记录中，没有 Init fatal、first-stage mount fatal、AVB、fstab 或 LP 错误指出为何选择 Recovery；Bootloader 阶段不在这份 kernel console 的直接采集范围。此结论只约束当前保存的实例，不覆盖未保存的前序启动。
- 2.084 秒出现 AVB `Invalid hash size`/digest 错误；约 2.0889 秒出现 `system_ext_a`、`product_a` 的 `DM_DEV_STATUS ... No such device or address` 和逻辑分区更新错误。它们均晚于 Recovery 分支记录，不能用来解释更早的 Recovery 选择。
- 约 3.300096 秒 Recovery 记录 `Boot command: boot-recovery`；约 3.300131 秒收到 `--prompt_and_wipe_data --reason=fs_mgr_mount_all`；约 3.300972 秒记录 `Writing BCB boot-recovery recovery`。没有记录实际擦除/格式化 userdata 或 metadata。
- 该 C13 system_a 的 SHA-256 为 `ee85f2459a6054f6f3b04a3485e552198ef1dfe06e302527a27bd63fc9adc2b4`，与 C7 system SAR 构建输入一致。直接从该镜像提取的 `/system/bin/init` 与 rootlike 构建输入同为 SHA-256 `9bb24ead728c13c50a5c734e6b3f951c83c7a81d86e2f973b1a1bd4fa9cab020`。该二进制包含字符串 `fs_mgr_mount_all suggested recovery, so wiping data via recovery with prompt.`、`--prompt_and_wipe_data` 和 `--reason=fs_mgr_mount_all`。
- 用户观察到约 10 秒小米 Logo、黑屏闪烁，并在手动进 Fastboot 前短暂看见类似 Recovery 的界面和未读文字。Recovery 确实运行过，但该屏幕来源及文字无法恢复，不能凭外观判断当时启动的是哪套 Recovery。
- 主机记录显示 16:48 C13 六分区刷写完成；16:54:09 Windows Kernel-PnP 记录 VID_18D1/PID_D001、序列号 [REDACTED_DEVICE_ID] 的 USB 枚举；16:56:12 StorDiag 记录四个非 ReadWrite SCSI SRB 失败请求，16:56:14–15 主机枚举/导出 Standalone `THYME_DIAG` UMS 卷。没有首次 `fastboot reboot` 的逐命令 transcript，也没有该启动过程的 ADB 连线记录；USB 枚举本身不能识别当时模式。Standalone 的 `dmesg_diag_boot.txt` 是后续诊断环境日志，不是 C13 日志。
- C13 salvage 中的 `oops.raw` 是历史遗留内容，不能归属为 C13 启动；C13 保存目录只有 `console-ramoops-0`，没有 `pmsg-ramoops`。文件及哈希见 [C13 原始 console-ramoops](20260925_CANDIDATE13_LOG_SALVAGE/run_20260925_165614/pstore/console-ramoops-0)、[SHA-256 清单](20260925_CANDIDATE13_LOG_SALVAGE/run_20260925_165614/SHA256SUMS.txt) 和 [前次 Recovery 分析](20260925_CANDIDATE13_RECOVERY_ANALYSIS.md)。

### 强推断，但尚非直接证明

Recovery 收到的 reason 与该 C13 实际 Init 二进制中的定制提示字符串完全对应。结合 Android 常见实现中 `mount_all` 调用 `fs_mgr_mount_all()`、再根据返回码触发 `queue_fs_event()` 的路径，最可能是前一轮普通 Init 通过 `mount_all` 请求转入 Recovery。`mount_all` 属于正常系统第二阶段启动流程；如果这条路径确实在本次启动运行，设备至少曾进入普通 Init 第二阶段，但这不等于已启动 vold、Keymaster、zygote 或 Android framework。

仍有未观测的替代可能：启动前 BCB/Recovery command 已携带相关参数；Bootloader/运行时启动上下文直接选了 Recovery；或先发生 Init fatal 后走 Recovery 目标。C13 启动前没有 BCB 原始快照，故不能排除这些情况。Recovery 后来写入 BCB 是进入 Recovery 后的结果，不能反推此前 BCB 内容。

### 当前无法确认

- 第一次内核是否以普通 Android 模式启动、启动了多久，以及是否发生重启。
- 普通 Init 是否真正执行了 `mount_all`，以及触发该 reason 的 fstab 项、设备、errno 或 fs_mgr/vold 子步骤。
- Recovery 前是否出现 `init: Compiling SELinux policy`、新策略加载失败、Keymaster/Gatekeeper AVC 或 QSEECom 错误。
- 启动前 BCB 是否为空，Bootloader 是否通过 BCB 或其他运行时状态选择 Recovery。
- 之后 PixelOS 恢复后读取 misc 时 BCB 四字段为空；这是 Recovery/恢复操作之后的状态，不能还原首次 C13 启动前的 BCB。

因此不能把本轮结论写成“已确认首次启动失败于 `/data`”或“已确认由 SELinux 导致 Recovery”。

## 2. `fs_mgr_mount_all`、Recovery 参数与 BCB 的含义

- Android Init 的 `mount_all` 调用 fs_mgr。AOSP 参考实现中，`FS_MGR_MNTALL_DEV_NEEDS_RECOVERY` 会调用 Recovery 重启路径，并写入 bootloader message；不同分支的命令参数可能不同。当前 upstream 参考代码对这个返回码使用 `--wipe_data --reason=fs_mgr_mount_all`；本项目实际提取的 Xiaomi donor Init 二进制明确包含 `with prompt` 自定义文本和 `--prompt_and_wipe_data`。所以应以本项目二进制作为目标语义证据，以 AOSP 源码作为执行机制参考，而不能把 upstream 参数直接套到此 ROM。[AOSP `builtins.cpp`](https://android.googlesource.com/platform/system/core/%2B/android16-qpr2-release/init/builtins.cpp)
- AOSP 当前 `fs_mgr` 参考实现中，`NEEDS_RECOVERY` 至少有一个明确路径：可格式化分区因 wiped/encryption-interrupted 等状态挂载失败，随后需要的格式化也失败。它不是“任意 mount 错误”的通用同义词；普通 mount 错误或 vdc 加密失败可返回其他错误。由于 Xiaomi donor 对应源码分支没有在本轮被固定，以上只限定参考路径，不能确认 C13 实际命中的子分支。[AOSP `fs_mgr.cpp`](https://android.googlesource.com/platform/system/core/%2B/main/fs_mgr/fs_mgr.cpp)
- `--prompt_and_wipe_data` 是 Recovery 的“要求用户确认后才可擦除数据”动作，不代表擦除已执行。Recovery 参数可来自 BCB 或 Recovery command 输入；Recovery 在处理后将命令写入 BCB 是可恢复执行流程的一部分。因此 `Writing BCB boot-recovery recovery` 是 Recovery 运行后的状态，不是启动前原因的证据。[AOSP `recovery.cpp`](https://android.googlesource.com/platform/bootable/recovery/%2B/master/recovery.cpp)
- `First stage mount skipped (recovery mode)` 只描述当前 first-stage 判定结果。AOSP 参考实现依据 `force_normal_boot` 与 Recovery 程序存在状态选择此分支；C13 vendor ramdisk 确有 `system/bin/recovery`，静态 vendor_boot cmdline 未包含 `androidboot.force_normal_boot=1`。实际保存的 C13 kernel command line 在面板参数处截断，无法排除 Bootloader/bootconfig 额外传参。C12 与 C13 的 vendor_boot 相同，但 C12 曾进入正常 first-stage，这说明运行时启动上下文仍需纳入比较。[AOSP `first_stage_mount.cpp`](https://android.googlesource.com/platform/system/core/%2B/6ad4d0a601485475645ddd1b23181a4c31754977/init/first_stage_mount.cpp)
- C13 `vendor_boot.img` 静态 cmdline 还包含 `androidboot.init_fatal_reboot_target=recovery`、`androidboot.init_fatal_panic=true`、`reboot=panic_warm`。所以 PID 1 fatal 是另一个可参与的 Recovery 路径；参考 Init 在 fatal 信号时先尝试触发 crash/panic，按配置目标重启也可能作为 fallback。现有可见 Recovery 实例之前没有保存 `InitFatalReboot`、`Trigger crash` 或 panic 现场，因此这是候选路径而非已发生事实。[AOSP `reboot_utils.cpp`](https://android.googlesource.com/platform/system/core/%2B/master/init/reboot_utils.cpp)

## 3. 为何 pstore 可能只留下 Recovery

`console-ramoops` 是固定大小的持久 RAM 日志区域，不是跨启动实例的完整数据库。ramoops 文档说明 console/record 受缓冲区大小限制，新记录可覆盖旧记录，counter 也会在重启后重置。WarmDtb 使部分 warm reset 后 RAM 更可能保留，但不保证故障类型、Bootloader 路径、后续 Recovery 内核和诊断采集顺序都会保留全部启动日志。[Linux ramoops 文档](https://docs.kernel.org/admin-guide/ramoops.html)

本轮 Standalone 是在设备已经显示 Recovery、用户手动回 Fastboot 后才临时启动；采集的是当时可见的 pstore。Recovery 的 kernel/init 输出足以占用有限 console 区域，先前启动即使发生过，也可能没有被保留或已被覆盖。当前单份 console 只能说明“保存下来的实例有一个”，不能证明“设备总共只启动过一次”。

## 4. C12/C13 差异、AVB、LP 与 fstab

| 对比项 | 实际核验结果 | 对本次 Recovery 的解释力 |
|---|---|---|
| `boot.img`、`vendor_boot.img`、`dtbo.img`、`vbmeta.img` | C12/C13 逐字节一致；vendor_boot 有 Recovery binary、first-stage fstab，并带 `init_fatal_reboot_target=recovery` / `init_fatal_panic=true` 参数 | 没有 C13 独有的静态引导镜像改动；不排除 BCB/运行时模式差异 |
| `system_ext` | 两棵解包树各 3,712 项，唯一内容差异为 `etc/selinux/system_ext_sepolicy.cil`：一个注释和两条 Keymaster/Gatekeeper→ion_device allow | 这是预期策略改动；没有静态证据显示它选择 Recovery |
| `system_a` / `product_a` | C13 system_a 提取 hash 与 C7 SAR 输入一致；C12/C13 `vbmeta_system` 的 system/product descriptors 一致 | 未发现两者新增 payload/descriptor 差异 |
| `super` LP metadata | C12/C13 metadata、分区布局及 extents 相同；A 槽 logical partitions 存在，B 槽为空；system_ext_a 942,669,824 B | 没有 LP 布局差异可解释 C13 特有 Recovery |
| `vbmeta_system` | C13 仅 system_ext hashtree root digest 与 C13 system_ext payload 相应变化；system/product descriptor 不变；顶层 vbmeta 的链关系仍指向 vbmeta_system | 静态验证关系一致；Recovery 后的 `Invalid hash size` 不能倒推为进入 Recovery 的原因 |

为核对 super 实际 payload，本轮从 C12/C13 raw super 各自单独提取 A 槽六个逻辑分区并比较 SHA-256。`system_a` 两边均为 `ee85f2459a6054f6f3b04a3485e552198ef1dfe06e302527a27bd63fc9adc2b4`；`product_a` 均为 `87955dbe97ac28b01a214273bd03f36b5886310dc3b2e4128b9f4661e1c3345e`；`vendor_a` 均为 `a53b926922e74df76112c3da76481a9d9ba175d3381026f35c212a0a636c68a0`；`odm_a` 均为 `46ae3bfbb1fbb14de348d04b9d2569b7ee239a7e293f5d0ff78c1ef54604c347`；`mi_ext_a` 均为 `43ed8fc0d1848f5d53bfb7206ac91fe5e5ed4e3f71e958d49f2eea4c9c8b4bce`。只有 `system_ext_a` 不同：C12 `403930ad84a9a3eb50c7be4ce0614dee9e6240ce411b24d7adaf1065e4f8d987`，C13 `34598e99d7fb63fc52966a620426ab2bcf7280d2cbc51093626488f6bd4a560c`。提取物保存在 WSL `[LOCAL_WSL_USER]/c13_audit/rootcause_lp_20260925_2145/extract_{c12,c13}_key_20260925/`。

Normal first-stage `fstab.qcom` 将 system、system_ext、product 配为 logical + EROFS + first-stage mount + slotselect/AVB(`vbmeta_system`)；vendor/odm 为 logical ext4；metadata 为 ext4 first-stage mount；userdata 为 F2FS、latemount、formattable，并启用 file/metadata encryption，metadata key 路径为 `/metadata/vold/metadata_encryption`。实际 C7/C13 `system/etc/init/hw/init.rc` 的 `late-init` 依次触发 `early-fs`、`fs`、`post-fs`、`late-fs`、`post-fs-data`；注释说明 fstab `mount_all --early` 会跳过 `latemount`，随后 `--late` 再挂载这些项，且 vold 在 `early-fs` 启动。因此，若 `fs_mgr_mount_all` Recovery 请求出现在正常 late mount，它可能位于 metadata 已 first-stage 挂载、vold 已启动、`/data` 正在挂载/加密处理的阶段；但 reason 本身没有标明所处 mount_all 阶段，不能断定失败来自 `/data`、metadata 或 vold。

Recovery fstab 对 system、system_ext、product 使用 ext4，而正常 first-stage fstab 对这些逻辑分区使用 EROFS。这是两条启动路径的配置差异；可能解释 Recovery 自身随后出现的挂载/逻辑分区错误，但配置由 C12/C13 共享，且日志错误发生在已经记录 Recovery 分支之后，不能说明最初为何进 Recovery。

## 5. SELinux 验收状态

Candidate 13 两条 allow 规则仍只有主机侧验证。C13 保存的日志显示 Recovery 分支从 monolithic `/sepolicy` 加载；没有 `init: Compiling SELinux policy`，也没有 Candidate 13 的 HAL、`/dev/ion`、AVC、QSEECom 或 vold/data 运行证据。因此本轮**没有有效的 SELinux 真机验收结果**。此前 `secilc -N` 主机编译跳过 neverallow 检查，也不构成独立 neverallow 验证。

C12 的正常启动现场 [console-ramoops](20260925_CANDIDATE12_LOG_SALVAGE/pstore/console-ramoops-0) 在 2.017602 秒出现动态策略编译，并继续记录到约 9.7 秒的 ION AVC；[pmsg](20260925_CANDIDATE12_LOG_SALVAGE/pmsg_clean.txt) 记录 Keymaster/Gatekeeper 相关 QSEECom abort 以及 keystore2 等待 `sys.boot_completed`。这支持 C12 已进入普通 Android 核心服务阶段，同时也说明旧 AVC/QSEECom 错误能够与启动继续并存，不能单独认定为 C13 Recovery 原因。C13 需要在下一次普通启动中分别核验策略加载、Keymaster/Gatekeeper AVC、QSEECom 和 vold/data；不删除现有规则，也不扩大权限。

## 6. 下一次最小诊断实验

### 本轮已准备的主机工具

新增/改进 [只读观察脚本](../../tools/observe_candidate13_readonly.py)：它每秒轮询 ADB/Fastboot 状态；设备进入 ADB 后立即持续采集 `logcat -b all -v monotonic`，异步保存启动属性、`/proc/cmdline`、`/proc/version`、首次 dmesg、getenforce、`/dev/ion` 标签、`/data` mount 和相关 Init 服务 SELinux 进程标签。脚本没有 reboot/boot/flash/erase/format 命令；本轮仅做 AST、帮助文本与静态命令审阅，未运行该观察器。

现有 Standalone 预构建镜像保留，201,326,592 B，SHA-256 `8a5803f09cbcb11056d8356f8d235c3c4450846244fa1b4033abaaacb213e98b`，与 C13 salvage 脚本 pin 的 hash 一致。它是已用过的 pstore/oops/dmesg 采集资产。当前 `build_standalone_diag.py` 源码已演变为 misc 采集用途，不包含旧预构建镜像里的完整 pstore/oops/dmesg 导出流程；下一次如要重建取证镜像，必须先恢复并核验这些采集能力。此次无需重建，避免替换已知可用镜像。

### 获得后续授权后按此顺序

1. 设备保持 PixelOS A0′，先确认健康基线与 ADB/Fastboot 状态；核对 C13 六镜像 hash。由于当前设备运行 PixelOS，要复现 C13 必须重新刷回同一 Candidate 13 的六个目标：`vbmeta_a`、`vbmeta_system_a`、`boot_a`、`vendor_boot_a`、`dtbo_a`、`super`。本报告不授权刷写。
2. 刷写成功后停在 Fastboot；单独取得首次启动授权。先启动主机只读观察脚本，再由用户准备观察手机并授权首次启动。保持设备可见；记录 Logo、黑屏、Recovery 屏幕的照片/视频和精确文字。Recovery 出现数据清除确认时不操作确认键、不选择 Factory Reset。
3. 若 ADB 曾上线，停止前先保存全部 logcat、时间线和快照，按启动顺序找出首条 Init/fstab/AVB/SELinux/vold/Keymaster 错误。检查动态策略是否编译并加载、ION 标签与 AVC、QSEECom、HAL 服务状态、metadata 与 userdata 挂载、bootreason/boot mode。
4. 若设备落入 Recovery，先让其画面停留以观察是否有可用的 Recovery ADB/USB 状态，不确认 wipe。随后按用户操作回到 Fastboot；只有获得单独的 Standalone RAM 启动授权后，再使用已核验诊断镜像采集 pstore、pmsg（若存在）、oops.raw、dmesg 和主机 USB/Fastboot 时间线。取证完成前不得运行自动 PixelOS 恢复流程。
5. 若仍只有 Recovery pstore 且没有 ADB，需承认未取得首次普通启动的直接日志。下一轮再评估外部 UART/早期 console 采集或经单独审查的临时诊断启动镜像；当前没有已验证的 pre-ADB 主机读取通道，不为此改 Candidate 13 内核、SELinux 模式或加密路径。
6. 失败现场证据保存和核对完成后，再单独授权 PixelOS A0′ 恢复及正常启动验证。恢复前不擦 userdata/metadata、不改 misc/BCB、不回锁 Bootloader。

该方案能增加 ADB 可达时首条真实启动错误被保存的概率，并降低恢复前证据丢失风险；若失败发生在 ADB 可用以前，仍不能保证捕获第一内核/init 现场。若要绝对覆盖该窗口，需要可用 UART 或改变早期启动采集设计，尚未证明本机现有条件支持。

## 7. 当前设备与工程判断

2026-09-25 最新只读复查：ADB `[REDACTED_DEVICE_ID]` 在线，`ro.product.device=thyme`、槽位 `_a`、`sys.boot_completed=1`、Android 17 / SDK 37、内核 `4.19.325-perf-g45b9b954f074`；vold running，FBE `encrypted/file`，`/data` 是 `/dev/block/dm-46` 上可写 F2FS；Verified Boot `green`、verity `enforcing`。Fastboot 设备列表为空，未发现 fastboot 写入进程。PixelOS A0′ 当前保持健康在线。

工程判断：

1. **最有证据支持的事件链：**普通 Init 的 `mount_all` 可能请求 `fs_mgr_mount_all` Recovery → Recovery 启动 → 首次完整取证只留下 Recovery 实例。此链对首个箭头是强推断，后续 Recovery 事实已直接证明。
2. **普通启动是否发生过：**有强间接线索（参数与已提取 C13 Init 的定制字符串匹配），但没有直接保存的普通 kernel/init 日志。
3. **`fs_mgr_mount_all` 与 Recovery：**`reason` 强烈指向该请求类别，不给出具体失败 fstab 项或错误码；Recovery 写 BCB 是入 Recovery 后的动作，不证明 pre-boot BCB 已存在相同命令。
4. **镜像差异：**已核验差异不足以解释首次选择 Recovery。没有明确主机可修复镜像故障。
5. **SELinux：**C13 现场没有进入动态 system_ext 策略加载证据窗口，故无效验收。
6. **下一次日志保护：**开机前运行只读观察器并保留屏幕/ADB；失败后先 Fastboot 再经授权 RAM 取证，最后才恢复 PixelOS。
7. **重建需求：**不重建 C13，不改变其启动条件；仅准备诊断采集流程。
8. **需另行授权的设备动作：**六分区 C13 重刷；Candidate 13 首次启动；失败后的 Standalone `fastboot boot` RAM 取证；取证后的 PixelOS 六分区恢复；PixelOS 恢复后的正常启动。每项仍沿用既有安全边界，Recovery wipe 不确认。
9. **PixelOS：**当前 ADB 健康在线，Android 已完成启动，加密 userdata 可写挂载。

## 参考资料

- [AOSP Init first-stage Recovery 判定与挂载](https://android.googlesource.com/platform/system/core/%2B/6ad4d0a601485475645ddd1b23181a4c31754977/init/first_stage_mount.cpp)
- [AOSP Init `mount_all`/Recovery 分支参考](https://android.googlesource.com/platform/system/core/%2B/android16-qpr2-release/init/builtins.cpp)
- [AOSP fs_mgr 可格式化分区与 NEEDS_RECOVERY 路径](https://android.googlesource.com/platform/system/core/%2B/main/fs_mgr/fs_mgr.cpp)
- [AOSP Recovery 参数、提示与 BCB 处理](https://android.googlesource.com/platform/bootable/recovery/%2B/master/recovery.cpp)
- [AOSP PID 1 fatal reboot/panic 处理](https://android.googlesource.com/platform/system/core/%2B/master/init/reboot_utils.cpp)
- [Linux ramoops 持久缓冲区说明](https://docs.kernel.org/admin-guide/ramoops.html)
