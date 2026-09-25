# K40 三方移植逆向取证（Phase 1）

## 状态

`REVERSE_ENGINEERING / IMAGE_READY=false / DEVICE_WRITE_STOP`

本轮是主机端、只读、低内存的包级取证。目标是从“官方 K40 旧底 + 小米15官方 OS4 donor + K40 成功移植结果”中提取移植方法，再迁移到 Xiaomi10S/thyme；不是把 K40 二进制直接复制到 thyme。

## 输入与格式

| 角色 | 输入 | 已确认格式/规模 |
|---|---|---|
| `PORT_REFERENCE_BASE` | `[LOCAL_PROJECT_ROOT]/K40官包_15澎湃4/alioth_images_OS1.0.10.0.TKHCNXM_13.0` | 官方 alioth Android13 线刷目录；`images/super.img` 7,877,133,784 bytes，为 sparse；`boot.img` 134,217,728；`vendor_boot.img` 100,663,296；`dtbo.img` 33,554,432；有 `metadata.img`、`partition.xml`、`rawprogram0-5.xml` 和官方脚本。 |
| `PORT_REFERENCE_DONOR` | `[LOCAL_PROJECT_ROOT]/K40官包_15澎湃4/dada-ota_full-OS4.0.0.8.XOCCNXM-user-17.0-f6a0447d15` | 小米15/dada Android17 Recovery/OTA；`payload.bin` 8,702,335,155 bytes，CrAU；`payload_properties.txt` 记录 payload size 8,702,335,155、metadata size 318,826；已完成单 worker 选择性提取七个 userspace logical partition，临时输出已清理。Phase1 仍只作为 userspace donor。 |
| `PORT_REFERENCE_RESULT` | `[LOCAL_PROJECT_ROOT]/OS4移植包_K40_12X/MiaoMiaoRom_红米k40_OS4.0.0.8` | K40 成功移植包；`super.img.zst` 5,108,797,958 bytes；`firmware-update/boot.img` 201,326,592、`vendor_boot.img` 100,663,296、`dtbo.img` 33,554,432；带自定义 `一键线刷.bat`。P1 曾一次性临时解压 raw super 只读 metadata，随后已删除。 |

12X 包只作已有来源/方法交叉参考；PixelOS 是救援/调试参考，Sky 是历史参考。二者均不进入本轮 K40 三方二进制来源链。

## 已观察到的 K40 结果差异（来源未证明）

- `boot.img`：官方和移植结果都是 Android boot header v3，但文件大小从 `134,217,728` 变为 `201,326,592`。这是可复现的包级差异，分类保持 `UNKNOWN`；不能证明是 porter 修改、重编 kernel、重打包、填充或多种操作的哪一种。
- `vendor_boot.img`：两者均为 VNDRBOOT v3、外层均 `100,663,296` bytes；有界头字段中的 vendor ramdisk size 从 `2238` 变为 `2283`。这是观察到的头字段差异，分类保持 `UNKNOWN`；不能证明 first-stage 文件、fstab 或 fs_mgr 的来源。
- `dtbo.img`：两者外层均 `33,554,432` bytes、表项数均 29；DTBO table `total_size` 从 `13,415,446` 变为 `13,415,454`。这是观察到的表级差异，分类保持 `UNKNOWN`；不能推出具体 panel、board ID 或显示修复。
- `super` 交付形态：官方是 raw sparse `super.img`；移植结果当前只看到 `super.img.zst`，脚本会先解压为 `super.img`。这是观察到的分发形态差异，逻辑分区内容和来源尚未读取。
- 刷机方法：移植脚本检查 `alioth`，对 `super.img.zst` 做解压，使用 `--disable-verity --disable-verification`，擦除 boot/vendor_boot/dtbo/recovery 双槽，再刷 firmware、两槽低层和 super，最后激活 a 槽。该事实证明 porter 修改了部署方法；不等于证明每个二进制的来源。
- 包完整性疑点：脚本引用 `recovery.img`，但在当前有界 `firmware-update` 清单中未看到该文件。不能因此自行生成或借用 recovery。

## 尚不能证明的内容

当前没有足够证据判断：

- K40 成功移植的 kernel 是沿用、重编、重打包还是来自第三方；没有看到 kernel source、defconfig、DTS、cmdline 或构建清单。
- DTB、DTBO overlay、modules、panel/display HAL、VINTF、SELinux、linker、provider/ABI 的真实来源和闭环。
- `vbmeta` 描述符、签名策略和 `super` 逻辑分区的具体来源；P1 只临时读取 liblp metadata，未运行 `lpunpack`，未展开逻辑分区，也未保留 raw super。
- 小米15 OTA 中哪些文件被 K40 porter 实际取用；本轮已读取 CrAU manifest/partition list，但未提取 payload 分区。

因此，来源分类中未闭合的项必须保持 `UNKNOWN`，不能凭文件名、目录名或“能启动”倒推来源。当前仅自定义 `一键线刷.bat` 的部署、AVB 和 slot 行为有直接证据，可分类为 `PORTER_MODIFIED`；image envelope/table/wrapper 的差异本身不升级为来源结论。`PORTER_REBUILT`、`PORTER_NEW` 本轮没有足够证据。

## P1 元数据 owner slice 已完成

### K40 port dynamic-partition metadata

- 对 `super.img.zst` 做了一次串行 zstd 解码，临时 raw super 为 `9,126,805,504` bytes；只读取 liblp geometry/header/table，未运行 `lpunpack`，未展开任何 system/vendor/product 文件系统。
- geometry 位于临时 raw offset `4096`：`gDla`、metadata max `65,536`、metadata slots `3`、logical block `4096`。metadata header 位于 offset `12288`：`0PLA`、major/minor `10/0`、header `128`、tables `848`。
- 表为 `10` partitions、`5` extents、`3` groups、`1` block device；block device 名为 `super`，first logical sector `2048`，alignment `1,048,576`，声明大小 `9,126,805,504` bytes。groups 为 `default`、`qti_dynamic_partitions_a`、`qti_dynamic_partitions_b`，后两者各 max `9,126,805,504` bytes。
- 当前 metadata slot 的 A 侧有 `odm/product/system/system_ext/vendor` 单 extent 条目；B 侧名称存在但 extent count 为 0。该结论仅是表事实，不是文件系统或运行时结论。

### Xiaomi15 OTA manifest

- `payload.bin` 为 CrAU v2；manifest `318,802` bytes，metadata signature `267` bytes；属性文件报告 payload `8,702,335,155` bytes、metadata `318,826` bytes。
- manifest 只读解析出 `48` 个 partition update。列表包含 `boot/vendor_boot/dtbo/vbmeta/recovery`，以及 `odm/product/system/system_ext/vendor/system_dlkm/vendor_dlkm/mi_product/mi_ext` 等。
- dynamic-partition metadata 为一个 `qti_dynamic_partitions` group，max `11,800,674,304` bytes，分区名为 `odm/product/system/system_dlkm/system_ext/vendor/vendor_dlkm/mi_product/mi_ext`；version/source `1/1`、COW `3`、压缩 `lz4`、block `65,536`、VABC `1`。另有 `42` 个 ApexInfo，security patch 字段为 `2026-08-01`。
- 这些是 donor OTA 的 metadata/partition shape，不证明 K40 porter 使用了每个文件，也不改变 thyme 的 hardware/kernel/vendor/odm owner 边界。

解析依据为 AOSP `liblp` metadata format；本地 stage 中保留的 TSV/MD 是本轮实际读取结果，不保留 raw super。

## P2 provenance / owner contract 对齐已完成

### FACT：K40 stock physical geometry

- XML sector size is `4096` bytes. `super` allocation is `8,912,896 KB` / `2,228,224` sectors / `9,126,805,504` bytes, while the packaged sparse file is `7,877,133,784` bytes.
- `metadata` allocation is `16,384 KB` / `4,096` sectors / `16,777,216` bytes, while the packaged sparse file is `49,228` bytes.
- `boot_a/b` slots are each `196,608 KB` / `49,152` sectors / `201,326,592` bytes; the stock `boot.img` file is `134,217,728` bytes and B filename is empty.
- `vendor_boot_a/b` slots are each `98,304 KB` / `24,576` sectors / `100,663,296` bytes. `dtbo_a/b` slots are each `32,768 KB` / `8,192` sectors / `33,554,432` bytes.
- The stock package uses `rescue`/`rescue.img`, not `recovery`/`recovery.img`: allocation is `131,072 KB` / `32,768` sectors / `134,217,728` bytes, packaged file is `41,036` bytes. This does not prove rescue and recovery are interchangeable.

### METHOD EVIDENCE and NOT PROVEN

- Stock physical `super` allocation equals the K40 port P1 liblp declared device size. This is a geometry alignment fact, not proof of logical partition or binary provenance.
- K40 port metadata has `qti_dynamic_partitions_a/b`, the five-name A/B family `odm/product/system/system_ext/vendor`, and no independent `mi_ext`/`mi_product` entry. Xiaomi15 donor metadata has nine logical names including `mi_ext` and `mi_product`, plus `system_dlkm`/`vendor_dlkm`.
- The donor manifest has `48` updates, group max `11,800,674,304`, `lz4`, block `65,536`, COW `3`, VABC `1`. Existing build.prop/provenance remains declaration-only evidence for alioth/K40 low-level and missi/dada OS4 user-space shape.
- It is not proven which donor payload files the porter used, whether `mi_ext` was deleted/moved/merged/functionally replaced, or where kernel/display/provider binaries came from.

The detailed alignment and requirement tables are `p2_provenance_owner_alignment.tsv` and `p2_thyme_requirement.tsv`; the standalone report is `[LOCAL_PROJECT_ROOT]/work/reports/20260918_K40_THREE_WAY_P2_PROVENANCE_OWNER_CONTRACT_1.md`.

## P3 exact-thyme owner gap delta 已完成

本轮只读取既有小型 owner 报告和 P2 requirement 表：官方 A13 thyme、Sky A16、Pixel A17 native control/rescue，以及既有 M33 kernel/display owner closure。没有读取 K40/Xiaomi15 大文件，没有解码、提取、构建或设备操作，也没有重新判断 M29 的历史根因。

- 官方 A13 thyme 是 exact-thyme 的 hardware/firmware/boot/vendor_boot/DTBO/fstab/AVB owner 参考，但仅有 Android13/OS1 证据。
- Sky A16 是 exact-thyme 的历史 HyperOS/可启动低层参考，但不是 A17/OS4 owner。
- Pixel A17 是 exact-thyme 的 Android17 native control/rescue；已有独立 runtime 的 `boot_completed=1`、Launcher、核心服务和 green/locked 只证明 Pixel native contract，不证明 HyperOS4 provider/MIEXT owner。
- 17U、K40、Xiaomi15 只保留 OS4 userspace 形态或方法参考，不提供可直接复用的 thyme 低层 owner。

P3 gap 表 `p3_thyme_owner_gap_delta.tsv` 将当前边界固定为：

- `KEEP_THYME_BLOB`：hardware/firmware/persist/slot，以及 physical super/slot/AVB 载体边界；
- `REBUILD_FOR_THYME`：boot/kernel/cmdline、DTB/DTBO/panel、modules ABI、vendor_boot/fstab/fs_mgr；
- `REIMPLEMENT_FOR_THYME`：display/provider ABI、VINTF/SELinux、linker namespace、MIEXT/resolver/services；
- `DONOR_USERSPACE`：system/system_ext/product 仅作为用户空间 donor 形态，仍需 exact-thyme provenance/runtime closure；
- `UNKNOWN`：OS4 super/AVB 的 exact-thyme provenance。

`REBUILD_FOR_THYME`/`REIMPLEMENT_FOR_THYME` 是目标要求，不是已有源码、来源闭合或可构建性证明。当前仍为 `MISSING_TARGET_CONTRACT`，不能生成 candidate 或刷写物。独立报告为 `[LOCAL_PROJECT_ROOT]/work/reports/20260918_P3_THYME_OWNER_GAP_DELTA_1.md`。

## P4 exact-thyme A17/OS4 owner input inventory 已完成

P4 是一次性、有限范围的输入盘点：只检查已知目录的顶层/有限深度文件名、现有 `source_map.tsv` 和报告索引；没有递归扫描 K40/Xiaomi15 大包，没有读取 `payload.bin`/`super.img` 内容，没有下载、解码、提取、构建或设备操作。

- 没有发现新的、明确声明为 exact-thyme + Android17/OS4 的 kernel、vendor_boot、DTB/DTBO、panel、modules、first-stage/fstab/fs_mgr、display/provider、VINTF/SELinux/linker、MIEXT/services 或 matching super/AVB owner/source 输入。
- 官方 A13 thyme、Sky A16、Pixel A17 均是已有 reference；17U、K40/alioth、Xiaomi15/dada 均是非 thyme 的 donor/method/userspace-shape reference，不能升级为 target owner。
- 机器可读清单为 `[LOCAL_PROJECT_ROOT]/work/reports/20260918_P4_EXACT_THYME_OWNER_INPUT_INVENTORY_1.md`。
- 结果固定为 `NO_NEW_EXACT_THYME_INPUT`。不自动创建 P5，不重复制造静态审计任务；继续保持 `MISSING_TARGET_CONTRACT / IMAGE_READY=false / DEVICE_WRITE_STOP`，直到出现新的可追溯 exact-thyme A17/OS4 owner/source 输入。

## K40 kernel/display evidence slice 已完成

本轮按审核纠正继续 K40 三方主线，只读取 K40 官方旧底与 K40 port 结果的 `boot/vendor_boot/dtbo` 及有限 ramdisk/模块/display 证据；没有读取 K40 `super` 逻辑分区，没有读取/解包 Xiaomi15 `payload.bin`，没有构建或操作设备。

- 两者 boot 都是 v3、OS `13.0.0`、patch `2024-04`、bounded cmdline 为空；但 kernel payload 从 stock `50,579,472` bytes / `4.19.157-perf-g92c089fc2d37` 变为 port `47,222,800` bytes / `4.19.325-cip135-st19-aptusitu-perf-ga8adb96703d6`，编译链和构建时间也不同。kernel 来源/是否重编保持 `UNKNOWN`，没有升级为 `PORTER_REBUILT`。
- port boot ramdisk 与 stock 差异很大，且出现 OrangeFox/recovery 形态、`magiskboot`/`mmgui`/`zstd`/`lz4` 以及 port-only display-config 库；这些是静态 recovery ramdisk 线索，不是正常 Android display provider 运行证明。
- vendor_boot 两者都是 v3，vendor cmdline、header size `2112`、DTB size `1,613,832` bytes 的 bounded 字段相同；port vendor ramdisk `2238→2283` bytes，fstab 直接新增 system/system_ext/product/vendor/odm/mi_ext 六条 EROFS first-stage 行，同时保留 ext4 行。该 fstab delta 仅作为 `PORTER_MODIFIED` 的观察层事实。
- DTBO 两者都是 29 项、ID/rev/custom 全零；table `total_size` `13,415,446→13,415,454`，entry 顺序变化，size multiset 只观察到 `484,181→484,189`，可读 panel/display token 集合没有新增。DTBO 来源/重编/选择仍为 `UNKNOWN`。
- 四个被有限展开的 ramdisk 中没有 `.ko`、`modules.load` 或 `modules.dep`；这不能推断 vendor/odm/system_dlkm 中不存在模块。kernel/display 字符串都含 `msm_drm`、`mdss`、`sde`、`dsi_display`，没有 IKCONFIG/defconfig/source commit 闭环。

机器可读表为 `[LOCAL_PROJECT_ROOT]/work/reports/20260918_K40_KERNEL_DISPLAY_EVIDENCE_SLICE_1.md`。详细分类遵守既有 `FROM_K40_STOCK / PORTER_MODIFIED / PORTER_NEW / REMOVED / UNKNOWN` 语义，不把尺寸差异直接写成重编或来源证明。

## K40 three-way adaptation map 已完成

本轮只把已证实的 K40 stock→port 事实映射到既有 thyme owner/gap 表，未新增大文件读取或设备动作。机器可读表为 `[LOCAL_PROJECT_ROOT]/work/reports/20260918_K40_THREE_WAY_ADAPTATION_MAP_SLICE_1.md`。

- kernel payload/version 差异保持 `UNKNOWN`，thyme 面为 `REBUILD_FOR_THYME`；禁止把 K40 kernel 列为可复制物。
- K40 六条 EROFS first-stage 行的抽象语义可作为 `DIRECT_LOGIC_PORT` 方法假设，但实际 thyme fstab/fs_mgr 必须从官方 A13 owner 重新 `REBUILD_FOR_THYME`，不复制 alioth 行。
- Recovery/OrangeFox/display-config 静态线索不是 normal Android display provider owner；对应 thyme 面为 `NOT_APPLICABLE` 或 `REIMPLEMENT_FOR_THYME`。
- vendor_boot bounded header/DTB-size 相同但 DTB bytes 未比；官方 thyme A13 vendor_boot/DTB 只能作为 owner input，最终 A17/OS4 vendor_boot/ramdisk/fstab 应 `REBUILD_FOR_THYME`，不能把 A13 二进制当最终结果；DTBO/panel、modules、provider/VINTF/SELinux/linker、AVB/super provenance 分别保持 device-specific 重建或 `UNKNOWN`。
- Xiaomi15 仍仅为 `DONOR_USERSPACE`；本轮没有授权任何 K40/Pixel/Sky 低层二进制复制，也没有生成 thyme candidate。

## K40 contract/provenance slice 已完成

本切片只读取已有 K40/12X 小型 init、contexts、VINTF、SELinux、MIEXT、provider closure 和既有报告，未读取/解包 K40 `super` 逻辑分区或 Xiaomi15 `payload.bin`。机器可读表为 `[LOCAL_PROJECT_ROOT]/work/reports/20260918_K40_CONTRACT_PROVENANCE_SLICE_1.md`。

- mqsasd、su_daemon、spu_service、authsecret、displayfeature 均有静态 init/context/policy 或 matrix 线索，但 ELF、DT_NEEDED、linker、完整 VINTF provider 和 runtime registration 仍未闭合；有界缺失不等于删除。
- K40/12X 的共同 init/contexts/matrix/policy 形状不能升级为 `PORTER_REBUILT` 或运行成功证明；12X vendor manifest 的 `psyche_fod.xml`/`fx.tunnel` 差异单独标为 `DEVICE_SPECIFIC`。
- MIEXT 维持“metadata 无独立 entry、fstab/init/overlay/bind/context 消费者仍存在”的 `UNKNOWN` 边界；通用 `overlay`/`resolver` service contexts 不构成 MIEXT-specific resolver 闭环。
- K40 stock owner、Xiaomi15 donor、K40 fstab direct delta、K40 recovery display-config port-only paths 分别保留 `FROM_K40_STOCK`、`FROM_XIAOMI15_DONOR`、`PORTER_MODIFIED`、`PORTER_NEW` 的最小使用范围；`PORTER_REBUILT`/`REMOVED` 本切片不分配。
- K40→thyme 状态只使用批准枚举；主线仍不是 `ADAPTATION_DESIGN_READY`、`THYME_BUILD_READY` 或 candidate 许可。

## K40 AVB / super provenance slice 已完成

本切片只读四个小型 `vbmeta`/`vbmeta_system`、已有 K40 stock XML/P1 liblp/P1 Xiaomi15 manifest 结果和 K40 一键线刷脚本文本；没有解码 payload 数据区、没有运行 `lpmake`/`lpunpack`、没有生成 candidate 或操作设备。机器可读表为 `[LOCAL_PROJECT_ROOT]/work/reports/20260918_K40_AVB_SUPER_PROVENANCE_SLICE_1.md`。

- K40 stock top-level/system vbmeta 均为 `flags=0`；K40 port 两个实际文件均为 `flags=3`，均为 `SHA256_RSA2048`，保留 `vbmeta_system` chain（top-level rollback location 2）和完整 hash/hashtree descriptor。实际 port 不是历史 staging/device-backup 的 `flags=2` 空壳探针，也不是无 descriptor 容器。
- stock→port 直接可见变化为 flags `0→3`、descriptor salts/digests 和部分 image size/property 变化；public-key SHA-1、algorithm、rollback index、chain 拓扑和 descriptor 分区名称保持。该范围可标 `PORTER_MODIFIED`，但没有 build/source 证据证明 `PORTER_REBUILT`，也没有直接删除证据证明 `REMOVED`。
- K40 port liblp super size `9126805504` 与 stock physical super allocation 对齐；port 当前只有五个 A-side logical names、无独立 `mi_ext/mi_product` entry；Xiaomi15 donor manifest 则是更大的 group、九个 logical names。它们是 geometry/shape 关系，不能升级为逻辑内容或 donor 二进制来源证明。
- 一键线刷脚本的 `--disable-verity --disable-verification`、双槽擦除/刷写、`set_active a` 是方法证据，不能替代镜像 descriptor。port `metadata.img` 在有界清单中缺失也不标 `REMOVED`。
- K40→thyme 继续遵守：physical super/metadata/slot/AVB carrier 保持 thyme owner (`KEEP_THYME_BLOB`)；目标 vbmeta descriptors/rollback/key policy 必须 `REBUILD_FOR_THYME`；Xiaomi15 仅 `DONOR_USERSPACE`；未知 provenance 保持 `UNKNOWN`。
- 本切片仍不能推进到 `ADAPTATION_DESIGN_READY`，不生成 thyme candidate，不刷写手机。

## K40 port logical identity slice 已完成

本切片先复用既有小型 logical/build identity/合同证据，没有重复解压 `super.img.zst`，没有创建新 raw super 或逻辑镜像。机器可读表为 `[LOCAL_PROJECT_ROOT]/work/reports/20260918_K40_PORT_LOGICAL_IDENTITY_SLICE_1.md`。

- 五个 A-side logical 分区均已有 `+0x400=[REDACTED_DEVICE_ID]` 的 EROFS 证据：`odm=614400`、`product=3198853120`、`system=904327168`、`system_ext=909021184`、`vendor=1162989568` bytes；extent 起点和大小来自既有 liblp 表。
- identity 交叉核对成立：system/system_ext 为 Android17 `missi`/OS4 形状，product 为 `dada/miproduct` OS4.0.0.8，vendor/odm 为 `alioth`/Redmi K40 低层声明。build.prop 是内容事实和 donor 线索，不是逐文件来源证明。
- 既有 bounded contract 证据显示 system_ext/vendor 的 init/VINTF/SELinux 路径存在，vendor_boot fstab 保留 ext4/EROFS 双套 first-stage、MIEXT bind/overlay；product/odm/linker 的部分路径未保留，均保持 UNKNOWN，不把未保留写成删除。
- K40 port metadata 没有独立 `mi_ext/mi_product/system_dlkm/vendor_dlkm` entry，但 `/mi_ext`/MIEXT 消费者仍存在；Xiaomi15 donor 有这些 logical names。差异不能推出删除、合并或逐文件 donor 来源。
- `PORTER_MODIFIED` 仅保留给直接 fstab 方法 delta；没有 `PORTER_REBUILT` 或 `REMOVED` 的直接证据。K40→thyme：low-level vendor/odm `KEEP_THYME_BLOB`，OS4 userspace shape `DONOR_USERSPACE`，fstab/fs_mgr `REBUILD_FOR_THYME`，MIEXT/provider/linker/VINTF/SELinux `REIMPLEMENT_FOR_THYME`，未闭合 provenance `UNKNOWN`。
- 本切片补强了内容身份和合同形状，但不能推进到 `ADAPTATION_DESIGN_READY`，不生成 candidate，不刷写手机。

## Xiaomi15 donor selective content slice 已完成

本切片第一次在不展开低层分区的前提下读取 donor 的真实用户空间镜像。机器可读表为 `[LOCAL_PROJECT_ROOT]/work/reports/20260918_K40_DONOR_SELECTIVE_CONTENT_SLICE_1.md`。

- payload manifest 确认 `system/system_ext/product/mi_ext/mi_product/system_dlkm/vendor_dlkm` 七个名字均存在；使用 `payload-dumper-go -c 1 -no-verify -p ...`，没有提取 boot/vendor/vendor_boot/dtbo/firmware。
- 七个输出均为 EROFS，`+0x400=[REDACTED_DEVICE_ID]`。system 为 `976527360` bytes，system_ext 为 `823607296`，product 为 `4334202880`，mi_ext 为 `170819584`，mi_product 为 `348160`，system_dlkm 为 `[REDACTED_DEVICE_ID]`，vendor_dlkm 为 `[REDACTED_DEVICE_ID]`。
- donor system/system_ext/product 的高层 identity 与已保存的 K40 port `missi/miproduct/OS4` 声明有重合；这是有效的 donor 交叉线索，不是逐文件 provenance。donor 的 mi_ext/mi_product/system_dlkm/vendor_dlkm 形状也被直接观察到，但 K40 port 的无独立 entry 不能据此标为 `REMOVED` 或合并。
- donor system_dlkm/vendor_dlkm 的模块身份为 Xiaomi15/dada、6.6 Android15；它们不是 exact-thyme owner，thyme 面保持 `REBUILD_FOR_THYME`。system/product/system_ext 继续是受限 `DONOR_USERSPACE`，MIEXT/MI product 继续 `REIMPLEMENT_FOR_THYME`。
- 本切片没有 `PORTER_REBUILT`、`REMOVED` 或 runtime 成功证据；继续保持 `REVERSE_ENGINEERING / IMAGE_READY=false / DEVICE_WRITE_STOP`，不生成 candidate、不刷写手机。

## K40 port ↔ Xiaomi15 donor contract crosscheck 已完成

本切片复用既有 K40 port 的小型 build.prop、system/system_ext/vendor 的有限 init/VINTF/SELinux/MIEXT/fstab 证据，与 donor TSV 做少数合同交叉；没有重新解压 K40 `super.img.zst`，没有读取 donor payload 数据区。机器可读表为 `[LOCAL_PROJECT_ROOT]/work/reports/20260918_K40_PORT_DONOR_CONTRACT_CROSSCHECK_1.md`。

- `system`、`system_ext`、`product` 的关键 build identity 归为 `DIRECT_MATCH`；它们证明静态声明/高层形状重合，不证明逐文件 donor 来源。K40 product 的 `ro.build.ROM=MiaoOS` 在选定属性比较中归为受限 `PORTER_ONLY`，不升级为 `PORTER_REBUILT`。
- system/system_ext 的有限 VINTF/SELinux/init 目录形状分别有 `DIRECT_MATCH`；product 的 init/VINTF/SELinux/linker 只在 donor 侧被直接保留，归为有界 `DONOR_ONLY`，不把 K40 未保留写成缺失。linker、MIEXT、mi_product 和 dlkm 的 entry/路径差异继续保留 `DONOR_ONLY` 或 `UNKNOWN`。
- K40 port vendor_boot fstab 的六条 EROFS first-stage 行和 MIEXT bind/overlay 是 `PORTER_ONLY` 的方法证据，provenance 仍仅限 `PORTER_MODIFIED`；donor 选择性范围没有读取 vendor_boot/fstab。
- 关系分类只是证据侧关系：`DONOR_ONLY` 不等于删除，`PORTER_ONLY` 不等于重建，`DIRECT_MATCH` 不等于来源证明。本切片没有新增 `PORTER_REBUILT`/`REMOVED` 或 runtime/启动证据。
- K40→thyme 保持：userspace `DONOR_USERSPACE`；MIEXT/MI product/linker/provider `REIMPLEMENT_FOR_THYME`；fstab/fs_mgr、system_dlkm/vendor_dlkm `REBUILD_FOR_THYME`；硬件 owner 与 AVB/slot carrier 结论不变。

## K40 kernel/display donor compare 已完成

本切片只对 Xiaomi15/dada donor 的 `boot/vendor_boot/dtbo` 做了单 worker、`-no-verify` 的选择性提取，读取 Android/VNDRBOOT/DTBO 头、有限 kernel/ramdisk/fstab/display 字符串和 DTBO 表项；没有提取 vendor/odm/modules/firmware，也没有复制 donor 低层文件。机器可读表为 `[LOCAL_PROJECT_ROOT]/work/reports/20260918_K40_KERNEL_DISPLAY_DONOR_COMPARE_1.md`。

- donor `boot/vendor_boot` 为 v4，kernel 为 `6.6.118`/clang 18，DTBO 为单 entry；K40 stock/port 为 v3、4.19 kernel family、vendor_boot header 2112/DTB 1613832 bytes、DTBO 29 entries。就已观察的包级 envelope、kernel family 和 DTBO 数量而言，K40 port 更接近 K40 stock；这不是 source/rebuild provenance 证明。
- donor 有界 fstab 观察到 8 个选定 logical 名称的 ext4/EROFS 形状（含 dlkm）；K40 port 六条 EROFS first-stage delta 仍只能标为 `PORTER_MODIFIED`，不能由尺寸或行差异升级为 `PORTER_REBUILT`。donor 有限非 module 路径查询没有单独 display provider 路径；K40 port recovery display-config 路径是静态 `PORTER_NEW` 线索，不是 normal Android runtime 证明。
- 该切片的来源、defconfig/DTS、display provider、VINTF/SELinux/linker 和 runtime closure 仍为 `UNKNOWN`；K40→thyme 的 kernel/vendor_boot/fstab/DTB/DTBO/modules/display provider 继续分别 `REBUILD_FOR_THYME` 或 `REIMPLEMENT_FOR_THYME`，donor 低层不作为 owner。

## 官方 thyme A13 owner baseline contract slice 已完成

本切片只建立官方 `thyme_images_OS1.0.4.0.TGACNXM_13.0` 的 A13 owner baseline，复用已有小型官方 vendor_boot/fstab 提取物；未解包逻辑分区、未生成 raw super、未提取 vendor/odm。机器可读表为 `[LOCAL_PROJECT_ROOT]/work/reports/20260918_THYME_OWNER_BASELINE_CONTRACT_SLICE_1.md`。

- 官方 boot 为 v3，kernel payload `52,654,096` bytes、ramdisk `19,850,726` bytes、Android 13/2024-04；bounded kernel string 为 `4.19.157-perf-g92c089fc2d37`、clang 10。官方 vendor_boot 为 v3/header `2112`/DTB `1,613,832` bytes，A13 fstab 为 active 35、first-stage 7、logical 6、AVB 6、ext4 9、EROFS 0、MIEXT 18、overlay 17、bind 1。
- 官方 DTBO 为 `33,554,432` bytes、29 entries、magic `0xD7B7AB1E`、total `13,415,454`；官方顶层/system vbmeta 均 `SHA256_RSA2048`、flags `0`，rollback 分别 `0`/`1709251200`，并保留 A13 thyme/missi 声明及 hash/hashtree descriptor。
- 官方 sparse `super.img` 的直接 `lpdump` 在不生成 raw 的前提下返回 invalid geometry/exit `66`；历史静态报告仍提供 sparse 文件 `7,882,016,224` bytes、逻辑容量 `9,126,805,504` bytes、4096 block、404 chunks 的形状参考，但本切片不把它写成已闭合 liblp metadata/extent 事实。
- A13 只作为 exact-thyme hardware/boot/AVB carrier owner input；K40 的 fstab/MIEXT 只保留抽象方法映射，A17/OS4 的 kernel、vendor_boot/fstab、DTB/DTBO、modules、provider/VINTF/SELinux/linker、super/AVB 仍须 `REBUILD_FOR_THYME`/`REIMPLEMENT_FOR_THYME`。本轮未达到 `ADAPTATION_DESIGN_READY`。

## thyme A13 ↔ PixelOS A17 debug contract diff 已完成

本切片只复用并有限读取 PixelOS A17 thyme 的 `boot/vendor_boot/dtbo`、kernel、ramdisk/fstab 及 `system/etc` 的有限 VINTF/linker 路径，与官方 thyme A13 owner baseline 对照。PixelOS 角色固定为 `RESCUE_ONLY / A17_DEBUG_REFERENCE`，不读取或复制其 vendor/odm/super/firmware，不把它升级为 HyperOS4 owner。机器可读表为 `[LOCAL_PROJECT_ROOT]/work/reports/20260918_THYME_A13_PIXEL_A17_DEBUG_CONTRACT_DIFF_1.md`。

- A13 与 Pixel A17 都是 boot/vendor_boot v3/header 2112、4.19 kernel family；但 kernel/compiler、vendor ramdisk、DTB、DTBO entry 数量和 fstab/MIEXT 合同均变化。Pixel A17 是 native control/rescue 差分，不是 OS4 target binary 来源。
- A13 fstab 有 MIEXT AVB mount、bind、17 overlay；Pixel A17 为 14 active/5 AVB/ext4 logical rows，无 MIEXT、bind、overlay。这个差异证明两套 owner contract 不能拼接；OS4 的 MIEXT/provider 需 `REIMPLEMENT_FOR_THYME`。
- Pixel 有界 boot-service VINTF 只有 AIDL boot control，`ld.config.txt` 明确 recovery scope，SELinux/完整 VINTF/linker/provider closure 未闭合；Pixel native 历史 `boot_completed` 只证明 native A17 控制链。
- A13→Pixel 对照没有达到 `ADAPTATION_DESIGN_READY`，不改变 `REVERSE_ENGINEERING / MISSING_TARGET_CONTRACT / IMAGE_READY=false / DEVICE_WRITE_STOP`。

## ADAPTATION-DESIGN-GATE-REVIEW-1 已完成

本轮只汇总已审核的 K40 三方报告/TSV、官方 thyme A13 owner baseline 和 A13→PixelOS A17 debug diff；没有读取大文件、构建、生成 candidate 或操作设备。正式交付为：

- 报告：[LOCAL_PROJECT_ROOT]/work/reports/20260918_ADAPTATION_DESIGN_GATE_REVIEW_1.md
- 机器可读汇总：[LOCAL_PROJECT_ROOT]/work/stage_c_adaptation_design_gate_review_1/adaptation_design_gate_review.tsv
- K40 方法摘要 15 条，逐条区分事实、方法证据和 UNKNOWN；kernel/display 明确不能证明 PORTER_REBUILT。
- K40→thyme matrix 明确拆分 WHY、SM8250 方法共性、alioth 专属和 thyme 实现；Pixel/Sky/K40/Xiaomi15 低层均不升级为 thyme owner。
- 第一版架构保留 exact-thyme carrier/provider/policy owner，OS4 userspace 只作为 DONOR_USERSPACE 形态，MIEXT 只允许完整 PRESENT 或 ABSENT 闭合。
- Top 3 blocker 为 exact-thyme A17/OS4 owner input 缺失、FS/MIEXT contract 未决、display/provider 与 AVB/super runtime 未闭合。
- 唯一下一项为 THYME-A17-OS4-OWNER-SOURCE-INTAKE-1；若没有新的可追溯 owner/source 输入，只记录 NO_NEW_EXACT_THYME_INPUT 后停止。

准入判断保持 REVERSE_ENGINEERING / MISSING_TARGET_CONTRACT / IMAGE_READY=false / DEVICE_WRITE_STOP，没有新增 PORTER_REBUILT 或 REMOVED，也没有进入 THYME_BUILD_READY。

## THYME-A17-OS4-OWNER-SOURCE-INTAKE-1 已完成

本轮只盘点已登记的本地路径、P4 owner-input inventory、中央 source map 和小型审核报告，没有大范围递归扫描、读取 payload/super 数据区、解包、构建或操作设备。

- 报告：[LOCAL_PROJECT_ROOT]/work/reports/20260918_THYME_A17_OS4_OWNER_SOURCE_INTAKE_1.md
- TSV：[LOCAL_PROJECT_ROOT]/work/stage_c_thyme_a17_os4_owner_source_intake_1/thyme_a17_os4_owner_source_intake.tsv
- 结果：NO_NEW_EXACT_THYME_INPUT。官方 A13、Sky A16、Pixel A17 native、K40/alioth、Xiaomi15/dada、17U 均保持 reference/donor 角色，没有新同 build exact-thyme Android17/OS4 owner/source bundle。
- 覆盖面：boot、kernel、vendor_boot、DTB/DTBO、fstab/fs_mgr、display/provider、VINTF、SELinux、linker、AVB/super manifest 均没有新增目标合同。
- 门禁：继续 REVERSE_ENGINEERING / MISSING_TARGET_CONTRACT / IMAGE_READY=false / DEVICE_WRITE_STOP；不生成 candidate，不构建，不刷写，不自动创建下一项静态扫描。

## K40 → thyme 迁移约束

- thyme 官方 A13 包继续是 `TARGET_HARDWARE`：硬件、firmware、persist、slot、DTB/DTBO、vendor/odm 的 owner。K40/alioth 低层包不得直接复制。
- 小米15/dada OS4 只作为 Phase1 userspace donor。不能把 OTA 的低层、签名、vendor、odm 当作 thyme owner。
- K40 成功包只提供“porter 做了哪些包级改动/部署动作”的方法证据。thyme 后续必须重新建立 exact-thyme 的 kernel、vendor_boot/fstab、DTB/DTBO/panel、modules、provider/ABI、VINTF/SELinux/linker 与 AVB/slot 合同。
- PixelOS/Sky 旧路线不再构成 HyperOS4 mainline candidate。旧报告仍保留为历史事实，但不能被恢复成当前候选。

## 本轮产物与验证

证据表位于 `[LOCAL_PROJECT_ROOT]/work/stage_c_thyme_a13_pixel_a17_debug_contract_diff_1/`。这些文件只保存小型路径、格式、差异、分类、缺口、输入索引、低层证据摘要和 owner 映射；本 logical identity slice 没有新建 raw super 或逻辑镜像。

本轮未构建、未运行 `lpmake`/`lpunpack`、未展开 K40 逻辑分区、未刷机、未重启、未擦除、未切槽。K40 kernel/display slice 只对 boot/vendor_boot/dtbo 做了有限解包和 ramdisk/表项读取，临时解包目录在收尾删除；K40 `super.img.zst` 仅曾一次性临时解压用于 metadata 读取，raw super 已删除；本 donor slice 只选择性提取七个用户空间 payload 分区，临时输出/属性提取目录在收尾删除，未读取 donor 低层分区。未触碰 Docker VHDX，未执行 `wsl --shutdown`，未计算 standalone SHA-256。

资源门禁：本 donor slice 开始前 Free RAM 约 `12.99 GiB`、Free Commit 约 `33.21 GiB`，C/D/E 可用约 `110.69/194.72/191.80 GiB`；payload worker 固定为 1，未触发 `5 GiB` 门禁。收尾已确认目标 worker=0、临时目录已删除；最终 Free RAM `12.62 GiB`、Free Commit `33.15 GiB`、C/D/E 可用约 `110.70/194.72/191.73 GiB`。

## 当前最小任务收尾

`K40-THREE-WAY-ADAPTATION-MAP-SLICE-1`、`K40-CONTRACT-PROVENANCE-SLICE-1`、`K40-AVB-SUPER-PROVENANCE-SLICE-1`、`K40-PORT-LOGICAL-IDENTITY-SLICE-1`、`K40-DONOR-SELECTIVE-CONTENT-PROVENANCE-SLICE-1`、`K40-PORT-DONOR-CONTRACT-CROSSCHECK-1`、`K40-KERNEL-DISPLAY-DONOR-COMPARE-1`、`THYME-OWNER-BASELINE-CONTRACT-SLICE-1` 和 `THYME-A13-PIXEL-A17-DEBUG-CONTRACT-DIFF-1` 已完成主机侧有界取证。donor 选择性内容、少数合同关系、kernel/display 近邻结论、官方 A13 owner baseline 和 A13→A17 debug diff 已补齐，但 exact-thyme A17/OS4 owner contract、逐文件 provenance、provider/runtime closure 与 sparse super liblp 直读仍未闭合；当前不生成 candidate，等待审核批准新的最小变量。

继续保持 `REVERSE_ENGINEERING / IMAGE_READY=false / DEVICE_WRITE_STOP`；不生成 thyme candidate，不刷写手机。

## 2026-09-18｜K40 port implementation decomposition supersedes the waiting gate

本节是对前述“等待 exact-thyme owner/source”门槛的当前替代，不删除历史结论：owner/source intake 已确认没有新输入，因此路线改为自行重建方法与目标合同，而不是继续等待。

- 当前阶段：`REVERSE_ENGINEERING / NO_PREBUILT_TARGET_OWNER / IMPLEMENTATION_RECONSTRUCTION_REQUIRED / IMAGE_READY=false / DEVICE_WRITE_STOP`。
- 已完成顺序：`kernel → DTB/DTBO → modules → display → vendor_boot/fstab` 的 bounded selective decomposition。
- 新产物：`work/stage_c_k40_port_implementation_decomposition_1/k40_lowlevel_provenance.tsv`、`work/stage_c_k40_port_implementation_decomposition_1/thyme_reconstruction_map.tsv`、`work/reports/20260918_K40_PORT_IMPLEMENTATION_DECOMPOSITION_1.md`。
- 关键修正：当前直接 kernel string 证据显示 K40 stock build line 为 2025-10-29；旧报告写作 2024 的记录保留为历史，但不再作为当前事实。
- 当前结论：K40 port 可以提供低层改造方法证据；port kernel 仅 `PORTER_REBUILT_POSSIBLE`，DTB/DTBO/fstab/display static contract 可作直接差异证据，均不能升级为 exact-thyme owner。
- 唯一下一阶段建议：`THYME_KERNEL_BUILD_PLAN_READY`；只写 thyme kernel source/config/DTS/ABI 计划，不编译、不生成镜像、不写设备。
