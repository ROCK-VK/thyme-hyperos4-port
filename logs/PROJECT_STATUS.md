# 小米 10S（thyme）HyperOS 4 / Android 17 移植项目当前状态

## 当前阶段

- 最新设备快照（2026-09-26 00:39）：PixelOS A0′ 六项恢复镜像已经按顺序写入；只读 Fastboot 查询返回唯一设备 `[REDACTED_DEVICE_ID]`、`product=thyme`、`current-slot=a`、`unlocked=yes`、`is-userspace=no`，ADB 未枚举。未启动，因此 PixelOS 当前健康状态尚未验证。

- 当前里程碑：原版 C13 六目标刷写、经授权的 `userdata`/`metadata` 擦除和一次首次启动均已完成。用户看到 Logo/黑屏循环两次并手动进入 Fastboot。随后 Standalone RAM 取证取得 C13 的单个可见启动记录：first-stage mount、动态 SELinux policy compile、enforcing second stage、APEX bootstrap 均有进展；日志止于启动约 3.75 秒，未覆盖 vold、HAL 或 `/data` 后续阶段。C13 尚未达到 ADB、启动动画或桌面可验证状态。
- 项目目标：以 Xiaomi 15（dada）HyperOS 4 / Android 17 用户空间为供体，适配小米 10S（thyme）原生硬件，尽快推进至正常 Android 启动、启动动画或设置界面。用户表示没有需保留的个人数据；任何 userdata/metadata 清除仍须单独明确授权。禁止修改 persist、无线电校准、EFS/NV、设备身份数据或回锁 Bootloader。
- 当前下一步：PixelOS A0′ 六项恢复镜像已于 2026-09-26 00:39 重刷完成，设备保持 Bootloader Fastboot。当前没有启动验证；需单独授权后才可启动 PixelOS。Candidate 13.1 未使用，本轮没有重建镜像。

## 当前有效技术状态

- A5 自编译内核仍是既有启动与诊断基础；没有重新编译或替换。
- Candidate 9 Property Contexts 去重修复已由历史现场证明解决 `persist.radio.imei` Duplicate Prefix；不得恢复旧冲突。
- Candidate 11 的 system_ext EROFS UID/GID、mode 与 SELinux xattr 修复仍保留；`/system_ext/apex` 需要 root:root、0755 与 xattr。
- Candidate 10-WarmDtb 的 `qcom,force-warm-reboot` 与 Standalone Diag 取证链仍保留；温复位不保证每类故障都留下完整 pstore。
- Candidate 12 实机证明 `/dev/ion` 运行时标签为 `ion_device:s0`，泛型 `device:s0` 拒绝归零；Keymaster/Gatekeeper 对 `ion_device` 的访问拒绝和 `QSEECom_start_app failed` 当时仍存在。
- Candidate 13 在 `system_ext_sepolicy.cil` 增加 `hal_keymaster`、`hal_gatekeeper` 对 `ion_device:chr_file` 的权限。旧数据状态下的保存实例进入 Recovery；2026-09-26 清数据首启的新 pstore 证明 C13 已进入正常 first-stage/second-stage，检测到 precompiled hash 不匹配后编译 SELinux policy 并在 enforcing 下继续。该日志未覆盖 Keymaster/Gatekeeper 启动，故两条规则的具体 HAL AVC 效果仍未验证。

## Candidate 13 本轮刷写结果

- 2026-09-26 00:12 按授权刷写原版 `vbmeta_a`、`vbmeta_system_a`、`boot_a`、`vendor_boot_a`、`dtbo_a`、`super`，全部成功；`super` 10/10 sparse 段成功，Fastboot 提示 `skip copying super image avb footer due to sparse image` 但命令退出成功。随后只执行一次 `fastboot erase userdata` 和一次 `fastboot erase metadata`，两项均返回 `OKAY`，未运行 `format`。没有回锁或写入其他分区。
- 用户随后授权一次 C13 首启，之后取得 pstore；实际启动阶段见“Candidate 13 清数据对照首启”。Candidate 13.1/14 均未刷写，未重建镜像。

## Candidate 13 首次启动现场

- 用户观察：启动后小米 Logo 约 10 秒，随后黑屏闪烁；用户手动进入 Fastboot。用户补充当时短暂看到像 PixelOS Recovery 的界面及几行未读文字。随后按取证流程以 `fastboot boot` 从 RAM 启动 Standalone Diag，没有刷写分区。该界面品牌/文字未被留存；其时间早于 PixelOS 救援镜像恢复，不能据外观确认运行的是哪套 Recovery。
- Standalone 导出目录：`work/reports/20260925_CANDIDATE13_LOG_SALVAGE/run_20260925_165614/`；导出 `diag_status.log`、`dmesg_diag_boot.txt`、`oops.raw`、校验文件和 `pstore/console-ramoops-0`。SHA-256 清单为同目录 `SHA256SUMS.txt`。
- `console-ramoops-0` 为上一轮候选 Android/recovery 启动的 pstore 现场；Standalone 自身的内核日志另存为 `dmesg_diag_boot.txt`（诊断环境命令行含 `androidboot.selinux=permissive`，PID 1 为 BusyBox shell）。不能将 Standalone 日志当作 C13 策略运行结果。
- 已保存的 C13 实例约 2.065 秒记录 `First stage mount skipped (recovery mode)`；之后 AVB 与 `system_ext_a` / `product_a` 逻辑设备错误均发生在 Recovery 分支之后。Recovery 约 3.300 秒收到 `--prompt_and_wipe_data --reason=fs_mgr_mount_all`，随后记录 `Writing BCB boot-recovery recovery`；无实际 userdata/metadata 擦除记录。实际 C13 `/system/bin/init` 与构建输入 SHA-256 相同，含有带 prompt 的 `fs_mgr_mount_all` Recovery 字符串，故前序普通 Init `mount_all` 请求 Recovery 是最有力推断，但并非被保存的首次普通启动日志；启动前 BCB 与具体失败 fstab 项未知。
- C13 现场的 init 从 monolithic `/sepolicy` 加载策略；该启动进入 recovery 且逻辑分区未挂载，因此没有验证 Candidate 13 计划中的动态 SELinux 策略路径或两条 HAL 规则。现场未出现 `/dev/ion`、Keymaster/Gatekeeper、QSEECom、vold 或 userdata 解密结果；相关验收仍未完成。
- 17:04 时 Standalone 卷标 `THYME_DIAG` 曾动态分配为 `F:` 并成功导出，随后 ADB 与 Fastboot 均未枚举；该记录是当时状态。2026-09-26 00:39 已重刷 PixelOS A0′ 六项恢复镜像，设备只读核验仍在 Fastboot。

## Candidate 13 清数据对照首启（2026-09-26）

- 使用原版 C13 六镜像；`userdata`、`metadata` 各执行一次经授权的 `fastboot erase`，均返回 `OKAY`，未运行 `format`。随后用户确认观察并执行一次 `fastboot reboot`，Fastboot 返回 `OKAY`。
- 用户观察到小米 Logo 常亮约 20 多秒，随后黑屏再亮 Logo；该循环重复两次后用户手动进入 Fastboot。没有用户报告看到 Recovery 界面，也没有证据表明设备自行进入 Recovery。
- 只读观察器目录：`work/reports/20260925_CANDIDATE13_STORAGE_SAFETY_AND_FIRST_FAILURE/observations/run_20260926_001542/`。主机在启动命令后立即启动观察器；ADB 一直为 absent，约启动后 16 秒开始识别 Fastboot，至观察器停止（约 53 秒）持续为 Fastboot。`logcat_all_monotonic.txt` 与客户端 stderr 均为 0 字节；因 ADB 未上线，观察器没有读取 pstore。
- 用户手动进入 Fastboot 后只读核验：serial `[REDACTED_DEVICE_ID]`、`product=thyme`、`current-slot=a`、`unlocked=yes`、`is-userspace=no`；ADB 未枚举。未对设备再发启动、写入或擦除命令。
- 新 `console-ramoops-0` 有一个可见 Linux/init 启动实例，含 `init first stage started!`、metadata ext4 mount/fsck 成功、多个逻辑设备文件系统挂载成功、`init: Compiling SELinux policy`、SELinux `enforcing=1`、`init second stage started!`，以及 `apexd-bootstrap` 成功扫描 41 个预装 APEX 并完成 bootstrap。记录末尾约 3.75 秒，未出现明确 panic/fatal/Recovery 标记；不能据此认定之后没有重启，也无法解释用户观察到的两次 Logo/黑屏循环。
- 这是首次实机证据表明原版 C13 清除旧 userdata/metadata 后越过 first-stage 并进入普通 Android second-stage。此前“旧加密状态导致 Recovery”因此得到支持，但仍非最终根因；首启只完成一条被保存的启动记录，不能确定设备总共尝试次数。
- 动态 SELinux 编译及 enforcing second-stage 已获得正向运行时证据；日志没有明确列出两条 allow 的编译输入，也未到 Keymaster/Gatekeeper 启动点，因此 ION AVC、QSEECom、HAL、vold、新 metadata encryption 密钥与 `/data` 挂载仍未验证。
- 取证导出目录：`work/reports/20260925_CANDIDATE13_LOG_SALVAGE/run_20260926_002005/`。`console-ramoops-0` 为 152,259 字节，SHA-256 `B3C1AED57D815DAF14B422623719FE1B6B0A9616D701FD876035926449324311`；完整清单见该目录 `SHA256SUMS.txt`。`oops.raw` 来自持久日志分区且含有较早 Android 记录，不作为本次 C13 启动证据；Standalone 自身 `dmesg_diag_boot.txt` 也不混入 C13 结论。
- 观察器目录 `work/reports/20260925_CANDIDATE13_STORAGE_SAFETY_AND_FIRST_FAILURE/observations/run_20260926_001542/` 中 ADB logcat 文件为空；pstore 实际由随后 Standalone 流程取得。Standalone USB Mass Storage 是取证后的历史状态；之后用户手动回到 Fastboot。

## PixelOS A0' 恢复结果

- 2026-09-25 17:15，按既定失败后恢复流程运行 tools/restore_pixelos_a0_prime.ps1 -ExecuteFlash。救援镜像大小与 SHA-256 校验全部通过，顺序刷写 boot_a、vendor_boot_a、dtbo_a、vbmeta_a、vbmeta_system_a、super；六项均成功，super sparse 1/9 至 9/9 全部成功，Fastboot 总耗时 170.931 秒，脚本退出码 0。
- Fastboot 对 sparse `super` 提示 `skip copying super image avb footer due to sparse image`；写入仍完成并返回成功。该提示不作为系统启动或 AVB 验证结论。
- 2026-09-25 20:37，用户单独授权后，Fastboot 预检确认唯一设备 [REDACTED_DEVICE_ID]、product thyme、current-slot a、unlocked=yes、is-userspace=no；执行一次 fastboot -s [REDACTED_DEVICE_ID] reboot（返回 OKAY），未刷写任何分区。随后 ADB 正常上线且 sys.boot_completed=1，PixelOS A0′ 首次正常启动验证完成。此为清数据对照实验前的历史基线，不代表当前设备仍运行 PixelOS。
- 启动验证只进行一次正常重启和只读属性/挂载查询；当时未修改 BCB/misc、userdata、metadata、persist、无线电/身份分区或 Bootloader 状态。该健康 PixelOS 状态是 C13 清数据实验前的历史基线；2026-09-26 恢复重刷后尚未再启动。

### 最新恢复刷写（2026-09-26）

- 00:36–00:39 按用户要求运行 `tools/restore_pixelos_a0_prime.ps1 -ExecuteFlash`。脚本先验证六项镜像大小和 SHA-256，再确认唯一设备 `[REDACTED_DEVICE_ID]`、`product=thyme`、`current-slot=a`、`unlocked=yes`、`is-userspace=no`。
- `boot_a`、`vendor_boot_a`、`dtbo_a`、`vbmeta_a`、`vbmeta_system_a`、`super` 六项全部成功；`super` sparse 1/9–9/9 完成，写入耗时 175.799 秒，脚本退出码 0。Fastboot 提示跳过 sparse super AVB footer 写入，但整体命令成功。
- 未擦除 userdata/metadata，未修改 misc/BCB、persist、modemst、EFS/NV 或 Bootloader 状态；未自动重启。写后只读状态为 `[REDACTED_DEVICE_ID] fastboot`、thyme、A 槽、unlocked=yes，ADB 未枚举。
- 当前只确认恢复镜像写入完成；PixelOS 尚未启动，因此当前健康状态、加密 `/data` 挂载和 `sys.boot_completed=1` 均待验证。2026-09-25 的启动验证仅代表此前基线。

## Candidate 13 实验资产与验证

- 镜像目录：`work/stage_c_thyme_os4_candidate_13_treble_ion_fix/images/`。
- 刷写前逐文件核对了本次六镜像的大小与 SHA-256；均与交付报告和脚本清单一致。`super.img` 的 LP 元数据核验包含 `system_ext_a`，A 槽逻辑分区完整，B 槽为空。

| 分区 | 镜像 | 字节数 | SHA-256 |
|---|---|---:|---|
| vbmeta_a | `vbmeta.img` | 131,072 | `013335BCA9B312E0BEFF737D30903A9B0A1EF829BA19A7BD5802BF83C04F40E9` |
| vbmeta_system_a | `vbmeta_system.img` | 131,072 | `BF4155CD99F125B8CAD26490FD2F3412EA4389F090CE56F36FAA2BF2A759C633` |
| boot_a | `boot.img` | 201,326,592 | `E5A016056D5C93C7A886980A7C062617EC44DC06A48417D7DD0F4476708A6368` |
| vendor_boot_a | `vendor_boot.img` | 100,663,296 | `02333B82BA936F1BAAB1ECAB744632C70F8FC16688A206C7041EF319F112A137` |
| dtbo_a | `dtbo.img` | 33,554,432 | `50E1AC0EDCBD333778217AA6FE8D972F6FF85ADD0DAE8A015A6642C2172DD886` |
| super | `super.img` | 7,684,274,964 | `8AFEFDDBCA2357D003DEF055418CC08A832B91EA08EDCB40DEECBEBD42FA2252` |

- `system_ext_c13.img` is included inside `super.img`; it is not an additional flash target. Its size is 942,669,824 bytes and SHA-256 is `34598E99D7FB63FC52966A620426AB2BCF7280D2CBC51093626488F6BD4A560C`.
- Re-ran `tools/precheck_candidate13.py`: all four host gates passed. This checks policy compilation with `secilc -N`, `sesearch`, EROFS metadata, AVB descriptor agreement, inherited image hashes, diagnostic assets and live ADB boot completion. It does not establish a real-device Candidate 13 result or an independent neverallow check.
- Final Candidate 13 EROFS contains both allow rules and the `/dev/ion -> ion_device:s0` context. The rules compile to permissions for the actual domains `vendor_hal_keymaster_qti` and `vendor_hal_gatekeeper_qti`.
- 正常 Android 的动态 SELinux 路径已有 2026-09-26 C13 pstore 证据：platform 与 ODM precompiled hash 不匹配后记录 `init: Compiling SELinux policy`，随后 enforcing=1 且 second-stage init 继续。该日志证明策略编译/加载路径推进，但未单独证明每条新增 allow 的运行效果；此前 Recovery 分支仍是 monolithic `/sepolicy`，两次启动证据应分开看。
- 已发现元数据差异：C13 `system_ext_sepolicy_and_mapping.sha256` 沿用 C12 值 `cd8873e789916bce6fe56980b563db332c69a4060190df6dab9b279c3bf11897`；按 C13 CIL 与 202604 mapping 重算为 `2be47f383705212c33b33cea9b56b670ccfbc6989f7d908fdf27e3b15120853e`。这不阻断当前动态编译路径，因为 platform 与 system_ext 预编译 ID 均不匹配；后续若更换 platform/vendor 基线，应同步重算。Candidate 13 本轮未为此重建。
- 交付报告中的 `secilc -N` 编译不能证明独立通过 neverallow 检查；neverallow 独立验证仍未完成。
- Candidate 13 刷写脚本：`tools/flash_candidate13.ps1`。默认只做六镜像大小/SHA 检查并打印单线程写入顺序；必须显式传 `-Execute` 才会尝试设备操作，执行前检查序列号、product、A 槽与 bootloader 解锁状态；脚本不含重启、不触碰 userdata/metadata/persist/无线电分区。
- 用户确认此设备的 Bootloader 历史上一直解锁，且此前多轮 Candidate 与 PixelOS A0' Fastboot 刷写成功。Android 属性 `ro.boot.vbmeta.device_state=locked` 不作为需要解锁或回锁的依据。
- 刷写授权前只读 Android 属性曾返回 `ro.boot.vbmeta.device_state=locked`；按用户澄清，此值不代表 Bootloader 锁定。刷写前真实 Fastboot 预检通过：serial `[REDACTED_DEVICE_ID]`、product `thyme`、current-slot `a`、`unlocked=yes`。未执行任何解锁/回锁操作；任何显式或间接 Bootloader 回锁均永久禁止。
- Candidate 13 Standalone 导出脚本：`tools/salvage_c13_diag.py`。只按 `THYME_DIAG` 卷标动态发现盘符，使用时间戳独立保存日志；会将诊断镜像 `fastboot boot` 入 RAM，不刷分区、不恢复 ROM。2026-09-26 导出目录见“Candidate 13 清数据对照首启”。

## 当前设备状态

- 刷写前 2026-09-26 00:01 ADB 只读确认：serial [REDACTED_DEVICE_ID]、product thyme、A 槽、`sys.boot_completed=1`、ro.crypto.state=`encrypted`、ro.crypto.type=`file`、ro.crypto.metadata.enabled=`true`。`userdata -> /dev/block/sda35`，解密映射 `/data` 为 F2FS；`metadata -> /dev/block/sda18`，`/metadata` 为 ext4。该 PixelOS 状态仅在本轮清除前有效。
- C13 清数据实验刷写前只读确认设备为 `thyme`、A 槽、`unlocked=yes`、`is-userspace=no`；按当时授权刷写 Candidate 13 六项并各擦除 userdata、metadata 一次。最新一次刷写为 PixelOS A0′ 六项恢复镜像，完整结果见下条；未执行 Bootloader 回锁。
- 2026-09-25 的前一次 C13 启动现场中，设备未进入可用 ADB，随后以 Standalone 导出日志；当时的诊断盘符 `F:` 仅为动态枚举结果。2026-09-26 清数据对照首启状态另见上节。
- 刷写前另有 `ro.boot.verifiedbootstate=green`、`ro.boot.vbmeta.device_state=locked`、build ID `CP2A.260605.016`、security patch `2026-08-01`、内核 `4.19.325-perf-g45b9b954f074` 记录；均为刷写前 Android 状态，不代表当前 Candidate 13 运行状态。
- 清数据实验前 PixelOS 的 `ro.build.fingerprint` 曾含 Xiaomi/thyme Android 13 字符串，与 release 17、SDK 37 和 display ID 不一致；此前决定不将此属性差异视为启动阻塞。该值不是当前 C13 属性读数。
- 2026-09-25 前一次 Candidate 13 实验按当时授权写入六项目标并首次启动，之后以 `fastboot boot` 在 RAM 中启动 Standalone Diag，再刷回 PixelOS A0'；该次未清除 userdata/metadata。C13 Recovery 曾记录自身 `Writing BCB`；之后只读 misc 采集发现 BCB 四字段为空，未修改 misc/BCB。2026-09-26 又按新授权重刷原版 C13 并各擦除 userdata/metadata 一次，后续首启结果见上节。
- 真机安全边界：禁止 `fastboot flashing lock`、`fastboot oem lock`、`fastboot flashing lock_critical` 及任何间接回锁；未经单独明确授权不得清除 `userdata` / `metadata`，不得修改 `persist`、`modemst`、EFS/NV、无线电或设备身份分区。刷写授权不包含首次启动授权。

## 主机、救援与诊断资产

- 项目目录没有 `.git`，无可用 Git 工作树状态。
- WSL Ubuntu 2 可用；本次限定分区提取完成后 `/dev/sdd` 约 71 GiB 已用、885 GiB 可用，`/tmp` 7.7 GiB 可用。Candidate 12/13 暂存树、C13 build config、C7 system SAR 输入、EROFS/AVB/LP 工具、`secilc` 与 `sesearch` 均存在。
- 最近一次主机环境记录中 Windows C/D/E 盘可用空间约 75 / 246 / 253 GiB。项目内 ADB/Fastboot 为 37.0.1；本次 PixelOS 恢复写入后只读核验设备处于 Bootloader Fastboot，ADB 未枚举。
- PixelOS A0' 救援目录 `work/restore_pixelos_a0_prime/images/` 的六项镜像大小与 SHA-256 均匹配 `tools/restore_pixelos_a0_prime.ps1` 清单。该 PowerShell 脚本默认仅校验；执行刷写后停留 Fastboot，不自动重启。
- Standalone Diag 镜像 `work/standalone_diag/standalone_diag_boot.img` 为 201,326,592 字节，SHA-256 与 `MANIFEST.txt` 一致。
- `tools/observe_candidate13_readonly.py` 每秒轮询 ADB/Fastboot、在线时实时保存 logcat，并异步采集启动属性、cmdline/version、dmesg、getenforce、ION 标签、`/data` mount 和关键服务 SELinux 进程标签；ADB state 为 `device` 或 `recovery` 时尝试只读导出 pstore。2026-09-26 首启后已运行；ADB 未上线，故无 logcat/pstore。随后通过已核验 Standalone RAM 流程成功单独导出 ramoops。
- 当前 `tools/build_standalone_diag.py` 是 misc 采集版本，不复现已知 Standalone 镜像中的完整 pstore/oops/dmesg 导出流程。后续失败取证应先使用 SHA-256 已验证的现有预构建镜像；若需重建，先恢复并静态核验完整采集逻辑。
- 本轮首个诊断镜像 `work/reports/20260925_MISC_BCB_READONLY/run_20260925_180634/standalone_build_retry1/standalone_diag_boot.img`（SHA-256 `f4aec1318cf109f55998e9731f112223d743c354678c3c4cfd0424d29c65532b`）启动后在 `dd` 前安全停止。最终修正版 `standalone_build_retry3/standalone_diag_boot.img`（201,326,592 字节，SHA-256 `6ff8d23d639bb7216192043740810ecf84e24fda11ad35051d95b446e72faf91`）已在补充授权内通过一次 RAM 启动并成功只读导出 misc；retry2 未上机。
- 旧生成文件 `work/standalone_diag/wsl_build_ramdisk.sh` 仍是历史版本，包含固定清理路径和基线输出路径；本轮未运行。后续仅使用要求全新 `--out-dir` 的构建器，且必须使用独立输出目录。
- `restore_and_verify_pixelos.py`、`auto_restore_pixelos_pipeline.py` 与 `auto_restore_a0_boot.ps1` 会等待 Fastboot 并自动刷写和/或重启；本轮未运行，且未发现对应活动进程或计划任务。取证前不得启动这些自动恢复流程。

## Candidate 13 Recovery 根因调查

- `console-ramoops-0` 只有一个可见内核/init 实例，且该实例从 Recovery 分支开始；这不证明设备总共只启动过一次。该日志前没有保存普通 Android 的挂载、策略编译、vold 或 HAL 错误。
- C13 Recovery 请求包含 `--reason=fs_mgr_mount_all`。实际 C13 system_a 中 `/system/bin/init` SHA-256 `9bb24ead728c13c50a5c734e6b3f951c83c7a81d86e2f973b1a1bd4fa9cab020` 与构建输入一致，并含 `fs_mgr_mount_all ... with prompt` 和两个参数字符串。这强烈支持前序普通 Init `mount_all` 曾要求进入 Recovery，但没有保存直接执行日志；具体失败分区/错误码及初始 BCB 未知。
- AVB hash-size 错误和 system_ext_a/product_a DM 设备不可用发生在 Recovery 分支之后，不能作为选择 Recovery 的原因。Recovery 写入 BCB 也不证明启动前 BCB 已有同样内容。
- C12/C13 `boot`、`vendor_boot`、`dtbo`、顶层 `vbmeta` 逐字节一致；super 的 LP metadata/布局一致，A 槽六个关键逻辑分区提取比对只有 `system_ext_a` 内容不同，且仅策略 CIL 变化；`vbmeta_system` 只更新 system_ext hashtree。未发现足以解释 Recovery 的静态镜像问题。正常 fstab 用 EROFS、Recovery fstab 对逻辑系统分区用 ext4；差异可能影响 Recovery 自身挂载，不解释先前模式选择。
- C13 的 `androidboot.init_fatal_reboot_target=recovery` / `init_fatal_panic=true` 仍是旧数据试验 Recovery 的候选机制，但该旧日志没有 fatal/panic 证据。新清数据试验另有普通 Android 动态策略编译与 second-stage 记录；两条 allow 的 HAL 运行效果仍未验证。
- 旧数据试验的 Recovery 原因仍未最终确认；新对照显示清除 userdata/metadata 后至少有一条启动越过 first-stage、进入 second-stage，支持旧存储状态与此前 Recovery 有关，但不证明唯一根因。不要重复清除数据；分析重心转到本次约 3.75 秒之后的未保存阶段。此前 fs_mgr 风险分析报告保留为历史技术资料。

## Candidate 13 存储安全与 C13.1 状态

- C13 `/metadata` 与 `/data` 均带 `check,formattable` 及元数据加密相关选项。K40 成功包采用同类 `check,formattable,wrappedkey` 和 metadata-encryption 配置，因此这些标记本身不是当前唯一根因证据。
- K40 first-stage fstab 对 system/system_ext/product/vendor/odm 逻辑分区声明 ext4 与 EROFS 两套行，并保留 MIEXT bind/overlay；C13 已有 MIEXT 合同，但 system/system_ext/product 只声明 EROFS（与 C13 实际逻辑镜像类型一致），vendor/odm 声明 ext4。K40 的双文件系统回退是可参考差异，当前没有证据证明它导致 C13 Recovery，故本轮不改 fstab。
- K40 包的“一键线刷”明确建议首次选择“双包”；该路径会清除 `userdata` 与 `metadata`，并同时刷入 K40 两槽启动/底层固件、super，设置 A 槽并重启。只把清除数据作为成功安装流程的可参考变量；不运行或照搬其 K40 专属脚本、引导镜像或底层分区操作。
- 清数据后的初始化已有部分实机记录：metadata ext4 在 first-stage 成功挂载，随后 e2fsck 报 clean（281/4096 files）；多个逻辑设备文件系统挂载有成功记录。现有日志未覆盖 `/data` late-mount、vold 或 metadata-encryption 完成情况；精确格式化/新密钥初始化路径仍未验证。
- 2026-09-25 前一次 C13 实验保留 PixelOS 原有 `userdata`/`metadata`，Recovery 保存了 `--prompt_and_wipe_data --reason=fs_mgr_mount_all`。2026-09-26 已完成获授权的原版 C13 清数据对照；C13.1 仍未上机，不重复清除 userdata/metadata。
- 原版 Candidate 13 六镜像保持不变，没有为本轮重建 super。当前已获得 C13 正常 second-stage 的有限现场；若下一步继续 C13，先决定如何获取 3.75 秒以后的日志，不做全量历史哈希审计或无关重建。
- C13 六镜像来源为 `work/stage_c_thyme_os4_candidate_13_treble_ion_fix/images/`；复用已构建资产，未重建 super/C13.1。实际操作使用对应镜像及既有分区顺序；K40 脚本未运行。本次未执行历史全量镜像哈希审计。

## 下一步

1. 当前设备为 PixelOS A0′ 六项恢复镜像已写回后的 Bootloader Fastboot；未自动重启。PixelOS 本次恢复后的正常启动尚未验证，首次启动需另行授权。
2. 本轮用户要求在恢复后创建独立公开 GitHub 仓库；公开仓库内容应只来自显式筛选的文本资料、脚本、补丁和报告，不包括完整 ROM、镜像、分区备份或密钥数据。
3. 后续 C13 技术工作围绕 3.75 秒后未记录阶段与 Logo/黑屏循环获取真实错误；Keymaster/Gatekeeper/ION/QSEECom、vold、`/data`、启动动画或桌面仍未验证。不要重复清除数据。
