# THYME-OS4：Milo HyperOS4 与 C30 四方启动链定点差异

日期：2026-09-30  
范围：第三方 Milo system、实际 C30 system、Xiaomi 15 donor system、Redmi K40 Android 17 成功 system。仅主机离线检查；没有启动第三方文件、操作手机、启动 C30、构建 C31 或改动 Candidate。

## 结论

没有发现 Milo 相对 C30、donor 或 K40 增加了可解释当前 C30 PID 1/Zygote 启动故障的 Android 17 + Linux 4.19 兼容补丁。没有足够证据把 Milo 的差异移植进 C31；本轮建议的 C31 修复集合为 **0 项**。

最直接的反证是：Milo 的 `netd.rc`、`netbpfload.rc`、Zygote rc 与 Xiaomi 15/K40 对应版本保持一致。Milo 仍保留 netd 重启两套 Zygote 的回调，也仍使用 Android 17 BPF loader；而 C30 分别已经删除 netd 的两条 Zygote 回调，并保留经实机验证有效的 BPF 绕过。把 Milo 的这两份 rc 移回 C30 会撤销已做的启动适配。

## 取证范围与限制

- 复用项目已有的 C30 实际构建树、Xiaomi 15 system EROFS、K40 `system_a` 和此前的 Milo system 定点缓存；没有解包四套完整 super。
- Milo `super.img` 是 sparse。为让现有 LP 工具只提取 `system_a`，生成了一个本地临时 unsparse 文件，再提取 system_a；输入包未修改。目标 EROFS 通过 `fsck.erofs -p`。未提取其他逻辑分区。
- 比较了 87 个 `/system/etc/init` 与 `/system/etc/init/hw` 路径、指定 runtime/APEX/classpath/VINTF/linker 文件，以及限定启动相关主体/目标的 `plat_sepolicy.cil` 规则。
- SELinux 比较是限定规则的字面 CIL 比较，不等同于四套完整 merged/vendor policy 语义审计。
- Milo system 树中的两个 BoringSSL reparse/symlink 项无法由 Windows 缓存直接读取；未把它们当作普通文件作内容结论。runtime manifest 中的 `libnativeloader.so` / `libnativehelper.so` 直接路径也未能可靠解析，故不据此作逐文件结论；ART/runtime APEX 本体哈希在四方相同。
- 本报告只依据可读取的 system 配置、文件哈希、ELF 依赖摘要及包审计已有事实。不同 build 的 jar/apk 字节差异不自动等同于兼容修复。

## 四方定点结果

| 启动链项目 | Milo | C30 | Xiaomi 15 donor | K40 成功包 | 判断 |
|---|---|---|---|---|---|
| `init.zygote64.rc`、`init.zygote64_32.rc` | 与其余三方逐字节相同 | 相同 | 相同 | 相同 | 未发现 critical、critical window、zygote-fatal、classpath 或 secondary callback 差异 |
| `netd.rc` | hash `51039198…`，含 `onrestart restart zygote` 和 `zygote_secondary` | hash `CE706B53…`，删除上述两条回调 | 与 Milo 相同 | 与 Milo 相同 | C30 是已有定点改动；Milo 没有对应修复 |
| `netbpfload.rc` | hash `14C576D0…`，Android 17 stock BPF loader/wait 路径 | hash `BDA68A4D…`，设置 `bpf.progs_loaded=1` 后启动 netd | 与 Milo 相同 | 与 Milo 相同 | Milo 没有 Linux 4.19 BPF workaround；移回会撤销 C14 修复 |
| `system/etc/init/hw/init.rc` | 与 donor 逐字节相同，hash `4A55170C…` | 增加 C28/C30 诊断导入与 marker | 与 Milo 相同 | hash `92FF466F…`，存在 K40 自己的若干设备/性能配置 | Milo 无 PID 1/recovery 修复；K40 独有内容不构成可直接移植证据 |
| `surfaceflinger.rc` | 与 donor/K40 相同，无 C30 的 ANGLE 属性触发 | 多一个 `ro.persistent_properties.ready=true` 时设置 `persist.graphics.egl angle` 的段 | 与 Milo 相同 | 与 Milo 相同 | 是 C30 保留的既有图形路由实验，不是 Milo 新方案，也无证据与本轮 PID 1 panic 有因果关系 |
| VINTF、linker、启动 classpath | 指定文件哈希与其他三方相同 | 相同 | 相同 | 相同 | 未发现 Android 17 system + Android 13 vendor 专用 namespace/VINTF workaround |
| ART/runtime | `app_process32/64`、两个 classpath 文件、ART/runtime APEX 与其余三方哈希相同 | 相同 | 相同 | 相同 | 运行时核心基线一致 |
| Framework | `services.jar`、`framework-res.apk` 与 C30 不同；`libandroid_runtime.so` 小幅不同 | 与 donor 相同 | 与 C30 对应文件相同 | 多数核心 runtime 相同；`services.jar` 为另一 build | 版本/内容差异存在，但没有发现与当前 PID 1 首因直接对应的行为补丁 |
| 限定 SELinux 规则 | 与 donor 的目标规则集合相同；Milo 相对 C30 无独有规则 | 多 30 条 C30 诊断规则 | Milo 的目标规则集合相同 | Milo 无独有目标规则；K40 多两条 shell/system_prop 规则 | 未发现 Milo 对 init/netd/Zygote/system_server/metadata/logd 的启动兼容规则 |

完整小型清单见同目录 `init_tree_fourway_manifest.csv`、`runtime_vintf_linker_fourway_manifest.csv`、`milo_system_selected_manifest.csv` 和 `selinux_scoped_fourway.txt`。

## 版本与来源关系

- Milo system：`ro.build.id=CP2A.260605.016`、SDK 37；incremental `17OS4.0.260923.154254873.QCPECN.S`，安全补丁 2026-09-01，system device/fingerprint 使用 generic `missi`。product 元数据标识 thyme / HyperOS 4.0.0.44（TGACNXM）。
- C30 与 Xiaomi 15 donor system：同一 CP2A build ID / SDK，incremental 为 2026-09-02 构建，C30 product 是 thyme / 4.0.0.8。指定 system 初始化树、ART/runtime APEX、classpath、linker、VINTF 文件与 donor 对应。
- K40 成功包的 system 也基于同一 2026-09-02 system build；它的 product/vendor 设备内容另有适配。被比较的 runtime 初始化文件多与 donor 完全相同。
- 因 Milo 的 system build 较 donor 更新且元数据仍是 generic `missi`，可确认它与 donor 属于相同 Android 17/HyperOS 系列基线，但仅凭元数据和有限文件哈希不能证明它是某个确切 Xiaomi 15 donor 镜像的直接重打包。
- 结合此前包体审计：Milo product 指向 thyme 4.0.0.44；vendor 是 thyme Android 13 线，boot/kernel 来自 10S 4.19.157 线。没有证据表明它采用 K40 的 boot/vendor 栈或内核补丁。

## 重点问题判断

### init、Zygote、netd 与 critical

Milo 没有修改 Zygote 的 `critical window` 或 `target=zygote-fatal`，没有关闭 critical，也没有 `init.svc_debug.no_fatal.zygote` 一类抑制配置。它的 Zygote rc 和 C30、donor、K40 相同。Milo 的 netd 仍会在 restart 时请求重启 primary/secondary Zygote；netbpfload 仍走 stock Android 17 的 BPF 规则。未发现 netd Linux 4.19 兼容 property、替代 trigger、BPF skip 或 recovery/PID 1 fatal workaround。

C30 当前与 Milo 在这两份关键 rc 上的差异，是 C30 既有工程修复，不是第三方方案：C30 移除了 netd→Zygote 两条 restart 回调，并对 BPF loader 使用已通过实机验证的 C14 绕过。C30 仍记录 PID 1 触发 sysrq panic，但其上游 init fatal 条件仍未闭环；本次差异不能进一步证明 netd/Zygote 是该 panic 的原因。

### Framework、VINTF、linker、Qualcomm

`app_process32/64`、ART/runtime APEX、boot/system-server classpath、linker config、VINTF manifest 和 compatibility matrix 在四方指定路径上逐字节一致。`libandroid_runtime.so` 的 Milo 文件比其他三方短 64 字节，SONAME 和 106 项动态依赖集合相同，仅 build ID/hash 不同；这不足以说明存在兼容逻辑。Milo 与 C30 的 `services.jar` 不同，class dex 字节有差异，但没有做全量反编译，也没有证据显示差异含 4.19、Zygote critical 或 PID 1 修复。`framework-res.apk` 也有资源差异，不能据此推断启动修复。

限定 SELinux CIL 规则中，Milo 与 Xiaomi 15 donor 目标规则一致；Milo 没有相对 C30 独有的 init、netd、zygote、system_server、metadata 或 logd 授权。C30 多出的相关规则属于 C30 诊断域和 marker。VINTF 与 linker 指定文件均相同，因此没有发现 Milo 专属 Qualcomm HAL namespace/manifest bridge。system/product 中可见的部分 Qualcomm 属性没有找到对应的 Milo 专有启动调用链，不能认作 thyme/4.19 补丁。

## 最多三个候选差异与工程决定

| 候选 | 证据与可能意义 | 决定 |
|---|---|---|
| Milo 较新的 `services.jar` / `framework-res.apk` / `libandroid_runtime.so` 内容 | build 增量更新，文件字节不同；没有定位到与当前 init fatal 或 C30 静态 Logo 的具体修复行为 | **暂不移植**。只有后续日志明确落在对应 Framework/UI 路径时，才对 dex/资源做定点差分 |
| C30 `surfaceflinger.rc` 的 ANGLE 属性触发段 | Milo/donor/K40 没有；这是 C30 既有图形实验配置，非 Milo 的修复；与当前已观察的 PID 1 panic 没有因果证据 | **不因本次对照改动** |
| Milo system build 比 C30/donor 更新 | 证明版本不同，不能证明更新带来针对 thyme 4.19 的兼容修复；runtime 初始化核心仍相同 | **不作为 C31 方案** |

因此本轮**没有形成值得进入 C31 的 Milo 移植项**。维持 C30 当前镜像与配置，不启动、不刷写；下一步仍应基于 C30 Unified First-Response 证据，闭环 PID 1 fatal 的上游触发条件。不要将 Milo 的 stock `netd.rc`/`netbpfload.rc` 覆盖回 C30。

## 第三方包判定

Milo 仍不是可直接实机刷写的 External Candidate。用户转述作者承认旧分区映射忽略 10S A/B，但尚未提供修订包和逐项写入映射。本报告不重审 BAT；前次审计已确认原包写入范围及 package 来源不一致。即使本次 system 树比较未发现启动 workaround，也不能用它替代完整的分区/AVB/LP/恢复路径审核。

本轮未运行 EXE、BAT、APK，未向设备发送命令；未刷写、启动、擦除、set_active 或修改 C30。未构建 C31。
