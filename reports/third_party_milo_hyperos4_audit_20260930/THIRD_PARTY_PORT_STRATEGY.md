# 第三方 Milo HyperOS4 10S 移植包离线审计与策略摘要

审计日期：2026-09-30
对象：本机现存目录 `10S系统/小米10s-MiloHyperOS-4.0.0.44TGNCNXM`
范围：静态清点、脚本文本审阅、镜像/LP/AVB 元数据检查、启动链定点对照。没有运行包内程序，没有操作手机。

## 结论摘要

这不是一个可直接信任的、单一格式的 thyme 发布包。它是**自定义 Windows Fastboot 刷机包与不一致的 Recovery updater 混合目录**：Windows BAT 声称用于 Xiaomi 10S/thyme，但会擦除 FRP 与 super、对一组底层分区使用 _ab 目标名（包括 modem）、写入 vbmeta A/B、设置 A 槽、可选擦除 userdata/metadata，并自动重启；Recovery updater 自称只适用于 Xiaomi Pad 7 Pro/muyu，且引用了包内不存在的固件文件。

包内的 system/product/vendor 元数据来源并不一致；super 的 LP 布局也不同于项目当前 C30。其 netd/BPF 关键代码与 C30/K40 对照没有显示出针对 Linux 4.19 的修复，反而保留 netd 重启 primary/secondary Zygote 的两条回调。因此它**不满足 External Candidate 条件**。本轮没有创建 staging 或刷写 Dry-Run。

作者后来向用户表示，他忘记 Xiaomi 10S 有 A/B 分区，先前使用的分区映射有误。该说明是用户转述的作者意见，没有随包附上修订版或更正后的完整分区表，故作为外部新信息记录，不能替代对本地这份旧包的静态审计。另一个交叉检查发现：项目保存的 Xiaomi 10S 官方 Android 13 fastboot 脚本本身也使用 boot_ab、vendor_boot_ab 等目标名。因此，作者所说的“分区错误”具体指哪些名称/写入对象仍待其给出明确更正；不能仅凭“忘了 A/B”推定本地 BAT 中每一个 _ab 名称都错误。无论该说明如何解释，本包现存 BAT 与 Recovery updater 的写入范围和来源矛盾已足以排除实机测试。

## 1. 包结构与类型

清点得到 49 个文件，总计 7,602,127,591 字节（约 7.08 GiB）。清单逐文件记录相对路径、大小、SHA-256、类型和静态标志，见 `THIRD_PARTY_PACKAGE_MANIFEST.csv`；镜像清单见 `IMAGE_AUDIT.csv`。

| 位置 | 文件数 | 大小 |
|---|---:|---:|
| bin | 17 | 29,043,129 B（约 27.70 MiB） |
| images | 24 | 7,540,262,460 B（约 7.02 GiB） |
| META-INF | 5 | 13,385 B |
| 根目录其他文件 | 3 | 32,808,617 B（约 31.29 MiB） |

类型判断：自定义 Windows Fastboot 包为主要入口，同时夹带一份不适用于 thyme 的 Recovery updater 和 OTA metadata。它不是可正常安装的标准 A/B Recovery ZIP：

- META-INF metadata 写有 ota-type=AB、pre-device=fuxi、Android 13/SDK 33、Xiaomi build V14.0.29.0.TMCCNXM，并引用 payload.bin；实际目录没有 payload.bin。
- updater-script 只有 10 字节占位文本。
- update-binary 文本明确写着仅限 Xiaomi Pad 7 Pro、设备代号 muyu；它直接向 by-name 块设备输出镜像。
- Windows BAT 则自称 Xiaomi 10S/thyme，同时顶部还写有 Xiaomi 17 Pro Max 移植字样。
- BAT 对 super.img.zst 的可选解压条件附近可见多余的右括号；没有运行它验证批处理行为。

### images 清单

abl.img、aop.img、bluetooth.img、boot.img、cmnlib.img、cmnlib64.img、devcfg.img、dsp.img、dtbo.img、featenabler.img、hyp.img、imagefv.img、keymaster.img、modem.img、qupfw.img、recovery.img、super.img、tz.img、uefisecapp.img、vbmeta_system.img、vbmeta.img、vendor_boot.img、xbl_config.img、xbl.img。

文件类型静态识别：super.img 是 Android sparse；boot.img、vendor_boot.img、recovery.img 是 Android boot image；dsp.img 是 ext4；bluetooth.img、modem.img 被识别为 FAT 文件系统镜像；多项低层固件镜像为 ARM/Qualcomm ELF；vbmeta 镜像为 AVB vbmeta。具体大小、SHA-256、稀疏状态和 AVB footer 状态见 IMAGE_AUDIT.csv。

## 2. 两套安装脚本的实际范围

### Windows Fastboot BAT

脚本共有 32 条 Fastboot 写入/控制命令，详见 `BAT_WRITE_PLAN.csv`。静态读到的行为：

1. 无条件 erase frp。
2. 对 abl、aop、bluetooth、boot、cmnlib、cmnlib64、devcfg、dsp、dtbo、featenabler、hyp、imagefv、keymaster、modem、qupfw、recovery、tz、uefisecapp、xbl、xbl_config、vendor_boot 发起 _ab 目标写入。这里仅记录命令中的目标名，不对 Bootloader 如何解析它作设备端断言。
3. 对 vbmeta_a、vbmeta_b、vbmeta_system_a、vbmeta_system_b 使用 --disable-verity 后写入。
4. erase super，再 flash super.img。
5. set_active a，随后 reboot。
6. 菜单选项 2 还会 erase userdata 与 metadata。
7. 脚本没有 persist、modemst、EFS/NV 写入或 Bootloader relock 命令；但它明确刷 modem 固件、多个 bootloader/固件分区，并擦 FRP 与 super。

项目本地 Xiaomi 10S 官方 Android 13 的 flash_all.bat 也使用 boot_ab、vendor_boot_ab、abl_ab 等目标名称并设置 active A。这只证明命名形式与官方脚本一致；本轮没有运行 fastboot、探测 bootloader 对这些名称的实际解析，也没有据此验证第三方完整映射正确。作者后来承认此前分区映射有误，因此必须取得其修订包和逐项映射才能重新审计。

### Recovery update-binary

静态写入计划见 `RECOVERY_WRITE_PLAN.csv`。update-binary 有 58 个块设备/数据路径动作记录：

- 通过 shell 重定向直接向大量 _a/_b by-name 节点写入固件、boot、vendor_boot、dtbo、vbmeta、recovery 等镜像。
- 引用但在包中不存在的源文件包括 xbl_ramdump.img、vm-bootsys.img、uefi.img、shrm.img、cpucp.img、aop_config.img（各目标 A/B 槽均出现）。脚本封装没有对每个 extract 调用做可靠的源文件检查，不能假设它会安全跳过。
- 手写 sparse 解码器把 super.img 的 RAW/FILL chunk 通过 dd 写向 super；没有先整体 erase super，DONT_CARE chunk 只推进偏移而不清除旧数据。
- 删除 /data/dalvik-cache 与 /data/system/package_cache 内容；脚本没有显式 erase/format userdata 或 metadata 命令，但文案建议首次刷入时手动格式化 data。
- updater 自己声明适用 muyu，不能作为 thyme 的安装依据。

这些动作是脚本文本审阅结果，并非执行结果。本轮没有运行 BAT、update-binary、bin 内工具或第三方 exe。

## 3. PE 与 APK 静态结果

- 驱动 EXE：文件版本 1.0.5.0，产品/描述标记为一键安装安卓驱动；未签名。静态识别为 x86 .NET GUI PE，导入包含 mscoree.dll 的 .NET 入口。未逆向安装逻辑，因此只能说其元数据“标称驱动安装器”，不能确认其行为就是普通 USB 驱动安装。
- SukiSu.apk：package com.sukisu.ultra，SukiSU Ultra v4.1.3（versionCode 40796），minSdk 31、target/compileSdk 37；含 arm64-v8a、armeabi-v7a、x86_64 native libraries，并有 KernelSU/SuSFS 及 root 管理相关组件。它是可选 Root 管理工具，不是 ROM 启动必需组件。APK 签名结构校验通过；这不等于对作者或来源的信任背书。
- 两者以及 APK/ZIP 内容没有执行、安装或启动。

## 4. 镜像、AVB 与 LP

### 启动链镜像与固件来源

第三方包中的 boot、vendor_boot、dtbo、vbmeta、vbmeta_system 均与本地 Xiaomi 10S Android 13 官方基线逐字节一致：

| 镜像 | 大小 | SHA-256 |
|---|---:|---|
| boot.img | 134,217,728 B | c96d171afc58e81ceba3a2fb79916b5e785ce875c3e497d5772f2e22b5b506eb |
| vendor_boot.img | 100,663,296 B | 69c59d9cf02c845490634f0c89ee7099f4353f92824f7e7aec0121a6dae2b592 |
| dtbo.img | 33,554,432 B | a0f550a32c15b95a6ba0bbe141976bad905d23fc74367e3e3ff0f41bc90c6d3a |
| vbmeta.img | 8,192 B | a425af6183813e1bbb234d56552a7058b652fb81e405f4a5d9806a431b69b3ba |
| vbmeta_system.img | 4,096 B | 12af57223c00c3bd9f04b522ac3e4b0cdaa3b838e5943c7b53184372f8f863ef |

该 stock boot 内核标识为 4.19.157-perf-g92c089fc2d37。它没有带来项目 K40 成功移植所用的 4.19.325 自定义内核，也没有可见的 Android17/4.19 内核兼容补丁证据。

多个第三方低层镜像与本地 10S Android13 官方 firmware 匹配：部分逐字节相同，部分为官方内容后填零至分区镜像尺寸。modem.img 与官方 NON-HLOS.bin 对应。未发现它使用 K40 的 modem 或整套 K40 固件。Recovery image 的 AVB 属性自标识为 TWRP thyme/alioth Android 15 测试构建；该标签不能证明其为 K40 成功包内容，也不能证明适用于本机。

### AVB 与 super 布局

- vbmeta 与 vbmeta_system 的 AVB 元数据来自 Xiaomi 10S Android13 基线，而不是明确为此 Android17 super 重新生成的描述符；BAT 对 A/B vbmeta 写入均带 --disable-verity。
- AVB 描述符与 super 内逻辑分区尺寸不一致：vbmeta_system 中 system 的描述符 ImageSize 为 1,188,585,472 B，而 system_a LP extent 为 978,804,736 B；product 描述符为 4,240,891,904 B，而 product_a extent 为 3,675,041,792 B。这个静态尺寸冲突需要按 AVB 元数据语义谨慎理解，但至少表明此包并非与 C30 相同的一套已验证 AVB/LP 产物；没有做设备端验证。
- super.img 是 6,683,588,156 B 的 sparse 文件，127 chunks，4096-byte block；LP 元数据版本 10.0、三份 metadata slot。解出的逻辑布局只填充 A 组：odm_a 128 MiB、product_a 3,675,041,792 B、system_a 978,804,736 B、system_ext_a 846,258,176 B、vendor_a 1,179,586,560 B；对应 B 组条目为空。
- C30 的 super 使用 LP metadata 10.2、virtual_ab_device、mi_ext_a，A 逻辑分区采用只读属性且分区/组尺寸不同。原始 10S 官方 A13 super 也有 virtual_ab/mi_ext 结构。第三方 super 不能被当作与 C30 同布局替换件。

## 5. 四方定点对照

| 项目 | 第三方 Milo 包 | 当前 C30 | K40 Android17 成功移植 | Xiaomi 15 donor |
|---|---|---|---|---|
| system/product | system/system_ext fingerprint 为 Xiaomi/missi，Android17 build CP2A.260605.016；product fingerprint 为 Xiaomi/thyme/miproduct、OS4.0.0.44.TGACNXM | 项目以 Xiaomi15 HyperOS4.0.0.8 Android17 system 为当前移植基线；C30 在其上添加诊断资产 | 项目报告确认以 Xiaomi15 HyperOS4.0.0.8 donor 内容为基础 | 本项目 donor 目标是 Xiaomi15/dada HyperOS4 Android17 |
| vendor/硬件栈 | vendor fingerprint 为 Xiaomi/thyme Android13 V816.0.4.0.TGACNXM；vendor build.prop 除 privapp 权限值外与本地 10S stock build.prop 行级一致，分区已重打包 | thyme 当前硬件栈与启动资产沿用项目已验证基线 | K40 使用 alioth 自己的低层硬件栈 | dada 是供体，不是 thyme 的硬件栈 |
| boot/kernel | boot/vendor_boot/dtbo 与 10S Android13 stock 完全相同；Linux 4.19.157 | thyme 内核/启动链；C30 修改重点为早期诊断 | K40 成功端使用其项目记录的定制 4.19.325 kernel | donor system，不等于 donor kernel 可直接用于 thyme |
| netd/Zygote | netd.rc 保留 netd restart 两条 Zygote 回调；netbpfload/libnetd_updatable 与 C30/K40 对应二进制完全相同 | C30 删除 netd→primary/secondary Zygote 两条 callback；保留其他已验证启动行为 | K40 netd.rc 与第三方相同；其成功不能证明第三方 stock 10S kernel 能通过同一路径 | donor 行为是基线，项目 C30 对回调有定点修改 |
| LP/AVB | A-only populated super 与 stock Android13 vbmeta 描述符并置，尺寸/layout 与 C30 不同 | C30 LP v10.2、virtual_ab_device、mi_ext、A partition readonly | K40 使用不同设备布局和专属 kernel/vendor | donor 镜像关系不等于本包的 AVB/LP 已重建 |

### 实际启动链比较

- 第三方 netd.rc SHA-256 `51039198c9ec69111b1f7f1c8257ae12ee0a677c14599a87416c5b24b112948b`，与 K40 对应 netd.rc 相同，包含 `onrestart restart zygote` 与 `onrestart restart zygote_secondary`。
- C30 netd.rc SHA-256 `ce706b53205492835be972de4381dc601297e4c0b211d3889c9c9e150428c5ee`；相对第三方/K40 的定点差异是移除上述两条 netd→Zygote 回调。
- init.zygote32.rc、init.zygote64_32.rc、init.zygote64.rc 在第三方、K40 和 C30 的提取版本哈希相同；primary 仍使用 critical window 配置，secondary 的 `onrestart restart zygote` 仍保留。
- 第三方的 netbpfload（102,536 B，SHA-256 `c6b2fdb0f68a8678899bd395546b77f6595c13109f50ccf380d1842f28db5f5`）与 C30、K40 完全相同；libnetd_updatable.so（103,648 B，SHA-256 `2c811151e99f227bc8e180f64f0b686e8d696b5323ce2f81313914cc597277ad`）也完全相同。第三方系统 /system/bin/netd 自身大小不同，但关键失败链二进制没有变化。
- 三方定点 CIL 查询中，第三方和 C30 的 netd/BPF 相关已检查规则一致；C30 另外有其诊断 domain/type 规则。未做全量 SELinux 语义比较，不能声称策略整体相同。
- K40 的成功样本具有不同的 K40 kernel/vendor 与移植环境。当前证据没有证明第三方包移植了 K40 的 4.19 修复，也没有发现它处理了项目 C30 已修改的 netd→Zygote 重启链。

### 来源可以确认到什么程度

system 的 build fingerprint 是 generic Xiaomi/missi Android17 build；product 是 thyme/OS4.0.0.44；vendor 是 10S thyme Android13 build；boot 与多项 firmware 是 10S Android13 stock。由此可判定它混用了 Android17 system/product 与旧 thyme 硬件底层，但不能从 fingerprint 独立证明该 system 的确切原始 donor 是 Xiaomi15/dada。Recovery updater 和 OTA metadata 指向其他设备，进一步降低了包内 provenance 的一致性。没有发现足够证据证明它直接包含 K40/alioth 成功移植包的硬件内容。

## 6. 是否有当前项目没有的有效兼容补丁

在本轮限定的 BPF/netd/Zygote/启动链范围内，没有找到能解决 C30 已知启动问题的新兼容补丁：

- netd/BPF 关键二进制与 C30/K40 相同；
- netd 对 Zygote 的重启回调仍存在；
- zygote init 定义并未显示修复 C30 panic/critical 链的新变化；
- kernel 是旧 10S 4.19.157，而不是 K40 的定制 4.19.325；
- vendor/firmware 沿用 10S Android13 路线；
- SELinux 检查未发现明确针对该 4.19 BPF 问题的新增规则。

这不等于对第三方所有图形、framework、SELinux 行为进行了全量比较；本轮按指令只做与当前早期启动阻塞相关的定点审计。

## 7. External Candidate 判定

**不建议，也不具备条件将本地 Milo 包认定为 External Candidate。没有创建 staging 目录或 Dry-Run 刷写脚本。**

阻止条件：

1. Recovery updater 明确针对 muyu，且有缺失固件源文件的直接块设备写路径。
2. Windows BAT 擦除 frp 和 super，写 modem、bootloader/启动固件、boot/vendor_boot/dtbo/recovery 以及两槽 vbmeta；选项 2 会擦 userdata 与 metadata，脚本自动 reboot。
3. 本地 super LP 结构及 stock Android13 vbmeta 与项目 C30 布局/Android17 描述符关系不一致。
4. 作者随后承认其先前分区映射有误，但尚未提供此次审计对象的修订包和准确的新映射；当前包不能因口头更正被视为已修复。
5. 项目 C30 当前的设备/槽位恢复资产虽有本地记录，但不能消除第三方包写入范围和来源不一致带来的风险。

本包确实含有标注 thyme 的 product 与 10S stock 硬件镜像，但这不足以证明完整、正确的 thyme A/B 安装方案，也不足以解释或修复当前 C30 的 PID1/Zygote 问题。若作者发布明确修订版，可按新包重新审计；需要提供版本标识、明确分区映射与更新的脚本/镜像。

## 8. 最终答复（按任务问题）

1. **包类型：** 自定义 Windows Fastboot 包与设备不匹配的 Recovery updater/过时 OTA metadata 混合物。
2. **总大小：** 49 个文件，7,602,127,591 B。
3. **images：** 上文列出 24 个镜像；super 为 sparse，见 IMAGE_AUDIT.csv。
4. **刷写脚本：** 根目录 `点我一键线刷.bat`；Recovery 侧为 `META-INF/com/google/android/update-binary`。
5. **BAT 写入：** 21 个 _ab 目标、4 个 vbmeta A/B 目标及 super；另有 frp/super erase、active A、自动 reboot。
6. **userdata/metadata：** BAT 菜单选项 2 擦除两者；Recovery updater 自身未发出擦除/格式化命令，但建议用户手动格式化 data。
7. **boot/vendor_boot/dtbo：** BAT 会写；Recovery updater 也写 A/B 节点。
8. **modem/persist/EFS/NV：** 明确写 modem firmware；未发现显式 persist、modemst、EFS/NV 写入命令。
9. **完整 thyme boot stack：** 镜像多与 stock 10S Android13 相符，但安装脚本相互不一致，且作者报告分区映射错误；不能判为可靠完整安装方案。
10. **system 来源：** fingerprint 为 generic missi Android17 build，精确 donor 尚不能确认。
11. **vendor 来源：** 10S thyme Android13 V816 stock lineage，重打包后与本地 stock build.prop 仅有已述差异。
12. **kernel 来源：** 10S stock Android13 boot，Linux 4.19.157。
13. **K40：** 没有直接 K40 kernel/vendor 适配证据；TWRP 属性中的 alioth 字样不是来源证明。
14. **Xiaomi 15：** 没有足够包内证据证明 system 直接来自 dada；build fingerprint 只指向 missi generic。
15. **Android17+4.19 netd：** 未解决；关键 netbpfload/libnetd_updatable 与当前 C30 相同。
16. **Zygote/init：** 保留 netd 重启 Zygote 回调；zygote rc 与 K40/C30 对应文件相同。
17. **critical window：** 没有发现与现有三方 zygote rc 不同的修复。
18. **secondary callback：** 保留 secondary→primary callback。
19. **PID1 fatal/recovery：** 未发现修复 C30 PID1 fatal 的新证据。
20. **SELinux：** 定点检查未见 BPF/netd 修复差异；没有全量比较。
21. **与 C30 主要差异：** 来源指纹混杂；旧 stock 4.19.157 kernel；super/AVB layout 不兼容；恢复/fastboot 刷写范围更广且会自动重启；netd 回调未删且无 BPF 修复。
22. **缺失兼容补丁：** 在本轮早期启动检查范围内未发现。
23. **External Candidate：** 不值得按当前包直接实机测试。
24. **应刷分区：** 本轮不给出可执行的刷写集；因此没有 staging/Dry-Run。
25. **恢复 C30：** 项目有 C30 资产记录，但本包覆盖面含低层固件/modem 和 super，且写入映射有争议；不足以把完整恢复路线当作已安全闭环。
26. **受限 Dry-Run：** 未生成，因为包未通过 Candidate 判定。
27. **设备操作：** 未向手机发送命令，未刷写/启动/擦除；C30 状态未改变。
28. **GitHub：** 发布后在项目执行记录中记录实际提交与公开验证结果。

## 附件与可复核清单

- `THIRD_PARTY_PACKAGE_MANIFEST.csv`：49 项文件逐项 size/hash/type。
- `IMAGE_AUDIT.csv`：24 个镜像的 size/hash/type/sparse/footer。
- `BAT_WRITE_PLAN.csv`：Fastboot BAT 的逐行命令计划。
- `RECOVERY_WRITE_PLAN.csv`：Recovery updater 的直接目标、缺失源文件与 super/cache 动作。
- `netd.rc.diff`：第三方/K40 与 C30 的两条回调差异。

原第三方包、本机提取分区、固件镜像、EXE/APK 和任何设备 raw 分区副本均未复制到公开报告目录。

**第三方 Milo HyperOS4 包已经完成离线审计；未执行其 exe/bat/apk，未向手机刷写任何内容；C30 当前状态保持不变。**
