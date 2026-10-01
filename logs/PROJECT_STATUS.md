# THYME-OS4 项目当前状态

更新时间：2026-10-01 11:07 HKT

## 项目目标与阶段
将 Xiaomi 15（dada）HyperOS 4 / Android 17 移植到 Xiaomi 10S（thyme）。当前主线是依据 C30 真实启动证据定位 PID 1 panic 的上游触发条件；第三方 Milo 包已完成离线评估，不作为当前 Candidate。

## 当前 Candidate 与设备状态
- C30 的 super 与 vbmeta_system_a 已刷入 A 槽并启动过一次；用户观察到静止 Xiaomi 第一屏，ADB 未上线。
- C30 console-ramoops 在 32.921975 秒记录 PID 1 init 经 write_sysrq_trigger 主动触发 kernel panic。新补充的 C30 pmsg 时间线有五个 `main` SIGABRT（估计 uptime 16.095、18.014、22.855、27.842、32.879 秒）；最后一次约早于 panic 43 ms。primary `zygote` 配置为 `critical window=10 target=zygote-fatal`，所以“Zygote critical escalation → PID1 panic”成为最强候选，但 `main` PID 未映射到 init zygote service，且没有 critical fatal 原文/abort backtrace，仍未证实。
- C30 的七条 vendor-property AVC 与首个 `main` SIGABRT 时间相邻，但 exact property key/PID/consumer 缺失；三条 `vendor_default_prop` AVC 在首个 SIGABRT 后约 77 ms。不得据此增加 SELinux allow。UltraFramework class-load exception 有共同 K40 fallback，不是已证实 fatal 根因。
- netd 的 Android 25Q2 / Linux 4.19 SIGABRT 是已确认独立服务故障。C26 中 netd `onrestart` 杀两套 Zygote 的直接链有记录；该两条回调已在 C27/C30 删除。C30 primary Zygote→netd 与 secondary→primary 回调仍在，可能构成反向/旁路连锁；C28–C30 marker 无序，当前不能判定 netd 与 Zygote 的首因顺序。
- 定点检查确认 C30 与 K40 成功样本的 `framework.jar`、`preloaded-classes` 字节完全相同；`UltraFrameworkComponentFactoryImpl` 加载异常由共同代码捕获并回退到基础工厂，C30 pmsg 随后仍记录了初始化继续。该缺类不再视为已证实 Zygote fatal 根因。K40 system_ext 对应路径未找到 `ultra-framework.jar`；没有扫描所有其他容器，不能断言全部分区均无此 class。
- K40 policy 允许 Zygote 读取四种相关 AVC type，但 C30 AVC 没有 exact key/PID，尚不能把权限差异连接到 SIGABRT。C30 的 `ro.hardware.fp` context 与 K40/donor 的 `ro.hardware.fp.` schema 不同；已定位的 `ro.hardware.fp.fod` getter 默认 `false`，不足以解释启动 fatal。C31 change set 为空；不构建 C31、不增加 SELinux allow。
- C30 pmsg 证明 /data、fscrypt 与 keystore2 初始化推进；netd 多次 SIGABRT。诊断 helper 的 canary/events/logcat 未留下有效内容，不能据此断定 system_server/Zygote 状态。
- 最近一次只读设备查询（2026-09-30 13:09 HKT）：Bootloader Fastboot；product=thyme，A 槽，unlocked=yes，is-userspace=no；A no/no/retry=3，B no/no/retry=7。此次第三方离线审计没有查询或操作手机；状态未被本轮改变。
- C30 本地镜像与 Unified First-Response Standalone 取证资产保持不变。没有再次启动 C30、刷写、set_active、清除数据或恢复 PixelOS。
- 本轮未查询手机；以上仍是最近只读状态记录，不代表当前实时状态。

## 第三方 Milo HyperOS4 旧包离线审计（4.0.0.44，历史）
- 本地目录：10S系统/小米10s-MiloHyperOS-4.0.0.44TGNCNXM。49 个文件，总计 7,602,127,591 B（约 7.08 GiB）。
- 类型：自定义 Windows Fastboot 包与面向 muyu 的 Recovery updater/不一致 OTA metadata 混合；不能认定为可靠 thyme 发布包。
- BAT 会 erase frp、刷 super 与多项底层/启动分区（含 modem）、对 vbmeta A/B 写入、set_active a、自动 reboot；菜单选项 2 会 erase userdata/metadata。Recovery updater 直接写很多 _a/_b 节点，且引用六种包内缺失固件源。
- boot/vendor_boot/dtbo/vbmeta/vbmeta_system 与本地 10S Android 13 官方基线逐字节相同；低层固件与 10S stock lineage 相符。super 的 LP 结构与 C30 不同，vbmeta 是 Android 13 基线，不能直接视为 C30 兼容产物。
- system/system_ext 指向 generic missi Android 17 build；product 指向 thyme；vendor 指向 thyme Android 13。仅凭元数据无法证明精确供体为 dada。
- netd.rc 保留 netd→primary/secondary Zygote restart；netbpfload 和 libnetd_updatable 与 C30/K40 对应二进制相同。未发现解决 C30 当前 PID 1/Zygote 问题的新增兼容修复。
- 用户转述作者承认此前分区映射有误，因为忽略 10S 的 A/B 分区。未收到修订包/准确映射。项目本地 10S 官方 fastboot 脚本也使用 boot_ab/vendor_boot_ab 等目标名，因此具体错项尚不能从这句话独立确定；当前包仍因写入范围、Recovery 来源、LP/AVB 不一致而不适合作为实机 Candidate。
- External Candidate：不通过。本轮未生成 staging/Dry-Run，第三方 exe/bat/apk 均未运行，未向手机发送命令。
- 报告与清单：work/reports/third_party_milo_hyperos4_audit_20260930/THIRD_PARTY_PORT_STRATEGY.md 及同目录 CSV/diff。

### Milo system 与 C30 四方启动链定点比较（2026-09-30）
- 已对 Milo system、实际 C30 system、Xiaomi 15 donor system、K40 Android 17 成功 system 做限定文件比较；未解包完整 super、未操作设备、未启动 C30、未构建 C31。
- Milo 的 `init.zygote64*.rc`、`app_process32/64`、ART/runtime APEX、boot/system-server classpath、linker config、VINTF manifest/matrix 与其他三方指定文件逐字节相同。限定启动主体/目标的 SELinux 规则中，Milo 与 donor 相同、Milo 没有 C30 未有的专属启动规则；C30 多出的规则是 C30 诊断授权。
- Milo `netd.rc` 保留 netd 重启 primary/secondary Zygote 的回调，`netbpfload.rc` 仍使用 Android 17 stock BPF 路径；两者与 donor/K40 相同。C30 已分别有自己的回调删除和经实机验证有效的 BPF 绕过。不要把 Milo 这两份 rc 覆盖回 C30。
- Milo system 是较新的 generic `missi` Android 17 build（CP2A.260605.016、2026-09-23 增量）；product 标识 thyme / HyperOS 4.0.0.44。与 2026-09-02 Xiaomi 15/K40 system 属于相同系列基线，但不是逐字节相同，精确供体来源不能仅凭现有元数据确认。Milo `services.jar`、`framework-res.apk`、`libandroid_runtime.so` 有版本字节差异，未找到与当前 PID 1 fatal 有关的具体兼容逻辑。
- C30 `surfaceflinger.rc` 中保留 ANGLE 属性触发段，Milo/donor/K40 没有；这是 C30 既有实验配置，不是 Milo 提供的修复，也没有证据解释 C30 的 PID 1 panic。
- 本轮未发现值得移植到 C31 的 Milo 启动修复，C31 候选为 0 项。报告与小型证据清单位于 `work/reports/third_party_milo_c30_startup_diff_20260930/`；公开增量另记执行记录及下方提交信息。
- 与 C30 当前阻塞交叉后，K40/Milo 唯一共同但 C30 未采用的配置状态是 Tango/pretrans 七项属性未启用；consumer 和启动因果未确认，不进入 C31。K40 自有 init 差异（可选 TCP ADB、Baiyang dexopt、主题/后期控制）不解释早期 fatal。
- C30 七条 AVC 的目标类型与时间已完成定点闭环；其与 main SIGABRT 时间紧邻，但 key、PID、调用点及因果仍未知。最新 Milo 4.0.11.0 vendor policy 已按下节核查，不再沿用“完整 K40 policy 缓存缺失”的旧状态。
- 当时的交叉报告保留在 `work/reports/k40_milo_c30_author_change_sets_20260930/AUTHOR_CHANGE_SET_AND_BLOCKER_CROSSCHECK.md`；property context 与 K40/Milo vendor policy 的后续定点结果见本状态末尾 2026-10-01 条目。

## DSU 侧载路线评估（2026-10-01，静态）

- PixelOS Android 17/SDK 37 的本地 system 镜像内存在 DynamicSystemInstallationService、gsid、gsi_tool、gsid.rc；kernel IKCONFIG 包含 DM_VERITY/FEC。first-stage fstab 对 system、system_ext、product、vendor、odm 声明 ext4 logical first-stage mount；metadata ext4 16 MiB first-stage mount；userdata F2FS。静态条件较强，但 feature flag、GSID 注册、AVB key lookup、Gatekeeper 大 USER_ID、/data 可用空间和 PixelOS 精确 init transform 均未在设备端验证。
- DSU 上游支持多分区 GSI，不限 system_gsi；单镜像 DynamicSystemClient 只覆盖 system。多分区 DSU 可考虑 system + system_ext + product。首轮应保留 thyme vendor/odm/boot/vendor_boot/dtbo/kernel。
- C30 system_c30.img 是 EROFS，且 AVB footer Algorithm NONE、依赖父 vbmeta；不能原样作为 DSU image。重建、受信任签名和 AVB descriptor 是先决条件。PixelOS host descriptor 与 C30 build.prop 显示 SPL 2026-08-01；AOSP 要求 guest AVB patch level 更新，C30 descriptor 仍需单独读回，不能假定通过或伪造。
- DSU 值得作为 ADB 取证侧线；当前不是可立即安装/启动 C30 的状态。详细矩阵、阻塞与退出预案：work/reports/dsu_feasibility_20261001/DSU_TESTABILITY_MATRIX.md。
- 本轮没有查询或操作手机；最近历史 A retry=3 不是实时状态。C/D/E 此次可用约 92.44/196.64/170.76 GiB，均高于 50 GiB，无空间清理；Docker 未触碰。
## 安全、磁盘与公开仓库
- Bootloader 保持解锁；禁止回锁及擅自修改 persist 硬件分区、modemst、EFS/NV、射频校准或设备身份资料。
- 清理后三盘复测（2026-09-30 22:12 HKT）：C/D/E 可用约 91.92/198.24/204.08 GiB。已删除三项本轮生成、可重建且不再需要的临时文件，共 10,145,771,198 B（约 9.45 GiB）；原始 Milo super、选定 system 缓存和 K40 system 缓存保留。Docker 未触及。
- 原始 ROM、镜像、设备 raw metadata/misc 及未脱敏硬件身份资料不得公开。第三方包仅公开审计文档、CSV 清单与小型文本差异，不公开其 exe/apk/镜像。

## 下一步
1. C30 主线唯一必要实验方向：若进入下一次设备实验，准备诊断型 Candidate，用 init 原生、pstore 可读的状态记录保存 zygote/zygote_secondary/netd 的状态和 PID，并只对 primary zygote 临时设置 `init.svc_debug.no_fatal.zygote=true`，检验 critical escalation 假说。此候选尚未构建；先核对当前 init 对状态触发、PID 属性、kmsg 写入与 SELinux 的实际支持。不得扩大 vendor-property allow 或同时改 netd/ART/GPU 行为。
2. 本轮设备未查询，C30 不重启、不刷写、不切槽、不清数据、不恢复 PixelOS。最近历史 A retry=3/unbootable=no 不是实时状态；任何设备操作前重新只读核对。新的 Candidate 正式启动前仍需用户在场确认。
3. DSU 维持侧线；不转换 C30，不做 DSU 实机实验，除非另行进入该路线并完成宿主运行时只读核对。
4. 若作者提供修订 Milo 包及逐项 A/B 分区映射，对新版本单独静态复核。

## 最新公开同步
- 本轮四方启动链报告与 4 份小型文本清单已推送到公开 main，Commit `f9b22d363d6334348b40ac539d4b96fb5c939f0e`。报告匿名 raw URL、init manifest 和 runtime manifest 均 HTTP 200；本地公开仓库干净，新增报告目录合计 52,778 B，不含镜像或程序。
- 公开路径：`reports/third_party_milo_c30_startup_diff_20260930/`。此前基础 Milo 包审计仍在 `reports/third_party_milo_hyperos4_audit_20260930/`，其首发提交 `9e7ff9dc3cb7b1648a849de0290f38080692cba0`。
- 本轮 K40/Milo/C30 交叉分析、矩阵、BoringSSL symlink 表、索引及脱敏状态/执行记录已推送至公开仓库 `main`，Commit `28b60e522dcf66d2ed4f5a8da351421044163371`。报告、两份 CSV、索引、状态和执行记录匿名 raw 均 HTTP 200；远端 main 与本地 HEAD 一致，工作树干净。未发布 ROM、镜像、设备 raw 备份或二进制。

### C30 AVC 与 UltraFramework/K40 因果闭环（2026-10-01）
- C30 七条 AVC 涉及五种 target type，其中 vendor_default_prop 重复三次。AVC 的 `name=` 是 property-area context；实际 key、PID、consumer 均未记录。property-context 只能给出显式 key/开放前缀候选，82 条 DEX 字面量也没有与事件闭环。
- C30 与 K40 成功样本的 `framework.jar` 完全相同：51,385,773 B，SHA-256 `4F24636042ED6661E62660F0724F5C3A22B7E5F2FE73750593F2DCFC77FBA613`；`preloaded-classes` 完全相同，SHA-256 `F99F598C4120F07869F5CF013BE9972A0903F87F21FC10DF3CA6789E812CAC79`。共同工厂代码捕获 Impl 加载异常并回退基础工厂；C30 PID 1051 在 ClassNotFound 后仍记录 `ThirdAppOptImpl has been initialized !`。缺类不再视为直接 Zygote fatal 的有力解释。未扫描所有 JAR/APK/APEX，故不声称全镜像绝无 Impl。
- K40 vendor CIL 明确允许 Zygote 读取四种非 fingerprint AVC type，并有 open/getattr/map；但没有 exact AVC key、PID 和 SIGABRT backtrace，无法证明这些规则解决了 C30 当前 fatal。C30 的 `ro.hardware.fp.`→`vendor_fingerprint_prop` 与 K40/donor 的 `ro.hardware.fp.`→`vendor_fp_prop` 是真实 schema 差异候选；`ro.hardware.fp.fod` getter 默认 false，但不能认定它就是 AVC #43 的 key。
- 决策：七条 AVC 仍为强时间相关、因果未闭合；PID1 约 32.922 秒 sysrq panic 的上游原因未知。`C31_SYSTEM_CHANGE_SET.csv` 无候选行；不构建 C31、不增加 SELinux allow。
- 本轮仅分析，设备未查询或操作。A retry=3/unbootable=no 仍是最近历史记录，不是实时状态；C/D/E 最近实测均高于 50 GiB，未清理，Docker 未触及。
- 新增报告 `work/reports/c30_ultraframework_closure_20261001/C30_ULTRAFRAMEWORK_K40_CAUSAL_CLOSURE.md`、原始 AVC 表和空 C31 change-set；待取得 property key/PID/调用点与可用 Zygote backtrace，再决定是否存在启动修复。
- 报告与 CSV 已公开同步；远端 main 与本地同步时 HEAD 一致，报告、两份 CSV、项目状态、执行记录及 reports 索引的匿名读取均返回 HTTP 200。公开发布内容仅为文本/CSV。
