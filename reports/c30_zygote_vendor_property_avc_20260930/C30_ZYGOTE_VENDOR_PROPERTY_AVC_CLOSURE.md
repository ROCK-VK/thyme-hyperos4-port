# C30 Zygote vendor-property AVC 定点闭环

时间：2026-10-01 HKT

## 结论摘要

- C30 console 中有七条 Zygote domain 对 vendor property area 的 read 拒绝，涉及五种目标 SELinux type。AVC 记录只有 context type、comm=main 和 tmpfs inode，没有具体 property key、property value 或 PID。
- 将五种 type 反查到 C30 有效 property-context 输入后，可以得到可能的 key 前缀/显式 key集合；其中若干规则是开放前缀，因此不能从 type 反推出唯一 key。
- C30 framework.jar/services.jar 的静态 DEX 扫描得到 82 个 property 字面量候选（vendor_default_prop 69、vendor_display_prop 6、vendor_system_prop 4、vendor_fingerprint_prop 3；vendor_displayfeature_prop 为 0）。它们只是代码引用候选，不是七条 AVC 的键值映射，也没有证明执行时序。
- pmsg 与 console 的时间对齐显示，第四条 AVC 到 PID 1051 的 main/SIGABRT 仅相隔约 143 ms；其余三条 vendor_default_prop AVC 在该 SIGABRT 后约 77 ms 出现。之后又有多次 main/SIGABRT，约 uptime 32.922 秒 PID 1 通过 write_sysrq_trigger 触发 panic。这个时间关系显著，但 AVC 没有 PID，且没有 fatal backtrace 或属性键，因果仍未闭合。
- 成功启动的 K40 vendor policy 对 vendor_default_prop、vendor_displayfeature_prop、vendor_system_prop、vendor_display_prop 明确授予 Zygote read；最新 Milo 4.0.11.0-TGBCNXM vendor policy 未见对这些类型的等价 Zygote grant，相关 property-context 映射基本与 C30 一致。Xiaomi 15 donor vendor policy 仅在本次定点规则检索中确认对 vendor_fp_prop 的 Zygote read。
- 不满足构建 C31 的 A/B 证据门槛：具体 AVC key 与消费者尚未对应，且拒绝后的进程失败没有因果证明。不得据此开放整类 vendor property。

## 范围与版本识别

本轮只做主机侧只读分析：未查询或操作手机、未启动 C30、未刷写、未 set_active、未擦除 userdata/metadata、未恢复 PixelOS、未构建 C31。

作者最新上传目录按用户提供的名称识别为 4.0.11.0-TGBCNXM。本轮只从其 super 中定点读取 vendor_a 的 property contexts 和 CIL，不把 BAT、EXE、APK 作为运行对象，也未把整套系统分区展开。包内 OTA metadata 与目录标签不一致（metadata 中仍出现 fuxi / Android 13 标记），故本报告将 4.0.11.0-TGBCNXM 视为上传目录标签，而不据此认证 system build fingerprint。该限制不影响本轮读取的 vendor_a SELinux 文件哈希。

## C30 原始 AVC

来源为 C30 首次启动保存的 console-ramoops-0，SHA-256：
9b10867ce85eef8ff439f6d013ba7c49f19a36cd452cbe622f0fb71f9a0c04e7

以下是七条完整原始记录。每条均为 scontext=u:r:zygote:s0、permission=read、tclass=file、comm=main、permissive=0。原始记录没有 PID、property key/value 或 property source path。

    [   15.864623] type=1400 audit(1857368.916:40): avc:  denied  { read } for  comm="main" name="u:object_r:vendor_displayfeature_prop:s0" dev="tmpfs" ino=14879 scontext=u:r:zygote:s0 tcontext=u:object_r:vendor_displayfeature_prop:s0 tclass=file permissive=0
    [   15.870559] type=1400 audit(1857368.923:41): avc:  denied  { read } for  comm="main" name="u:object_r:vendor_system_prop:s0" dev="tmpfs" ino=14955 scontext=u:r:zygote:s0 tcontext=u:object_r:vendor_system_prop:s0 tclass=file permissive=0
    [   15.937830] type=1400 audit(1857368.990:42): avc:  denied  { read } for  comm="main" name="u:object_r:vendor_display_prop:s0" dev="tmpfs" ino=14878 scontext=u:r:zygote:s0 tcontext=u:object_r:vendor_display_prop:s0 tclass=file permissive=0
    [   15.951674] type=1400 audit(1857369.003:43): avc:  denied  { read } for  comm="main" name="u:object_r:vendor_fingerprint_prop:s0" dev="tmpfs" ino=14883 scontext=u:r:zygote:s0 tcontext=u:object_r:vendor_fingerprint_prop:s0 tclass=file permissive=0
    [   16.180116] type=1400 audit(1857369.223:46): avc:  denied  { read } for  comm="main" name="u:object_r:vendor_default_prop:s0" dev="tmpfs" ino=14874 scontext=u:r:zygote:s0 tcontext=u:object_r:vendor_default_prop:s0 tclass=file permissive=0
    [   16.180163] type=1400 audit(1857369.223:47): avc:  denied  { read } for  comm="main" name="u:object_r:vendor_default_prop:s0" dev="tmpfs" ino=14874 scontext=u:r:zygote:s0 tcontext=u:object_r:vendor_default_prop:s0 tclass=file permissive=0
    [   16.180184] type=1400 audit(1857369.223:48): avc:  denied  { read } for  comm="main" name="u:object_r:vendor_default_prop:s0" dev="tmpfs" ino=14874 scontext=u:r:zygote:s0 tcontext=u:object_r:vendor_default_prop:s0 tclass=file permissive=0

| uptime | audit serial | target type | inode | comm | exact key |
|---:|---:|---|---:|---|---|
| 15.864623 | 40 | vendor_displayfeature_prop | 14879 | main | not recorded |
| 15.870559 | 41 | vendor_system_prop | 14955 | main | not recorded |
| 15.937830 | 42 | vendor_display_prop | 14878 | main | not recorded |
| 15.951674 | 43 | vendor_fingerprint_prop | 14883 | main | not recorded |
| 16.180116 | 46 | vendor_default_prop | 14874 | main | not recorded |
| 16.180163 | 47 | vendor_default_prop | 14874 | main | not recorded |
| 16.180184 | 48 | vendor_default_prop | 14874 | main | not recorded |

因此不是七种已知 property：实际是五个目标 type，其中 vendor_default_prop 重复三次。name= 中的值是属性区 inode 的 SELinux context 名，不是 Android property key。

## C30 property-context 反查

映射输入：

- C30 vendor_property_contexts（thyme vendor 提取缓存）：31,655 B，SHA-256 5F5A61368B71F0B27A98B1D9BBF2629E16DEDE136B98D69D292FA3C788CB9864。
- C30 plat_property_contexts（C30 最终 system tree）：SHA-256 077A682C00335D045C268DF2D57C6D966C87959E61AC2195F6884A971A72FA66。
- C30 vendor_sepolicy.cil：988,992 B，SHA-256 EA2CD71B7A6047E5ABACA70C1EC0A011D24B2FDCD479E35B6BBD04DF8F8D7373。

按 Android property-info trie 的前缀/精确匹配语义合并上下文后，AVC type 的可映射名称范围如下。属性名若来自开放前缀，匹配规则可能覆盖多个子属性；type 本身不能告诉我们运行时实际访问的是哪一个。

### vendor_displayfeature_prop（42 个显式属性）

ro.vendor.eyecare.threshold、ro.vendor.eyecare.level、ro.vendor.hist.threshold、ro.vendor.histogram.enable、ro.vendor.whitepoint_calibration_enable、ro.vendor.df.effect.conflict、ro.vendor.fod.dimlayer.enable、persist.vendor.df.extcolor.proc、vendor.displayfeature.entry.enable、persist.vendor.df.color.temp、ro.vendor.colorpick_adjust、ro.vendor.display.type、ro.vendor.xiaomi.bl.poll、persist.vendor.dc_backlight.threshold、persist.vendor.dc_backlight.enable、persist.vendor.fod.modified.dc_status、persist.vendor.light.bit.switch、ro.vendor.all_modes.colorpick_adjust、ro.vendor.cabc.enable、ro.vendor.bcbc.enable、ro.vendor.dfps.enable、ro.vendor.smart_dfps.enable、vendor.hbm.enable、persist.vendor.dfps.level、persist.vendor.user.fps、persist.vendor.power.dfps.level、persist.vendor.video.dfps、persist.vendor.video.dfps.level、ro.vendor.display.default_fps、persist.vendor.max.brightness、ro.vendor.soft_backlight.enable、ro.vendor.gcp.enable、ro.vendor.sre、ro.vendor.standard.video.enable、ro.vendor.hbm_backlight.enable、ro.vendor.display.touch.idle.enable、ro.vendor.display.smartpen.idle.enable、ro.vendor.video_box.version、ro.vendor.video.decode.only、ro.vendor.localhbm.enable、ro.vendor.fps.switch.thermal、ro.vendor.fps.switch.default。

### vendor_system_prop

开放前缀：persist.vendor.sys.

### vendor_display_prop

开放前缀：vendor.display.、ro.vendor.display.、persist.vendor.display.、vendor.panel.；另有显式项 vendor.display.disable_rounded_corner_thread。

### vendor_fingerprint_prop

开放前缀/条目：gf.debug.、persist.vendor.fingerprint.、persist.vendor.fpc.、persist.vendor.sys.fp.、ro.boot.fpsensor、ro.hardware.fp、sys.panel.display、sys.panel.touch_vendor、vendor.fps_hal.。

### vendor_default_prop

来自 plat_property_contexts 的通用开放前缀：init.svc.odm.、init.svc.vendor.、ro.hardware.、ro.odm.、ro.vendor.、ro.vendor_dlkm.、ro.odm_dlkm.、odm.、persist.odm.、persist.vendor.、vendor.。更具体的 vendor/product/odm context 会覆盖较宽前缀。仅凭 AVC 无法在这些开放范围中选出发生拒绝的名称。

C30 vendor CIL 对 zygote_30_0 明确包含 vendor_fp_prop 的 read/getattr/map/open 访问，但没有针对以上五种 runtime-denied type 的等价 vendor allow。实际 AVC 已证明这七次访问在 C30 enforcing 状态被拒绝。

## 消费者检查与失败语义

对 C30 framework.jar/services.jar 的 DEX 字面量扫描产生 82 个候选引用，完整清单见 C30_PROPERTY_DEX_CANDIDATES.csv。候选条目是静态字符串和所属类/方法，不等于发生 AVC 的属性键，也不等于该方法在 Zygote 主进程启动窗口中被调用。

较接近启动的候选：

- vendor_fingerprint_prop：ro.hardware.fp.fod 出现在 AmbientDisplayConfiguration 的静态初始化，调用 SystemProperties.getBoolean，默认 false。该候选若遭拒，读取结果可退回 false，语义更像关闭 FOD 配置，而不是直接 fatal。ro.hardware.fp.sideCap 出现在指纹传感器配置映射方法；没有证据该方法在 AVC 时运行。
- vendor_display_prop：DEX 出现 vendor.display.disable_rounded_corner、ro.vendor.display.dynamic_get_brightness_to_nits_spline、ro.vendor.display.uiservice.enable、vendor.display.builtin_mirroring、vendor.display.builtin_presentation、vendor.display.override_mirroring_rotation。引用分散在显示/窗口相关类中；没有把任何一项关联到七条 AVC。
- vendor_system_prop：DEX 候选包括 persist.vendor.sys.satellite.enable、persist.vendor.sys.fast_setup_data_network、persist.vendor.sys.activitylog、persist.vendor.sys.debug.wfd.gointent；没有证据这些 getter 在 Zygote 预加载路径中导致退出。
- vendor_displayfeature_prop：framework.jar/services.jar 扫描没有找到匹配的 literal property key。thyme vendor 中存在 displayfeature/HWC 相关二进制，但仅凭这些文件含有图形属性字符串，不能将其认作 Zygote 在本次 AVC 的实际消费者。
- vendor_default_prop：69 个 DEX 候选包含 Build 静态初始化候选、vendor.package.map，以及条件分支中的 persist.vendor.gwpasan.enable 等。逐项候选在 CSV；没有运行时 key、调用栈或对应 getter 错误能指出其中任何一项就是这三条 AVC。

Console 记录的是属性共享区文件 context，而非 property key；静态字符串引用只能缩小候选集合，不能闭合 property key → 具体 getter → 失败/退出。另对 124 个候选名称做了 system/vendor 编译文件字符串检索；检索返回状态 2，输出的命中文件路径不构成完整 native consumer 清单，也没有建立运行时访问到 AVC 的对应关系，因此不作为排除 native consumer 的证据。

## 时间对齐：AVC 与 Zygote SIGABRT / PID 1 panic

console audit 时间与 pmsg 启动日志时间对齐如下：

| 时间（约） | 证据 | 解释 |
|---|---|---|
| 19:56:08.634 | PID 1051 的 main 路径记录 UltraFrameworkComponentFactoryImpl ClassNotFoundException | 后续同一日志流仍继续初始化；不单独证明 fatal |
| 19:56:08.916–09.003 | AVC 40–43，四种 property type | console 没有 PID；comm=main |
| 19:56:08.920 | PID 1051 记录 ThirdAppOptImpl 初始化完成 | 说明至少有启动工作继续执行 |
| 19:56:09.111 | PID 1052 的 main 记录相同 ClassNotFoundException | 不足以将其与 console AVC 对应 |
| 19:56:09.146 | PID 1051 的 main 收到 SIGABRT | 距离最近的前一条 type AVC 约 143 ms；pmsg 随后说 crash_dump helper failed to exec / was killed，没有 backtrace |
| 19:56:09.223 | AVC 46–48，vendor_default_prop 三条 | 比 PID 1051 SIGABRT 晚约 77 ms；可能处于后续实例，但 AVC 无 PID，不能确认 |
| 19:56:11.065 / 15.906 / 20.893 / 25.930 | PID 1754 / 2453 / 2636 / 2756 的 main SIGABRT | 重复 Zygote-domain main 进程崩溃；仍无 crash backtrace |
| uptime 32.921975–32.922062 | console: sysrq Trigger a crash、Kernel panic；栈经过 PID 1 init 的 write_sysrq_trigger | panic 是 init 主动走 sysrq 路径；与最后一条已见 main SIGABRT 相隔约 6.99 秒，触发该 init fatal 的上游属性/条件仍不明 |

C30 metadata marker 曾观察到 zygote running/restarting 状态，但有序 events/logcat 文件为空，没有可用于关联 service、PID 与每条 AVC 的时间序列。因此：

- AVC 与 Zygote main SIGABRT 存在强时间相关；
- 没有证据说明是哪条 AVC 触发了 PID 1051；
- 没有证据证明 AVC 导致后续所有 Zygote 重启；
- 没有证据将某个 vendor-property deny 连接到 PID 1 的 sysrq panic；
- UltraFrameworkComponentFactoryImpl 缺类在同一启动窗口出现，但已看到初始化继续，尚无直接 fatal 因果。

## C30 / K40 / Xiaomi 15 donor / Milo 4.0.11.0 对照

使用的 vendor SELinux 文件：

| 样本 | vendor_property_contexts SHA-256 | vendor_sepolicy.cil SHA-256 |
|---|---|---|
| C30 thyme vendor | 5F5A61368B71F0B27A98B1D9BBF2629E16DEDE136B98D69D292FA3C788CB9864 | EA2CD71B7A6047E5ABACA70C1EC0A011D24B2FDCD479E35B6BBD04DF8F8D7373 |
| K40 alioth successful package | 075E5C4AC595948D840179C140FA3DD79BB075BCDECA5BA45FFE5C2DFF9F347C | 472585D57CFB39C57C924E4FF349C2A45DC724CAA2A94D517F5E09397AB783F9 |
| Xiaomi 15 donor vendor snapshot | 91EF20409FF9674505B7B1800FCCD3FF35D72F1C73D0EE91213AC88A9F289677 | D9A7F01635AFF92A3EA251837CF4FE334236EC707046EEC17AFD790FBD3EF2B5 |
| Milo 4.0.11.0 vendor_a | C8EF48D563AC60076E6FF7537C93AFE32E76C74E7D87B68213B9300815CFDE49 | A9AE72213B406C516A18A009FDC58F058CD49D66BE8212C7461E75AD33D52E1F |

| runtime-denied type | C30 | K40 | Xiaomi 15 donor | Milo 4.0.11.0 |
|---|---|---|---|---|
| vendor_default_prop | runtime read denied; no matching explicit C30 vendor zygote read grant | explicit zygote read plus open/getattr/map | no equivalent grant found in targeted vendor CIL search | context rules same family as C30; no explicit zygote grant found |
| vendor_displayfeature_prop | runtime read denied; no matching explicit C30 vendor zygote read grant | explicit zygote read plus open/getattr/map | no equivalent grant found in targeted vendor CIL search | same 42 relevant mappings as C30; no explicit zygote grant found |
| vendor_system_prop | runtime read denied; no matching explicit C30 vendor zygote read grant | explicit zygote read plus open/getattr/map | no equivalent grant found in targeted vendor CIL search | relevant mapping persist.vendor.sys. matches C30; no explicit zygote grant found |
| vendor_display_prop | runtime read denied; no matching explicit C30 vendor zygote read grant | explicit zygote read plus open/getattr/map | no equivalent grant found in targeted vendor CIL search | relevant display prefixes match C30; no explicit zygote grant found |
| vendor_fingerprint_prop | runtime read denied. C30 allows zygote_30_0 to vendor_fp_prop, a different type | K40 maps ro.hardware.fp. to vendor_fp_prop and grants zygote_30_0 read | donor likewise maps ro.hardware.fp. to vendor_fp_prop and grants zygote_202504 read | Milo maps the relevant family to vendor_fingerprint_prop like C30 and has no explicit zygote grant to that type |

K40 is the only compared success sample with explicit Zygote grants matching the first four denied contexts. This is useful compatibility evidence, but the exact C30 AVC keys are absent, and Milo 4.0.11.0 does not reproduce those K40 grants. It supports a follow-up targeted diagnosis, not a broad allow or a causal claim.

The latest Milo super image is 6,463,833,468 B, SHA-256 72A2B43B8766DF827E3A3D35E2D51887A9F541C1DB1995926CA5E03E607BDE40. The selected vendor_a image is 878,948,352 B, SHA-256 A0455C51973F2E130A740A31938B2975E08E50FD4384F6F2F4C465792D1164A6. The full Milo system_a was not extracted for this report; system-version attribution remains unverified.

## 决策与下一步

- 不构建 C31；不添加 broad vendor property read。
- 不把七条 AVC 认定为无害，也不认定为 Zygote 崩溃根因：这是与 main SIGABRT 紧邻的高价值相关线索。
- 下一项有效证据应能同时记录 Zygote 读取的 property key 和对应 PID/调用点，或取得可用的 SIGABRT tombstone/backtrace；C30 当前日志格式不具备这些字段。
- 在获得该证据前，保留当前 C30 和现有有效 Candidate，不修改 SELinux。
- 本轮设备状态未实时查询；最后历史只读记录为 A retry=3、unbootable=no，不应视为当前实时状态。
- C/D/E 当前空闲空间实测分别为 93.35 / 198.16 / 170.94 GiB。没有清理空间、未触及 Docker。分析工作区仍有可重建临时提取物，本轮未清理。

## 参考与来源

- 本地 C30 原始证据：C30 首次启动 Standalone 导出中的 pstore/console-ramoops-0、pmsg-ramoops-0；两者均保留原字节。
- C30 DEX 候选生成器与 JSON：本目录中的 dex_property_refs.py、c30_dex_property_refs.json；生成的面向审核 CSV 为 C30_PROPERTY_DEX_CANDIDATES.csv。
- AOSP PropertyInfoArea 前缀/精确匹配测试仅用于解释 property-context trie 的名称匹配规则；不是对 Xiaomi runtime policy 的替代：<https://android.googlesource.com/platform/system/core/+/master/property_service/libpropertyinfoserializer/property_info_serializer_test.cpp>
