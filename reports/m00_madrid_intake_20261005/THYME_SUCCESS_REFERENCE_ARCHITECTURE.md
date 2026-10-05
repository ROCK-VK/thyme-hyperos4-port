# THYME SUCCESS REFERENCE ARCHITECTURE — 成功包启动兼容架构审计

- 对象：`10S系统\BB解密-261002_移植Mi18pm-_HyperOS_4.0.15-for_thyme_A17`（**THYME Mi18PM Known-Good Port Baseline**）
- 生成时间：2026-10-05
- 状态：**第一版，含明确标注的未闭合项**。本文件由主窗口撰写；
  原计划的独立审计子代理在收尾阶段被中止，其已落盘证据（APEX 哈希矩阵、kernel config 实解、
  madrid 清单）已并入本文件与 `MADRID_PAYLOAD_INVENTORY.md`。
- 证据级别：`[A]` 真机 / `[B]` 静态文件 / `[C]` Known-Good 对照 / `[D]` 推断
- **未标注 `[A]` 的结论均不代表真机已验证。本机从未启动过这个包。**

---

## 0. 一句话结论

这个 port 能启动，靠的是**三层拼合 + 一套自包含启动 ramdisk**，
而**不是**靠某个单一的内核补丁：

```
madrid/missi 的 HyperOS 4 (OS4.0.15.0.XEOCNXM)   system / system_ext / product / system_dlkm
        +                                        (EROFS，与官方 madrid 4.0.19 的 APEX 36 个中 35 个逐字节相同)
thyme 自己重建的 vendor / odm / mi_ext            (ext4，A13 底座 + A17 重打包)
        +
TWRP/Magisk 派生的自包含 boot ramdisk             (50.6 MB，"它自己把 super 挂起来")
        +
社区 4.19.325 自定义内核                          (BPF_LSM / EROFS / ANDROID_VENDOR_HOOKS 全部 backport)
        +
thyme 第三方固件包                                (与 OurSky 包逐字节相同)
        +
AVB verification disabled                        (4096 B 空 vbmeta，Flags: 2)
```

---

## 1. A. Flash / Partition architecture

### 1.1 第三方原版脚本写什么（`YT_shuaji_xianshua.bat`，GBK 读取）`[B]`

原脚本共 **24 个 fastboot 写入 + 1 个 erase**，顺序为：
`erase boot_ab` → `boot_ab` → `set_active a` → `dsp_ab` / `xbl_config_ab` / `modem_ab` /
`vbmeta_system_ab` / `tz_ab` / `vbmeta_ab` / `bluetooth_ab` / `abl_ab` / `cmnlib_ab` / `cmnlib64_ab` /
`dtbo_ab` / `featenabler_ab` / `vendor_boot_ab` / `keymaster_ab` / `uefisecapp_ab` / `qupfw_ab` /
`xbl_ab` / `devcfg_ab` / `hyp_ab` / `imagefv_ab` / `aop_ab` → `flash super`
→（可选）`erase frp` / `erase userdata` / `erase metadata` → `set_active a` + **`fastboot reboot`**。
`flash cust_ab` 为条件分支，而包内**不存在 `cust.img`**，实际不执行。

完整矩阵、逐项 SHA256、以及本项目受控脚本的对比，见
`CONTROLLED_FLASH_MATRIX_AND_RISK.md`（本目录）。

### 1.2 固件层的真实归属 `[B]`

| 镜像 | 结论 |
| --- | --- |
| `abl` / `dtbo` / `imagefv` | 与官方 thyme `thyme_images_OS1.0.4.0.TGACNXM_13.0\images\` 对应文件 **SHA256 全等** |
| `aop`/`bluetooth`/`cmnlib`/`cmnlib64`/`devcfg`/`dsp`/`featenabler`/`hyp`/`keymaster`/`modem`/`qupfw`/`tz`/`uefisecapp`/`xbl`/`xbl_config` | 与 `OurSky_Mi10s_OS3.0.318.0.WPBCNXM_A16_b3334\firmware-update\` 对应文件 **SHA256 全等** |
| `vbmeta` / `vbmeta_system` | 均为 **4096 B**，`Algorithm: NONE`、`Flags: 2`、`Descriptors: (none)`，**两者哈希相同** |
| `vendor_boot` | 100,663,296 B，**与两个 thyme 参照包都不同** |

→ 成功包的固件层是**社区 thyme 固件包**，不是 donor 内容；AVB 为**重生成的空 vbmeta（校验已禁用）**。
**没有任何 madrid 固件进入这个包。** `[B]`

### 1.3 AVB handling

`Flags: 2` = `AVB_VBMETA_IMAGE_FLAGS_VERIFICATION_DISABLED`。
对照官方 madrid 4.0.19 `vbmeta.img`（12,288 B、`SHA256_RSA4096`、2 个 chain descriptor、20+ prop、`Flags: 0`）`[B]`。
→ 刷此包**不会引入 madrid 的公钥信任链，也不存在 rollback index 抬升导致无法回退的问题**。 `[B]`

---

## 2. B. Boot compatibility stack

### 2.1 内核 `[B]`

| | kernel 版本串 | 工具链 | `BPF_LSM` | `EROFS_FS` | `ANDROID_VENDOR_HOOKS` |
| --- | --- | --- | --- | --- | --- |
| **成功包** | `4.19.325-cxk-lxsclnb-g33d88af64048` | ZyC clang 16.0.6 | **y** | **y** | **y** |
| Legacy C47 | `4.19.325-perf-g45b9b954f074` | clang 21.0.0 | **y** | **y** | **y** |
| 官方 madrid 4.0.19 | `6.18.21-android17-5-…` | kleaf / clang 22 | 原生 | 原生 | 原生 |
| 官方 thyme OS1.0.4.0 | `4.19.157-perf-…` | clang 10 | **缺** | **缺** | **缺** |

**关键结论**：
- **`CONFIG_BPF_LSM` 与 `CONFIG_EROFS_FS` 才是"能不能跑 Android 17 userspace"的分水岭**，
  而它们来自 **4.19.325**（社区 backport），不是来自 4.19.157。
- **成功包与 C47 的内核同属 4.19.325 谱系且都已具备这些能力**，
  所以「旧 4.19 内核没有 BPF 能力 ⇒ netd 必失败」这一假设**不成立**。
- **官方 madrid 的 6.18.21 内核不可用于 thyme**（不同 SoC / DTB / 驱动）。 `[D]`
- **回退官方 thyme 4.19.157 内核不可行**：会同时丢掉 BPF LSM 与 EROFS。 `[B]`

### 2.2 启动 ramdisk 的真实性质 —— 本审计最重要的结构性发现 `[B]`

把成功包 `boot_noroot.img` 的 **50,637,560 B** ramdisk（gzip）解出 CPIO（展开 99,590,400 B）后实读：

```
prop.default:
  ro.product.system.device=alioth
  ro.product.system.model=Mi 10S
  ro.product.system.name=twrp_thyme
  ro.system.build.fingerprint=Xiaomi/twrp_thyme/alioth:15/SP2A.220405.004/sekaiacg12132152:eng/test-keys
  ro.system.build.type=eng
  # from /home/sekaiacg/opt/AOSP/AOSP_12/out/target/product/alioth/obj/PACKAGING/system_build_prop_intermediates/buildinfo.prop
```

ramdisk 内的关键条目：
`twrp_ramdisk-timestamp`、`twres/`、`init.recovery.qcom.rc`、`init.recovery.usb.rc`、
`init.recovery.hlthchrg.rc`、`libaosprecovery.so`、`libminuitwrp.so`、`libgpt_twrp.so`、`libtar.so`、
`customzip/Magisk/`、`magisk_prebuilt-timestamp`、`miui_prebuilt-timestamp`、
`ramdisk-files.txt`(110,955 B)、`ramdisk-files.sha256sum`(334,181 B)、
`first_stage_ramdisk/{avb/q-gsi.avbpubkey, r-gsi.avbpubkey, s-gsi.avbpubkey, system/bin/e2fsck}`、
`system/etc/init/hw/init.rc`、`system/etc/recovery.fstab`、`vendor/lib/modules/1.1/exfat.ko`。

**判读**：这是社区作者 `sekaiacg` 基于 TWRP 的 **recovery ramdisk**（并内建 Magisk 与 MIUI 预置），
被直接当作 `boot` 的 ramdisk 使用：**由它自己负责把 `super` 里的 dynamic partitions 挂起来，
再把控制交回标准的 `/system/etc/init/hw/init.rc`。**

这解释了成功包为什么 **`vendor_boot` 的 ramdisk 只有 2,180 B**：
first-stage 的挂载职责不在 `vendor_boot`，而在 `boot` 的大 ramdisk 里。

### 2.3 与 Legacy C47 的组织方式对比（互不兼容）`[B]`

| | 成功包 | Legacy C47 | 官方 madrid 4.0.19 |
| --- | --- | --- | --- |
| `boot` header | v3 | v3 | **v4** |
| `boot` kernel | 47,185,936 B | 53,436,440 B | 42,674,688 B |
| `boot` ramdisk | **50,637,560 B**（gzip，TWRP 派生自包含） | 3,564,549 B（legacy-LZ4） | **0** |
| `vendor_boot` header | v3 | v3 | **v4** |
| `vendor_boot` ramdisk | **2,180 B**（近空） | **23,340,130 B** | **76,143,885 B**（3 段：platform / recovery / "16K"） |
| `vendor_boot` dtb | 1,613,832 B | 1,424,301 B | 2,148,992 B |
| vendor cmdline | 官方 thyme 原版 | 大幅扩展（`fstab_suffix=qcom`、`init_fatal_panic=true`、`iptable_raw.raw_before_defrag=1` 等） | `video=vfb:… erofs.reserved_pages=64 nf_conntrack.hashsize=32768 … bootinfo.fingerprint=madrid:17/OS4.0.17.1.XEOCN:user` |

→ **三者的 boot/vendor_boot 职责划分完全不同**，刷写时不能只替换其中一侧。
→ madrid `vendor_boot` 的 4 个 DTB 全部 `qcom,board-id <0x00 0x00>`、`qcom,msm-id 0x2c3/0x2c4`、
机型名 "Art SoC / Art v2 / ArtP SoC / ArtP v2"；`dtbo.img` **只有 1 个 entry（id 0）**
→ **madrid 侧不存在基于 board-id 的面板/变体选择**，与 thyme 依赖 dtbo 面板选择的机制**根本不同**。 `[B]`

### 2.4 dtbo `[B]`

成功包 `dtbo.img`（33,554,432 B）与官方 thyme `OS1.0.4.0` 的 `dtbo.img` **SHA256 全等**
（`A0F550A32C15B95A6BA0BBE141976BAD905D23FC74367E3E3FF0F41BC90C6D3A`）。
→ **成功包没有改动 dtbo**，沿用官方 thyme 的面板选择结果。

---

## 3. C. Dynamic partitions

### 3.1 成功包 super 的真实结构 `[B]`

成功包 `super.img` = **9,126,805,504 B（8.5 GiB 整）**，
SHA256 `D05DC8DFDD7DCD54A319D0051BDD1BB9942F3E162C52B2272DFC585E0B314496`。

**它不是 sparse**，且 LP 元数据是**非 AOSP 布局**，因此 `simg2img`、`lpdump`、`lpunpack` 全部拒绝解析：

```
0x0000  全零填充
0x1000  LpMetadataGeometry  magic 0x616C4467 ("gDla")
0x2000  该 geometry 块的重复副本（AOSP 此处本应是 header → 这就是 lpdump 失败的原因）
0x3000  LpMetadataHeader     magic 0x414C5030 ("0PLA"), header_size=256, LP 10.2
0x3100  partitions 表（12 × 52 B）
0x3700  extents 表（6 × 24 B）
0x3a00  groups 表（3 × 48 B）
0x3b90  block_devices 表（1 × 64 B）
```

extent 语义经**文件系统 magic 实测验证**（ext4 `0xEF53` @+0x438 / EROFS `0xE0F5E1E2` @+1024）：

| extent | 分区 | 大小 (B) | 文件系统 | super 内偏移 |
| --- | --- | --- | --- | --- |
| 0 | `mi_ext_a` | 174,723,072 | **ext4** | 0x00100000 |
| 1 | `odm_a` | 2,351,104 | **ext4** | 0x0A800000 |
| 2 | `product_a` | 4,110,647,296 | EROFS | 0x0AB00000 |
| 3 | `system_a` | 959,201,280 | EROFS | 0x0FFC0000 |
| 4 | `system_ext_a` | 850,153,472 | EROFS | 0x138F00000 |
| 5 | `vendor_a` | 2,044,887,040 | **ext4** | 0x16BA00000 |

（`_b` 槽分区在元数据中 `num_extents = 0`，即本包**只填充了 A 槽**。）

### 3.2 文件系统类型本身就是架构证据 `[B]`

官方 madrid 4.0.19 的 `system / system_ext / product / vendor / odm / mi_ext` **全部是 EROFS**；
成功包的 `vendor / odm / mi_ext` 是 **ext4**。
→ 从文件系统层面再次印证：**成功包的 vendor 层不是 madrid 的，是 thyme 侧重做的**。

### 3.3 各分区身份（证明三层拼合）`[B]`

| 分区 | 身份读数 |
| --- | --- |
| `system_a` | `ro.product.system.device=missi`、`ro.build.flavor=missi-user`、`ro.system.build.fingerprint=Xiaomi/missi/missi:17/CP2A.260605.016/17OS4.0.260925.012628646.QCPECN.S:user/release-keys` |
| `system_ext_a` | 同 `missi` 谱系（`ro.product.system_ext.device=missi`） |
| `product_a` | **`ro.product.product.name=miproduct_madrid`**、`ro.product.build.fingerprint=Xiaomi/madrid/miproduct:17/CP2A.260605.016/OS4.0.15.0.XEOCNXM:user/release-keys` |
| `mi_ext_a` | **`ro.mi.os.version.incremental=OS4.0.15.0.XEOCNXM`**、`ro.product.mod_device=thyme`、`ro.vendor.build.ab_ota_partitions` 与 madrid 逐字符相同 |
| `vendor_a` | `ro.product.vendor.device=thyme`、`ro.product.vendor.marketname=Mi 10S`、`ro.product.board=thyme`、`ro.board.platform=kona`、`# from device/xiaomi/thyme/special_ro.prop` |
| `odm_a` | `ro.product.odm.device=thyme`、`model=M2102J2SC`、`marketname=Mi 10S`、`ro.odm.build.fingerprint=…V816.0.4.0.TGACNXM`（A13 字符串） |

### 3.4 与官方 madrid 4.0.19 的 A 层差分 —— APEX 逐包哈希矩阵 `[B]`

`work\madrid_m01_audit\apex_hash_matrix.txt`：

- `system/apex` 下 **36 个包中 35 个 SHA256 完全相同**
- 唯一差异：`com.android.virt.apex`，两者**大小同为 93,360,128 B**，哈希不同
  （成功包 `[REDACTED_DEVICE_ID]…0AE6` vs madrid `[REDACTED_DEVICE_ID]…230B`）
- `com.android.tethering.capex` 两包**相同**：`327C191797AC3CBFB4562DF5423AE0129A68A4F02F4D91B7171A526E861B1A35`
- `com.android.runtime.apex`（含 `linker64`）两包**相同**：`021646695BA127260EA9CC96DF6C924EDFEB86BA783781A9CC276DB232443FC4`
- `system_ext/apex`：`art.compatible` / `compos` / `vndk.v34` 三个**相同**；
  **成功包多出 `com.android.vndk.v30.apex`（114,769,920 B），madrid 没有**

**判读**：
- 二者的 system 层**共用同一 `missi` 平台构建谱系**，A 层替换不需要重做架构 → 支持
  「Known-good 4.0.15 port → upgrade to official madrid 4.0.19」的可行性。 `[B]`
- `com.android.vndk.v30.apex` 的存在与成功包的 **A13 vendor 底座**相关；
  替换 A 层时必须**同步评估 VNDK 组合**，不能只看版本号。 `[D]`

---

## 4. D. Network / BPF

### 4.1 事实 `[B]`

| 项目 | 成功包 |
| --- | --- |
| `com.android.tethering.capex` | 17,248,810 B，SHA256 `327C191797AC3CBFB4562DF5423AE0129A68A4F02F4D91B7171A526E861B1A35` |
| 其 `original_apex` | 36,724,736 B |
| 其 `apex_payload.img` | 36,421,632 B，**ext4**（非 EROFS），UUID `[REDACTED_DEVICE_ID]-9dfa-5edb-a43e-98e3a4d20250` |
| `lib64/libnetd_updatable.so` | 103,648 B，SHA256 `2C811151E99F227BC8E180F64F0B686E8D696B5323CE2F81313914CC597277AD`；`0x11534` 处**仍是未修补的 `cbnz w8, 0x115d8`** |
| `lib64/libnetd_resolv.so` | 2,482,912 B，SHA256 `FF9E1619C298A787748B8BB9ABFFBC3A9065E2CD8216B4C328EEECA192D737B5`；`0x1a92b8` 处**仍是未修补的 `cbnz w0, 0x1a9388`** |
| `/system/bin/netd` | 695,816 B，SHA256 `5B316597C9AD3FBB6B3E35DF04A10AEAC8C5A3730FDAE18E4060CE93F362661` |
| kernel BPF 能力 | `BPF_LSM=y`、`CGROUP_BPF=y`、`BPF_JIT=y`、`BPF_JIT_DEFAULT_ON=y`、`NET_ACT_BPF=y`、`NET_SCH_TBF=y`、`NET_CLS_MATCHALL=y`、`NETFILTER_XT_MATCH_BPF=y` |

### 4.2 「为什么成功包原版 netd 能跑」—— 目前能回答到什么程度

**已确认的** `[B]`：
1. `isAtLeast25Q2 && !isAtLeastKernelVersion(5, 4, 0)` 是**纯内核版本号比较**（`work\BpfHandler.cpp` 行 105），
   **不做任何 BPF 能力探测**。因此**内核 backport 多少 BPF 特性都不会让这个 gate 通过**。
2. 成功包携带的 `libnetd_updatable.so` 与 dada 参考副本 **`cmp` IDENTICAL**，
   且 `0x11534` 仍是未修补形态 → **「成功包打了补丁所以能跑」不成立**。
3. 成功包的 `com.android.tethering.capex` 与 madrid 4.0.19 **哈希相同** → 该 gate 是 4.0.x 共有代码。

**尚不能回答的** `[D]`（两种可能，均未验证）：
- **(i)** 成功包真机上 tethering CAPEX **同样没有成功激活**，`netd` 以"缺库"方式运行，
  根本不会执行到那两个 gate。C44 真机日志中的
  `netd: library "libnetd_updatable.so" not found` 为此提供了直接支持
  （`[A]`，来自 `日志\执行记录.md` 2026-10-04 18:00 条）。
  若成立，则成功包的"能启动"包含**网络子系统部分降级**，与其社区反馈的"功能问题"吻合。
- **(ii)** CAPEX 激活了，但 `netd` 走了与该 CAPEX 无关的初始化路径。

**判定方法**：M01 Known-Good 取证时，直接采集
`apexd` 的 CAPEX 激活日志、`netd` 的缺库报错、`service list | grep inetd`、`dumpsys connectivity`。
**这是决定 Legacy-C48A（`libnetd_resolv.so` `0x1a92b8` NOP）去留的唯一判据。**

### 4.3 不要默认的错误结论

- ✗「kernel config 一样 = 问题解决」——已证伪：C47 的内核同样具备 BPF_LSM。
- ✗「成功包靠 userspace 补丁跑通」——已证伪：两包该文件逐字节相同。
- ✗「换成正确内核后原版 `libnetd_*` 就一定能工作」——**未验证**，且由于 gate 是版本号比较，
  仅靠内核**不可能**通过该 gate；只有"该 gate 不被执行到"才可能。

---

## 5. E. HAL / VINTF

**未闭合。** 原计划的独立审计子代理在收尾阶段被中止，本项未产出。

已知的间接证据 `[B]`：
- 成功包 `vendor` 层来自 `device/xiaomi/thyme/...`（源码注释保留），`ro.board.platform=kona`，
  `ro.hardware.vulkan=adreno`、`ro.hardware.egl=adreno`、`ro.hardware.fp.fod=true`、
  `ro.vendor.display.type=oled` → **HAL 归属是 thyme，不是 madrid**。
- 成功包 `odm` 仅 2,351,104 B（madrid 的 odm 是 5,976,252,416 B）→ **成功包没有沿用 madrid 的 odm**。
- 成功包 `/system_ext/apex` 中多出的 `com.android.vndk.v30.apex` 指向 A13 时代 vendor 的 VNDK 需求。

**下一步需要做的**：比对成功包 vs C47 vs madrid 的 `vendor/etc/vintf/manifest.xml`、
`compatibility_matrix.*.xml`、`hwservice_contexts`、`vndservice_contexts`、以及
`vendor/lib64/hw/` 下的 HAL 实现清单。

---

## 6. F. SELinux

**未闭合。** 已知 `[B]`：成功包 boot ramdisk 内自带 `sepolicy`(610,156 B)、
`plat_file_contexts`(47,253 B)、`plat_property_contexts`(76,885 B)、
`file_contexts.bin`(1,154,282 B) 与 `file_contexts`(66,173 B)，
以及 `vendor_file_contexts`(11,617 B)；`odm_/product_/system_ext_*_contexts` 均为 **0 字节**。

→ `[D]` 这套策略是**跟 boot ramdisk 一起打包的**（TWRP 派生），
因此其 label 集合对应的是成功包自己的分区组合，**不能假定对 madrid 4.0.19 的 A 层成立**。
替换 A 层时必须同步核对 file_contexts / property_contexts / hwservice_contexts。

---

## 7. 已知缺口清单（本文件未闭合的部分）

| # | 缺口 | 需要什么 |
| --- | --- | --- |
| 1 | HAL / VINTF 逐项对照 | 独立审计（见第 5 节） |
| 2 | SELinux 策略逐项对照 | 独立审计（见第 6 节） |
| 3 | 成功包真机启动的**完整链路证据** | M01 Known-Good 取证（`getprop` / `lshal` / `dmesg` / `logcat` / `apexd` / `service list`） |
| 4 | tethering CAPEX 是否激活 | M01 取证（决定 Legacy-C48A 去留） |
| 5 | `com.android.virt.apex` 同尺寸不同哈希的具体差异位置 | 逐字节解包差分 |
| 6 | 成功包 `init.rc` / fstab（在 boot ramdisk 内）与 madrid 的差异 | 定点读取 + 比对 |
| 7 | super 内各 logical 分区的**设备端实际 LV 尺寸** | M01 取证的 `lpdump`（也是 M02 裁剪 madrid super 的输入） |
| 8 | Fastboot 写回 / 失败回滚演练 | 单独授权的回退演练 |

---

## 8. 证据来源索引

- 主报告：`SUCCESS_PORT_DONOR_IDENTITY.md`、`MADRID_PAYLOAD_INVENTORY.md`、`THREE_WAY_STRUCTURE_MAP.md`、
  `CONTROLLED_FLASH_MATRIX_AND_RISK.md`（均在本目录）
- 冻结数据：`work\reference_madrid_os4_0_19\`（66 镜像 / 14.9424 GiB + `IMAGE_INVENTORY.csv/.json`）、
  `work\reference_thyme_success_mi18pm_20261005\`（6 个 dynamic partition + `EXTRACT_MANIFEST.json`）
- 内核 config 实解：`work\madrid_m01_audit\ikconfig_{SUCC_boot_noroot,C47_boot,MADRID_boot_4.0.19,STOCK_THYME_boot}.txt`
- APEX 矩阵：`work\madrid_m01_audit\apex_hash_matrix.txt`
- 工具：`tools\extract_success_super.py`、`tools\parse_lp_metadata.py`、
  `tools\scan_identity_strings.py`、`tools\read_ext4_props.py`
- 刷写脚本：`tools\controlled_thyme_success_flash.ps1` + `.constants.json`（DRY-RUN 已 PASS，未执行）
