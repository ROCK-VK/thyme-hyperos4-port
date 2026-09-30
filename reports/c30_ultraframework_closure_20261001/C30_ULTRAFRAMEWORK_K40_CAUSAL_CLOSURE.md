# C30 Zygote AVC、UltraFrameworkComponentFactory 与 K40 因果闭环

日期：2026-10-01（HKT）
范围：主机侧离线定点分析。未查询或操作手机；未启动 C30；未刷写、切槽、擦除或恢复 PixelOS；未构建 C31。

## 结论

1. C30 的七条 AVC 证明 `zygote` 域中的进程 `main` 读取五类 vendor property area 文件时被 enforcing SELinux 拒绝；AVC 没有 property key、PID 或调用栈。因此不能把七条直接映射到七个属性，也不能从 `tcontext` 倒推出唯一 key。
2. AVC #43 与 PID 1051 的 `main` SIGABRT 相隔约 143 ms，但 AVC 没 PID。另三条 `vendor_default_prop` AVC 比该 SIGABRT 晚约 77 ms。时序很接近，因果没有闭合；PID1 在约 32.922 秒触发 sysrq panic 是更晚的独立事件，现有证据不能把它归因于这些 AVC。
3. C30 与成功 K40 样本的 `framework.jar` **字节完全相同**（SHA-256 `4F24636042ED6661E62660F0724F5C3A22B7E5F2FE73750593F2DCFC77FBA613`），`preloaded-classes` 也完全相同（SHA-256 `F99F598C4120F07869F5CF013BE9972A0903F87F21FC10DF3CA6789E812CAC79`）。C30 的工厂代码把 `UltraFrameworkComponentFactoryImpl` 加载异常捕获并记录，随后返回基础工厂；pmsg 中同一 `main` 进程随后继续记录 `ThirdAppOptImpl has been initialized !`。因此，现有证据不支持“缺少 Impl 类直接令 Zygote 因未捕获异常退出”。
4. K40 vendor CIL 明确允许 Zygote 读取四种 AVC type（`vendor_default_prop`、`vendor_displayfeature_prop`、`vendor_system_prop`、`vendor_display_prop`），并为这些文件规则提供 open/getattr/map；但没有策略注释或运行时对应关系证明这些授权专门修复了 C30 这条 SIGABRT 路径。K40 成功基线提高了这些差异作为兼容性线索的价值，不能替代 exact key、consumer 和 failure 的因果证据。
5. 发现一个精确的 schema 差异候选：C30 把 `ro.hardware.fp.` 映射到 `vendor_fingerprint_prop`，K40 与 Xiaomi 15 donor 映射到 `vendor_fp_prop`；C30 已允许 Zygote 读后者，却没有对前者的对应授权。可是七条 AVC 中 fingerprint 那条没有具体 key；已知 `ro.hardware.fp.fod` 的 framework getter 默认值为 `false`。故此差异目前只能作为 fingerprint 配置兼容性候选，不能作为启动修复。
6. **C31_SYSTEM_CHANGE_SET 为空；没有达到 A/B 证据门槛，本轮不构建 C31。** 不添加任何 SELinux allow。

## C30 七条 AVC 原始记录

逐条原始记录、时间、type、权限、缺失字段已保存在 [C30_AVC_7_RAW.csv](C30_AVC_7_RAW.csv)。原始 console 位于 `work/reports/candidate30_first_boot_20260930/standalone/run_20260930_120848/THYME_DIAG/pstore/console-ramoops-0`，SHA-256 `9b10867ce85eef8ff439f6d013ba7c49f19a36cd452cbe622f0fb71f9a0c04e7`。对应 pmsg SHA-256 为 `f23f288ea72b31c89e3a702f087e9aebf761ff4430933a3aafb61cc0109557a6`。

| uptime（秒） | audit serial | source / comm | target property type | permission / class | PID / exact key |
|---:|---:|---|---|---|---|
| 15.864623 | 40 | `zygote` / `main` | `vendor_displayfeature_prop` | `read` / `file` | 未记录 / 未记录 |
| 15.870559 | 41 | `zygote` / `main` | `vendor_system_prop` | `read` / `file` | 未记录 / 未记录 |
| 15.937830 | 42 | `zygote` / `main` | `vendor_display_prop` | `read` / `file` | 未记录 / 未记录 |
| 15.951674 | 43 | `zygote` / `main` | `vendor_fingerprint_prop` | `read` / `file` | 未记录 / 未记录 |
| 16.180116 | 46 | `zygote` / `main` | `vendor_default_prop` | `read` / `file` | 未记录 / 未记录 |
| 16.180163 | 47 | `zygote` / `main` | `vendor_default_prop` | `read` / `file` | 未记录 / 未记录 |
| 16.180184 | 48 | `zygote` / `main` | `vendor_default_prop` | `read` / `file` | 未记录 / 未记录 |

七条不是七个不同 type；统计为 5 个 type，其中 `vendor_default_prop` 重复三次。AVC 的 `name="u:object_r:…:s0"` 是被访问属性区文件的 SELinux context，并不是 Android 属性名。

## type → 候选 key → consumer 的证据边界

C30 property-context 映射只允许从 type 得到可匹配的显式 key 集合或开放前缀，不能确定运行时 key。候选全表和属性 context 文件哈希见上一份 [C30 Zygote vendor-property AVC 定点闭环报告](../c30_zygote_vendor_property_avc_20260930/C30_ZYGOTE_VENDOR_PROPERTY_AVC_CLOSURE.md) 与 `C30_PROPERTY_DEX_CANDIDATES.csv`。

| AVC type | C30 上下文所覆盖的主要范围 | 找到的代码候选 | 能否认定为实际 deny key / 致命 consumer |
|---|---|---|---|
| `vendor_displayfeature_prop` | 42 个显式 display-feature key，如眼护、FOD dimlayer、DC backlight、DFPS 等 | framework.jar/services.jar DEX 字符串扫描为 0；vendor native consumer 未完整闭合 | 否；key 与消费者均未知 |
| `vendor_system_prop` | 开放前缀 `persist.vendor.sys.` | 有若干 DEX 字符串候选，但没有证据在该时点被 Zygote 调用 | 否 |
| `vendor_display_prop` | `vendor.display.`、`ro.vendor.display.`、`persist.vendor.display.`、`vendor.panel.` 等 | 显示/窗口组件中存在 DEX 候选；未关联到 AVC #42 | 否 |
| `vendor_fingerprint_prop` | 包括 `ro.hardware.fp`、`persist.vendor.sys.fp.`、指纹前缀等 | `ro.hardware.fp.fod` 在 `AmbientDisplayConfiguration.<clinit>` 中以 `getBoolean(key, false)` 读取；该类列于 C30 preload 清单 | 否；AVC 无 key。若恰为此 key，静态代码呈现默认 false 的功能回退，不是直接 fatal 证据 |
| `vendor_default_prop` | 多个通用 `ro.hardware.`、`ro.vendor.`、`persist.vendor.` 等开放前缀，且会被更具体 context 覆盖 | 69 个 DEX 字符串候选，包括 `Build` / 其他类候选；不能映射到 AVC #46–48 | 否；三条具体 key 与执行方法未知 |

DEX 字符串只证明代码包中出现过某个名字，不证明 Zygote 在 15–16 秒调用了它。先前基于混合 UNC 路径的 native 搜索未完成，不能据其“没有命中”排除 native consumer。

## UltraFrameworkComponentFactoryImpl 核查

### 样本文件

| 样本 | `system/framework/framework.jar` | 字节数 / SHA-256 | `preloaded-classes` SHA-256 | 静态结果 |
|---|---|---|---|---|
| C30 | 最终 C30 system tree | 51,385,773 / `4F24636042ED6661E62660F0724F5C3A22B7E5F2FE73750593F2DCFC77FBA613` | `F99F598C4120F07869F5CF013BE9972A0903F87F21FC10DF3CA6789E812CAC79` | 有基础 `UltraFrameworkComponentFactory`；该 JAR 没有 Impl class definition；preload 清单含 Impl |
| Redmi K40 Android 17 | 成功包 system_a 的同一路径 | 51,385,773 / `4F24636042ED6661E62660F0724F5C3A22B7E5F2FE73750593F2DCFC77FBA613` | 与 C30 相同 | framework.jar 与 preload 清单均与 C30 字节相同；定点检查 K40 system_ext 未找到 `/framework/ultra-framework.jar` |
| Milo 4.0.11.0（辅助） | 现存选定 system_a 缓存 | 51,387,717 / `553113B7136B4B69313D7F3872DF46947E14DAAAB3D998F012CF9A4CAB84AB8A` | 与 C30 相同 | framework.jar 未定义 Impl；preload 清单含 Impl；定点检查已有 system_ext 镜像未找到目标 ultra-framework.jar |
| Xiaomi 15 donor | 当前 C30 来自 donor 的 Android 17 system 基线；独立 donor framework.jar 缓存未在本轮小型缓存中找到 | 未单独哈希 | donor 对应完整 preload 文件未独立复核 | 不对 donor 另作文件级结论 |

对 C30/K40/Milo 的 `framework.jar` 做了 DEX class-definition 检查：三者的 `UltraFrameworkComponentFactory` 实现代码可定位；各自该 JAR 中均未定义 `UltraFrameworkComponentFactoryImpl`。这不等价于扫描了镜像里每一个 JAR/APK/APEX，所以不能声称“所有分区、所有容器中都绝对不存在这个 class”。C30 的运行时 `ClassNotFoundException` 证明此次 classloader 查询没有找到它；K40/Milo 目标 system_ext 文件路径的定点查询没有该 jar。K40 runtime 是否打印同一条异常没有设备日志证明。

### 调用与异常处理

C30/K40 共有的 `framework.jar` DEX 中，基础工厂的 `getInstance()`：

1. 先通过类名尝试加载 `android.os.ufw.UltraFrameworkComponentFactoryImpl`；
2. 代码含 `/system_ext/framework/ultra-framework.jar` 路径和显式类加载逻辑；
3. 加载/实例化区间捕获 `Exception`，记录 `Failed to create UltraFrameworkComponentFactoryImpl`；
4. 捕获后创建并返回基础 `UltraFrameworkComponentFactory` 实例。

`SurfaceControl.<clinit>` 调用 `getInstance()` 与 `makeTransactionCallerTracer`。C30 的 preload 清单包含 `SurfaceControl` 与 Impl，因此该路径处于 Zygote 类预加载过程中。C30 pmsg 在 19:56:08.634（PID 1051，`main`）报告 ClassNotFound；约 286 ms 后同一 PID 记录 `ThirdAppOptImpl has been initialized !`。这证明启动继续执行到另一个初始化点，与“该 ClassNotFound 未捕获并立即杀死该 PID”不符。

C30 pmsg 在 19:56:09.146 另报告 PID 1051 `main` 收到 SIGABRT，但没有 abort message 或 native/Java backtrace；crash_dump helper 未能提供 tombstone。第二个 PID 1052 在 19:56:09.111 也记录 ClassNotFound，说明不是唯一的一次类查找。现有材料没有把 SIGABRT 的 `abort()` 调用栈连接到工厂 fallback，也没有证明它由某个 property getter 引发。

## K40、donor、Milo 的 SELinux 对照

K40 当前缓存中的 vendor policy 是 source CIL，明确出现下列规则（`file` 指 property-area 文件访问）：

| K40 CIL 规则 | 含义 |
|---|---|
| `(allow zygote vendor_default_prop (file (read open getattr map)))` | Zygote 可读/打开/查询/映射该 property type |
| `(allow zygote vendor_displayfeature_prop (file (read open getattr map)))` | 同上，display-feature type |
| `(allow zygote vendor_system_prop (file (read open getattr map)))` | 同上，vendor system type |
| `(allow zygote vendor_display_prop (file (read open getattr map)))` | 同上，display type |
| `(allow zygote_30_0 vendor_fp_prop (file (read open getattr map)))` | K40 的特定 zygote_30_0 domain 可读 K40 fingerprint type |

K40 property contexts 把 `persist.vendor.sys.` 映射为 `vendor_system_prop`，把 `vendor.display.` / `ro.vendor.display.` / `persist.vendor.display.` 映射为 `vendor_display_prop`；`ro.hardware.fp.` 与 `persist.vendor.sys.fp.` 等指纹前缀映射到 `vendor_fp_prop`。K40 的精确 display-feature keys 可查上一份闭环报告中的属性清单。

对照结果：

| 目标 | C30 | K40 成功包 | Xiaomi 15 donor | Milo 4.0.11.0 辅助包 |
|---|---|---|---|---|
| 四种常见 type 的 Zygote access | runtime AVC 已证明 read 被拒；C30 未见等价 vendor grant | 有显式 Zygote read/open/getattr/map | 本轮限定 CIL 检索未见等价四条 grant | 本地缓存的 vendor CIL 未见等价四条 grant；不是成功基线 |
| fingerprint 前缀 | `ro.hardware.fp` family 映到 `vendor_fingerprint_prop`；C30 policy 的 Zygote grant 面向另一 type `vendor_fp_prop` | `ro.hardware.fp.` → `vendor_fp_prop`，且 `zygote_30_0` 可访问 | `ro.hardware.fp.` → `vendor_fp_prop`，donor 对应 zygote domain 有 grant | context 仍采用 fingerprint 类型命名；未见 Zygote 对 C30 被拒 type 的 grant |
| 四种 grant 具体修了什么 | 无法由 C30 policy 推断 | policy 证明读取被允许；没有注释/运行时 key 与此 SIGABRT 的映射 | 不足以证明 K40 方案 | 仅辅助对照，不用于成功性结论 |

K40 的四类规则解释了为什么这些 property-area 读取在 K40 策略下不会产生同类 read AVC；它们**不证明**K40 作者是为当前启动 fatal 增加规则，也不证明 C30 的实际读取值对 Framework 必不可少。Milo 缺少同类 grant 且也有近似 framework/preload 基线，进一步说明不能仅凭 K40 grant 推断该拒绝必然造成启动失败；但 Milo 没有已确认的 10S 成功实机结果，不能把它当成反证或成功样本。

### Fingerprint type/schema 候选

C30 property context 中实际字符串是 `ro.hardware.fp`（没有末尾点），映射到 `vendor_fingerprint_prop`；K40 与 Xiaomi 15 donor 使用 `ro.hardware.fp.`，映射到 `vendor_fp_prop`，且对应 Zygote domain 有该 type 的读取规则。按 C30 已解析的属性上下文语义，这形成 fingerprint key-family schema 差异候选，不是仅凭 type 名相似得出的等价关系。C30 的 `ro.hardware.fp.fod` 候选由预加载的 `AmbientDisplayConfiguration` 以默认 `false` 读取，倾向于功能回退。由于 AVC #43 不含 key/PID，仍不能说它就是 `ro.hardware.fp.fod`，更不能把它解释为 main SIGABRT 根因。

相关策略来源指纹（文件本身为本地现存文本，不是本轮从 ROM 全量重新提取）：

| 样本 | vendor_property_contexts SHA-256 | vendor_sepolicy.cil SHA-256 |
|---|---|---|
| C30 thyme vendor | `5F5A61368B71F0B27A98B1D9BBF2629E16DEDE136B98D69D292FA3C788CB9864` | `EA2CD71B7A6047E5ABACA70C1EC0A011D24B2FDCD479E35B6BBD04DF8F8D7373` |
| K40 alioth success sample | `075E5C4AC595948D840179C140FA3DD79BB075BCDECA5BA45FFE5C2DFF9F347C` | `472585D57CFB39C57C924E4FF349C2A45DC724CAA2A94D517F5E09397AB783F9` |
| Xiaomi 15 donor | `91EF20409FF9674505B7B1800FCCD3FF35D72F1C73D0EE91213AC88A9F289677` | `D9A7F01635AFF92A3EA251837CF4FE334236EC707046EEC17AFD790FBD3EF2B5` |
| Milo 4.0.11.0 auxiliary | `C8EF48D563AC60076E6FF7537C93AFE32E76C74E7D87B68213B9300815CFDE49` | `A9AE72213B406C516A18A009FDC58F058CD49D66BE8212C7461E75AD33D52E1F` |

K40 vendor CIL 的四种 Zygote read 规则位于约 11137、11181–11184 行；同类 open 规则位于约 11319、11336–11338 行，getattr 位于约 11435、11447、11449、11452 行，map 位于约 11536、11544–11546 行。fingerprint `zygote_30_0 → vendor_fp_prop` 规则位于约 11019 行。行号按缓存文件 `work/stage_a_tmp_k40/k40_vendor_meta/k40_vendor/etc/selinux/vendor_sepolicy.cil`。

## 时间与因果判定

| 时间（启动墙钟） | 事件 | 可以证明什么 | 不能证明什么 |
|---|---|---|---|
| 19:56:08.634 | PID 1051 `main` 记录 Impl ClassNotFound/fallback 路径 | 类加载失败发生在 Zygote 初始化窗口 | 不能证明此异常致命 |
| 19:56:08.916–09.003 | AVC #40–43 | 四个不同 type 的访问在 Zygote domain 被拒绝 | AVC 没 PID/key，不能 join 到 PID 1051 |
| 19:56:08.920 | PID 1051 `ThirdAppOptImpl` 初始化完成 | PID 1051 在工厂异常后继续执行 | 不能证明之后不会因另一原因 abort |
| 19:56:09.111 | PID 1052 同类 ClassNotFound | 第二个 `main` 实例也触发类查找 | 不能证明 PID 1051/1052 的 fork/退出因果 |
| 19:56:09.146 | PID 1051 `main` SIGABRT | PID 1051 终止信号确定 | 缺 abort message/backtrace；无法确定 abort 调用点 |
| 19:56:09.223 | AVC #46–48 | 三次 vendor_default_prop 访问被拒，时间晚于 PID 1051 SIGABRT | 不清楚对应哪个 PID/consumer |
| uptime 32.922 s | PID 1 通过 `write_sysrq_trigger` 触发 panic | PID 1 的主动 sysrq panic 与较早 main SIGABRT 不同事件 | 没有 init fatal 上游条件，不能连到 AVC 或 Impl 缺类 |

判定：7 条 AVC 属于 **B 类（时间相关但缺因果）**。UltraFramework ClassNotFound 本身因 catch/fallback 与后续执行证据，作为直接 fatal 假说降级；仍不能排除另一个未捕获错误。PID1 panic 独立原因尚未定位。

## C31 决策与下一步

`C31_SYSTEM_CHANGE_SET.csv` 仅含表头：本轮没有符合门槛的系统行为修改。

| 候选 | 当前证据 | 决策 |
|---|---|---|
| 对四类 vendor property 增加 Zygote `get_prop` | K40 有授权，C30 有 AVC；但具体 key、consumer、PID、后续 failure 未闭合，Milo 辅助样本也未见同类授权 | 不进入 C31；不允许 broad type allow |
| 修复 `vendor_fingerprint_prop` / `vendor_fp_prop` schema 差异 | 前缀映射差异确证；实际 AVC #43 key 未知；已定位 FOD consumer 使用默认 false | 仅保留为后续功能兼容候选；不能当启动 blocker |
| 补入 `UltraFrameworkComponentFactoryImpl` | C30/K40 framework.jar 与 preload 完全一致；缺类异常在代码里有 catch/fallback，C30 随后继续初始化 | 不修；没有证据它导致 SIGABRT |
| 修改 Tango、critical、secondary zygote callback、ART | 本轮无新的直接因果证据 | 冻结，不混入候选 |

下一次若要推进这条根因线，关键新增证据应能同时给出：property key + 读取进程 PID/调用点，以及 Zygote abort 的可用 tombstone/backtrace。C30 canary/events/logcat 文件为空，不能再依赖其现有运行证据。当前 A retry=3 是最后历史只读记录，不是本轮实测；本轮未查询设备。不得把该值当实时状态。

## 验证与公开范围

- 比较对象是 C30 实际构建 system tree、K40 Android 17 system_a/system_ext 缓存和已存在的 Milo 4.0.11.0 system_a/system_ext 缓存；未重新展开整套 ROM，也未提取完整 super。
- framework.jar 的 SHA/大小及 DEX class-definition、preloaded list 的 SHA 为主机静态检查；不是 K40 设备日志或 C30 运行时反编译。
- C30 的运行时事实来自已保存原始 pstore/pmsg；其未修改原件保持本机原处。本报告和 CSV 不包含原始 pstore、镜像或第三方二进制。
- 本轮不查询设备；A retry=3 仅为最近历史快照。
