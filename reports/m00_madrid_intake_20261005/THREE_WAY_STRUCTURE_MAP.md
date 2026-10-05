# 三方结构地图：SUCC（Mi18PM Known-Good） vs 官方 madrid 4.0.19 vs Legacy C47

- 生成时间：2026-10-05
- 状态：**第一版，部分章节等待子代理审计回填**。已标注 `[PENDING]` 的条目为尚未闭合项。
- 证据级别：`[A]` 真机 / `[B]` 静态文件 / `[C]` Known-Good 对照 / `[D]` 推断

---

## 0. 三方身份一句话对照（决定性的第一组事实）

| | **SUCC**（Known-Good Port） | **官方 madrid 4.0.19** | **Legacy C47** |
| --- | --- | --- | --- |
| system 指纹 | `Xiaomi/missi/missi:17/CP2A.260605.016/17OS4.0.260925.012628646.QCPECN.S` | `Xiaomi/missi/missi:17/CP2A.260605.016/17OS4.0.261004.020338398.QCPECN.S` | `Xiaomi/custom_thyme/thyme:17/CP2A.260605.016/OS4.0.0.8.XOCCNXM` |
| product 指纹 | `Xiaomi/madrid/miproduct:17/CP2A.260605.016/OS4.0.15.0.XEOCNXM` | `Xiaomi/madrid/miproduct:17/…/OS4.0.19.0.XEOCNXM` | `[PENDING]` |
| mi_ext 版本 | `OS4.0.15.0.XEOCNXM`（smr_base `OS4.0.11.0`） | `OS4.0.19.0.XEOCNXM`（smr_base `OS4.0.17.0`） | `[PENDING]` |
| odm fingerprint | `Xiaomi/thyme/thyme:13/RKQ1.211001.001/V816.0.4.0.TGACNXM`（**A13 字符串**） | `Xiaomi/madrid/madrid:17/CQ2A.260712.001-CP2A.260605.016/OS4.0.17.1.XEOCN` | `[PENDING]` |
| vendor fingerprint | `Xiaomi/thyme/thyme:13/RKQ1.211001.001/V816.0.4.0.TGACNXM`（**A13 字符串**） | `Xiaomi/mivendor/mivendor:17/CQ2A.260712.001-CP2A.260605.016/OS4.0.17.1.XEOCN` | 采用官方 thyme A13 vendor `[D]` |
| 版本线代号 | **`XEOCNXM`（madrid 线）** | **`XEOCNXM`（madrid 线）** | **`XOCCNXM`（dada 线）** |
| donor | Xiaomi 18 Pro Max / `madrid` | Xiaomi 18 Pro Max / `madrid` | Xiaomi 15 / `dada` |

**关键判读**：`XE…` 与 `XO…` 是两条不同的机型版本线。SUCC 与官方 madrid 同线（`XEOCNXM`），Legacy C47 属于 `XOCCNXM`（dada）。这从版本号层面独立印证了 donor identity 审计的结论。 `[B]`

---

## 1. A. Kernel / Boot

| 项目 | SUCC | 官方 madrid 4.0.19 | Legacy C47 |
| --- | --- | --- | --- |
| `boot.img` 大小 | 134,217,728 B（`boot_noroot` / `_magisk` / `_alpha` / `_KSU` / `_apatch` 五个变体） | 100,663,296 B | 201,326,592 B |
| kernel 版本串 | `Linux version 4.19.325-cxk-lxsclnb-g33d88af64048 (root@cxk)`，`ZyC clang 16.0.6`，`#1 SMP PREEMPT Mon Sep 21 …` | `Linux version 6.18.21-android17-5-g1d099fcb35e0-abogki540753930-4k`，`kleaf@build-host`，`clang 22.0.1` | `Linux version 4.19.325-perf-g45b9b954f074 ([LOCAL_BUILD_HOST])`，`clang 21.0.0` |
| boot header | v3, `os_version 13.0.0`, `os_patch 2024-04`, cmdline 空 | v3（madrid 侧）`[B]` | v3, `os_version 17.0.0`, `os_patch 2026-08`, cmdline `panic=0` |
| kernel 段 SHA256 | `B9D1E524B3AED85C7D3F19DBD900A0E291EC9310A3B36DC47ADDAA29D20C621C` | `[PENDING]` | `6FDFFDBBE9BD65197B32A8A603C8548793F0CDF7C3CC3A1D6443C36121B62FA9` |
| boot ramdisk 大小 | 50,637,560 B | `[PENDING]` | 3,564,549 B |
| `vendor_boot.img` | 100,663,296 B；header v3；**vendor ramdisk = 2,180 B（几乎空）**；dtb 1,613,832 B | 134,217,728 B；`[PENDING]` | 100,663,296 B；header v3；**vendor ramdisk = 23,340,130 B（legacy-LZ4）**；dtb 1,424,301 B |
| vendor cmdline | 官方 thyme 原版（`console=ttyMSM0,115200n8 … video=vfb:640x400,… buildvariant=user`） | `[PENDING]` | 大幅扩展（含 `androidboot.fstab_suffix=qcom`、`androidboot.init_fatal_panic=true`、`iptable_raw.raw_before_defrag=1`、`deferred_probe_timeout=300` 等） |
| kernel config banner | `Linux/arm64 4.19.325` | `Linux/arm64 6.18.21`（GKI，Google 构建） | `Linux/arm64 4.19.325` |
| `CONFIG_BPF_LSM` | **y** | `[B]` 6.18 主线原生具备 | **y** |
| `CONFIG_EROFS_FS` | **y** | **y** | **y** |
| `CONFIG_ANDROID_VENDOR_HOOKS` | **y** | 现代 GKI 原生具备 | **y** |
| `CONFIG_BPF_JIT_DEFAULT_ON` | y | 原生 | y |
| `CONFIG_MODULE_SIG` | 未设置 | y | 未设置 |
| `CONFIG_LSM` | `"lockdown,yama,loadpin,safesetid,integrity,selinux,smack,tomoyo,apparmor,bpf"` | `"landlock,…,ipe,bpf"` | 未显式设置（legacy 默认） |

### 1.0 madrid 4.0.19 的 super 布局（子代理实测，`[B]`）

**该 OTA 内没有 `super.img`**；super 的几何信息在 `DeltaArchiveManifest` 的 **field 15**：

| 项目 | 值 |
| --- | --- |
| group | `qti_dynamic_partitions` |
| group `max_size` | 18,779,996,160 B（17.4924 GiB） |
| **super 分区大小（f15.9）** | **18,790,481,920 B（17.5021 GiB）** |
| 成员（9 个） | `odm`、`product`、`system`、`system_dlkm`、`system_ext`、`vendor`、`vendor_dlkm`、`mi_product`、`mi_ext` |
| 全部文件系统 | **EROFS**，4096 B 块，`LZ4_0PADDING`，元数据声明 **"required kernel 5.4"** |
| `mi_product` | **空壳**（只有 `ro.mi.version.mi_product=empty`，AVB 记录原始大小 4,096 B） |
| `abl` / `devcfg` | **payload 中不存在** |

`fstab.qcom`（vendor_boot vendor_ramdisk idx 0）把
`system/system_ext/product/mi_ext/vendor/vendor_dlkm/system_dlkm/odm` 以
`logical,first_stage_mount` 经 dm 挂载；**没有按名字挂载 `super`**；`mi_product` **不在 fstab 中**。 `[B]`

**对 thyme 移植的含义 `[D]`**：
- madrid 的 super 是 **17.50 GiB**；thyme 的 super 是 **8.5 GiB**（成功包）或 7.7 GB（C47）。
  → **madrid 的 super 完全放不进 thyme**，必须重新裁剪 dynamic partition 尺寸。
- EROFS 元数据写着 "required kernel 5.4"，而 thyme 侧是 4.19.325（带 EROFS backport）。
  成功包已证明 4.19.325 能挂载 madrid 侧 EROFS，**但 madrid 4.0.19 这一版尚未在 4.19 上验证过**。 `[D]`
- madrid `vendor_boot` 的 4 个 DTB 全部是 `qcom,board-id <0x00 0x00>`、`qcom,msm-id 0x2c3/0x2c4`、
  机型名 "Art SoC / Art v2 / ArtP SoC / ArtP v2" → **madrid 侧不存在基于 board-id 的面板/变体选择**，
  与 thyme 依赖 dtbo 面板选择的机制**机制不同**。 `[B]`

### 1.1 boot ramdisk 的真实性质（新发现，重要）

把 SUCC 的 50 MB boot ramdisk（gzip）解出 CPIO 后（99,590,400 B 展开）实读 `prop.default`：

```
ro.product.system.device=alioth
ro.product.system.model=Mi 10S
ro.product.system.name=twrp_thyme
ro.system.build.fingerprint=Xiaomi/twrp_thyme/alioth:15/SP2A.220405.004/sekaiacg12132152:eng/test-keys
ro.system.build.type=eng
ro.build.version.incremental=eng.sekaia.20241213.215331
# from /home/sekaiacg/opt/AOSP/AOSP_12/out/target/product/alioth/obj/PACKAGING/system_build_prop_intermediates/buildinfo.prop
```

ramdisk 内容特征：
- `twrp_ramdisk-timestamp`、`twres/`、`init.recovery.qcom.rc`、`init.recovery.usb.rc`、`libaosprecovery.so`、
  `libminuitwrp.so`、`libgpt_twrp.so`、`libtar.so` → **这是社区作者 `sekaiacg` 基于 TWRP 的 recovery ramdisk**
- `magisk_prebuilt-timestamp`、`customzip/Magisk/` → 内建 Magisk 注入
- `miui_prebuilt-timestamp`、`miui_prebuilt-timestamp` → 内建 MIUI 组件预置
- `ramdisk-files.txt`(110,955 B) + `ramdisk-files.sha256sum`(334,181 B) → 完整文件清单
- `first_stage_ramdisk/{avb/q-gsi.avbpubkey, r-gsi.avbpubkey, s-gsi.avbpubkey, system/bin/e2fsck}`
- `system/etc/init/hw/init.rc`（标准 Android init.rc）、`system/etc/recovery.fstab`
- `vendor/lib/modules/1.1/exfat.ko`

**判读 `[B]`**：SUCC 的启动方案是 **"TWRP/magisk 派生的自包含 ramdisk 直接作为 boot ramdisk"**，
由它自己负责把 super 里的 dynamic partitions 挂起来，再交回标准 `system/etc/init/hw/init.rc`。
这解释了为什么 SUCC 的 `vendor_boot` 只需要 2,180 B 的近空 ramdisk
（vendor/odm 的挂载与模块加载由 boot ramdisk 侧承担），也解释了其 `boot.img` 里携带 50 MB ramdisk。

**这条与 C47 形成鲜明对比**：C47 把 23.3 MB 的 first-stage ramdisk 放在 `vendor_boot` 里，
并按 AOSP 的 GKI 分工来组织；SUCC 则把全部负担压在 `boot` 里。
**两者不可逐项类比，刷写时也不能只替换其中一侧。**

### 结论（这是本次三方对照最重要的结论之一）

- **SUCC 与 C47 的 kernel 同属 4.19.325 谱系，且两者都已启用 `CONFIG_BPF_LSM`、`CONFIG_EROFS_FS`、`CONFIG_ANDROID_VENDOR_HOOKS`**。因此：
  - **「旧 4.19 内核没有 BPF 能力 ⇒ netd 必失败」这一假设不成立**：C47 用的内核本身已具备现代 BPF/LSM 能力。 `[B]`
  - 任务书中"如果 Known-Good 包通过 custom kernel / bpffs / cgroup / kernel BPF backport 让原版 netd 正常运行，则最终 madrid port 应优先复用正确 compatibility stack"的条件**已经部分满足**：custom kernel 已经存在且已在 C47 上运行过。 `[B]`
- 两者是**不同的构建**（不同版本串、不同构建者、不同工具链、不同 SHA256），所以不能假定内核完全相同。 `[B]`
- 与**官方 thyme 4.19.157** 相比，4.19.325 才是关键：官方 thyme 内核缺 `CONFIG_BPF_LSM`、缺 `CONFIG_EROFS_FS`、缺 `CONFIG_ANDROID_VENDOR_HOOKS`。**任何回退到官方 thyme 内核的方案都会同时丢掉 BPF LSM 与 EROFS**，不可行。 `[B]`
- **官方 madrid 4.0.19 的 6.18.21 内核无法用于 thyme**（不同 SoC、不同 DTB、不同驱动），donor 的 kernel 只能作为"上层需要什么"的参照。 `[D]`

### madrid 4.0.19 `vendor_boot` 实测（`[PENDING]` 已回填）

```
boot magic: VNDRBOOT
vendor boot image header version: 4          <-- 注意是 v4，不是 v3
page size: 0x00001000
kernel load address: 0x00008000
ramdisk load address: 0x01000000
vendor ramdisk total size: 76,143,885
vendor command line args: video=vfb:640x400,bpp=32,memsize=3072000 erofs.reserved_pages=64
    nf_conntrack.hashsize=32768 nosoftlockup console=ttynull qcom_geni_serial.con_enabled=0
    bootconfig bootinfo.fingerprint=madrid:17/OS4.0.17.1.XEOCN:user
    mi_mtdoops.fingerprint=madrid:17/OS4.0.17.1.XEOCN:user bootconfig
dtb size: 2,148,992
vendor ramdisk table: vendor_ramdisk00 (22,405,123 B, type 0x1)
                      vendor_ramdisk01 (29,988,606 B, type 0x2 "recovery")
                      vendor_ramdisk02 (23,750,156 B, type 0x0 "16K")
vendor bootconfig size: 311
```

→ madrid 的 `vendor_boot` 是 **header v4 + 76 MB 三段式 ramdisk（含 recovery / 16K 变体）**，
而 SUCC 与 C47 都是 **v3 + 单段 ramdisk**。**madrid 的 vendor_boot 结构在 thyme 上完全不适用。** `[B]`

### `[PENDING]` 待回填
- C47 `vendor_ramdisk`（legacy-LZ4，23.3 MB）的实际内容清单与 fstab
- C47 实际引导使用的是 boot 内 kernel 还是 vendor_boot 内 kernel（决定性）

---

## 2. B. Vendor / ODM

| 项目 | SUCC | 官方 madrid 4.0.19 | Legacy C47 |
| --- | --- | --- | --- |
| vendor 文件系统 | **ext4**（2,044,887,040 B） | **EROFS**（1,512,136,704 B） | 官方 thyme A13 vendor `[D]` |
| odm 文件系统 | **ext4**（2,351,104 B） | **EROFS**（5,976,252,416 B） | 官方 thyme A13 odm `[D]` |
| vendor identity | `ro.product.vendor.device=thyme`、`ro.product.vendor.marketname=Mi 10S`、`ro.product.board=thyme`、`ro.board.platform=kona` | `ro.product.vendor.device=mivendor`、`ro.product.vendor.name=mivendor_sm8950`、`ro.product.board=art` | `[PENDING]` |
| odm identity | `ro.product.odm.device=thyme`、`model=M2102J2SC`、`marketname=Mi 10S` | `ro.product.odm.device=madrid`、`model=M154FF`、`marketname=Xiaomi 18 Pro Max` | `[PENDING]` |
| 源码出处注释 | `from device/xiaomi/thyme/special_ro.prop` 保留 | — | `[PENDING]` |
| 构建日期 | `Wed Jun 5 14:36:38 UTC 2024`（与官方 A13 thyme odm 相同） | `OS4.0.17.1.XEOCN` 线 | `[PENDING]` |

**判读**：SUCC 的 vendor/odm **既不是 madrid 的，也不是新构建的**——其 `ro.vendor.build.date` 与 odm fingerprint 与官方 thyme `V816.0.4.0.TGACNXM`（Android 13）完全相同，但**文件系统换成了 ext4 并重新打包**，且 `ro.product.mod_device` 被改写为 `thyme`。 `[B]`

**这条对 C47 的含义（高价值）**：C47 与 SUCC 很可能**共用同一个"官方 thyme A13 vendor/odm"底座**，只是：
- C47：system 侧 = **dada（XOCCNXM）** 的 HyperOS 4 → **system/vendor 跨 donor、跨版本线**
- SUCC：system 侧 = **madrid（XEOCNXM）** 的 HyperOS 4 → **system 与 vendor 均来自 `XE…` 谱系**（vendor 的 V816 字符串是历史遗留标记，不代表其 ABI 是 A13）

`[D]` 推断：这正是 SUCC 的 `netd` 能跑而 C47 的 `netd` 崩的**首要候选差异**，且属于 **userspace compatibility 层**而非 kernel。

### `[PENDING]` 待回填
- C47 的 vendor/odm 实际哈希与身份属性
- SUCC vendor 的 VINTF manifest / HAL 清单 vs C47
- 两边的 `libnetd_updatable.so` / `libnetd_resolv.so` / `netd` 字节级对照（子代理审计中）

---

## 3. C. System / Framework

| 项目 | SUCC | 官方 madrid 4.0.19 | Legacy C47 |
| --- | --- | --- | --- |
| system 大小 | 959,201,280 B（EROFS） | 977,055,744 B（EROFS） | 1,092,616,192 B（EROFS） |
| system_ext | 850,153,472 B（EROFS） | 817,614,848 B（EROFS） | `[PENDING]` |
| product | 4,110,647,296 B（EROFS） | 5,667,659,776 B（EROFS） | `[PENDING]` |
| mi_ext | 174,723,072 B（**ext4**） | 173,858,816 B（**EROFS**） | `[PENDING]` |
| 版本增量 | `17OS4.0.260925.012628646.QCPECN.S` | `17OS4.0.261004.020338398.QCPECN.S` | `17OS4.0.260902.005534479.QCPECN.S` |
| build 时间 | 2026-09-25 | 2026-10-04 | 2026-09-02 |

**判读**：
- SUCC 与 madrid 的 system 层是**同一平台（missi）构建的不同日期产物**，日期差 9 天。 `[B]`
- C47 的 system 层来自 **dada 线**，且其 `ro.product.system.name=custom_thyme`（被改写）。 `[B]`
- 注意：C47 的 `system.img` 比 SUCC 与 madrid 都**更大**（1.09 GB vs 0.96/0.98 GB），符合"dada HyperOS 4 系统树 + 大量注入补丁"的特征。 `[D]`

### SUCC 与 madrid 同线版本的降级差分（任务 4 的核心）
`OS4.0.15.0.XEOCNXM`（SUCC）与 `OS4.0.19.0.XEOCNXM`（官方）之间相隔 4 个小版本。已确认的**同源标记**：
- `ro.vendor.build.ab_ota_partitions` 逐字符相同（70 项 madrid 专属分区布局） `[B]`
- product 指纹同构：`Xiaomi/madrid/miproduct` `[B]`
- mi_ext 指纹同构：`Xiaomi/madrid/mi_ext` `[B]`
- 均已确认的**差异**：版本号、smr_baseversion、构建日期、`ro.product.mod_device`（madrid → thyme，属移植适配）

`[PENDING]`：A 层（system/system_ext/product/）的逐文件差分需要 madrid 4.0.15 官方包；本机无该包。

---

## 4. D. Network / BPF

| 项目 | SUCC | 官方 madrid 4.0.19 | Legacy C47 |
| --- | --- | --- | --- |
| kernel BPF LSM | y | y | y |
| kernel EROFS | y | y | y |
| `/system/bin/netd` | **695,816 B**，SHA256 `5B316597C9AD3FBB6B3E35DF04A10AEAC8C5A3730FDAE18E4060CE93F362661`，**未见 4 字节 NOP 补丁特征** `[B]` | `[PENDING]` | 695,440 B；**已打 4 字节 NOP**（`0x761c0` `cbnz w0` → `nop`），pre-patch SHA256 `[REDACTED_DEVICE_ID]…9E7D`，post-patch `[REDACTED_DEVICE_ID]…C8AD` `[B]` |
| tethering CAPEX | **17,248,810 B**，SHA256 `327C191797AC3CBFB4562DF5423AE0129A68A4F02F4D91B7171A526E861B1A35` `[B]` | `[PENDING]` | 17,314,320 B；C46 统一后 SHA256 `[REDACTED_DEVICE_ID]…48C9` `[B]` |
| CAPEX 内 `libnetd_updatable.so` | **103,648 B**，SHA256 `2C811151E99F227BC8E180F64F0B686E8D696B5323CE2F81313914CC597277AD`；`0x11534` 处**仍是未修补的 `cbnz w8, 0x115d8`**（编码 `28 05 00 35`） `[B]` | `[PENDING]` | 同一文件；**C43 已在 `0x11534` 打 4 字节 NOP** `[B]` |
| CAPEX 内 `libnetd_resolv.so` | **2,482,912 B**，SHA256 `FF9E1619C298A787748B8BB9ABFFBC3A9065E2CD8216B4C328EEECA192D737B5`；`0x1a92b8` 处**仍是未修补的 `cbnz w0, 0x1a9388`** `[B]` | `[PENDING]` | 同一偏移；**Legacy-C48A 计划在此打 NOP（当前不构建）** `[B]` |

### 4.1 决定性发现：`libnetd_updatable.so` 在两个包里**逐字节相同**

```
SUCC  CAPEX original_apex → apex_payload.img(ext4) → /lib64/libnetd_updatable.so
      103,648 B  SHA256 2C811151E99F227BC8E180F64F0B686E8D696B5323CE2F81313914CC597277AD
dada  参考副本 libnetd_updatable_dada.so
      103,648 B  SHA256 2C811151E99F227BC8E180F64F0B686E8D696B5323CE2F81313914CC597277AD
      → cmp 结果：IDENTICAL
```

且反汇编实读确认 SUCC 该文件在 `0x11534` 处是 `cbnz w8, 0x115d8`（原始未打补丁形态）。 `[B]`

**这条事实的含义（重要，且纠正了此前的归因方向）**：
既然 SUCC 携带的是**同一份未打补丁**的 `libnetd_updatable.so`，那么"SUCC 靠打了补丁所以能跑"这一解释**不成立**。
`isAtLeast25Q2 && !isAtLeastKernelVersion(5, 4, 0)` 在 4.19 内核上返回的 `Status` 必然是非 OK，
**除非 `BpfHandler::init()` 根本没有被调用到那一步**，或者 `libnetd_updatable.so` 根本没有被 `netd` 加载。

C44 首启日志为此提供了直接线索（`[A]`，来自 `日志\执行记录.md` 2026-10-04 18:00 条）：
`netd: library "libnetd_updatable.so" not found` —— **在 tethering CAPEX 未能激活的情况下，
`netd` 会因为找不到这个库而根本不执行那段 `init`**。

**因此需要区分的两种可能（未验证）**：
- **(i)** SUCC 的 tethering CAPEX 在真机上**同样没有成功激活**，`netd` 以"缺库"方式运行，
  绕过了两个 gate —— 那么 SUCC 的"成功"包含了**网络子系统部分降级**（这与其社区反馈的
  "功能问题"吻合）。 `[D]`
- **(ii)** SUCC 的 tethering CAPEX 激活了，但 `netd` 走了另一条与该 CAPEX 无关的 BPF 初始化路径。 `[D]`

**结论：`BpfHandler` 版本门与 `libnetd_resolv` 断言这两处是否仍需 NOP 旁路，取决于真机上
tethering CAPEX 的实际激活状态。这必须用真机证据回答，不能用静态分析替代。**

### 4.2 已确认：这个 gate 是**纯内核版本号比较**，与内核实际 BPF 能力无关

`work\BpfHandler.cpp`（AOSP 源码，行 78–107）原文：

```cpp
static Status initPrograms(const char* cg2_path) {
    if (!cg2_path) return Status("cg2_path is NULL");
    if (!isAtLeastT) return Status("S- platform is unsupported");
    if (!isAtLeastKernelVersion(4, 9, 0))  return Status("kernel version < 4.9.0 is unsupported");
    if (isAtLeastU && !isAtLeastKernelVersion(4, 14, 0)) return Status("U+ platform with kernel version < 4.14.0 is unsupported");
    if (isAtLeastU && !!strcmp(cg2_path, "/sys/fs/cgroup")) return Status("U+ platform with cg2_path != /sys/fs/cgroup is unsupported");
    if (isAtLeastV && !isAtLeastKernelVersion(4, 19, 0)) return Status("V+ platform with kernel version < 4.19.0 is unsupported");
    // 25Q2 bumps the kernel requirement up to 5.4
    if (isAtLeast25Q2 && !isAtLeastKernelVersion(5, 4, 0)) return Status("25Q2+ platform with kernel version < 5.4.0 is unsupported");
    ...
```

判读 `[B]`：
- 这是**编译期/运行期的内核版本号数字比较**，**不做任何 BPF 能力探测**。
- 因此：**无论 4.19 内核 backport 了多少 BPF 特性，这个 gate 都不会因此通过。**
- 这直接修正了任务书第四节第二类的判断依据：C43/C47 的 NOP 属于
  **"userspace 版本门旁路"**，而非"绕过缺失的 BPF 能力"；把它归类为"仅历史 hack"是不准确的，
  它命中的是 AOSP 的硬编码版本下限。
- 但**是否需要**它，仍由第 4.1 节的真机问题决定。 `—`

### 4.3 kernel 侧能力对照（用于排除"内核缺能力"解释）

| CONFIG | SUCC `4.19.325-cxk` | Legacy C47 `4.19.325-perf` | 官方 thyme `4.19.157` |
| --- | --- | --- | --- |
| `CONFIG_BPF_LSM` | y | y | **MISSING** |
| `CONFIG_EROFS_FS`（含 XATTR/ZIP/SECURITY/ACL） | y | y | **MISSING** |
| `CONFIG_ANDROID_VENDOR_HOOKS` | y | y | **MISSING** |
| `CONFIG_BPF_JIT_DEFAULT_ON` | y | y | MISSING |
| `CONFIG_NET_ACT_BPF` | y | `[PENDING]` | **MISSING** |
| `CONFIG_NET_SCH_TBF` / `NET_CLS_MATCHALL` | y | `[PENDING]` | **MISSING** |
| `CONFIG_DM_USER` / `DM_BOW` | y | `[PENDING]` | **MISSING** |
| `CONFIG_MODULE_SIG` | MISSING | MISSING | y |

→ 内核能力**不是** SUCC 与 C47 的分水岭；**回退到官方 thyme 4.19.157 内核不可行**（会同时丢掉 BPF LSM 与 EROFS）。 `[B]`

---

## 5. E. SELinux / init / VINTF

`[PENDING]` — 由子代理审计回填。

---

## 6. F. Firmware

| 项目 | SUCC | 官方 madrid 4.0.19 | Legacy C47 |
| --- | --- | --- | --- |
| 固件策略 | 包内自带**第三方 thyme 固件**（与 OurSky 包逐字节相同） `[B]` | donor 自带 madrid 固件（不可用于 thyme） | 未刷写固件（沿用设备既有） `[C]` |
| `abl` / `dtbo` / `imagefv` | 与官方 thyme `OS1.0.4.0` 逐字节相同 `[B]` | madrid 专属 | 未改写 |
| `aop`/`bluetooth`/`cmnlib`/`cmnlib64`/`devcfg`/`dsp`/`featenabler`/`hyp`/`keymaster`/`modem`/`qupfw`/`tz`/`uefisecapp`/`xbl`/`xbl_config` | 与 OurSky thyme 固件包逐字节相同 `[B]` | madrid 专属 | 未改写 |
| `vbmeta` | 4096 B，`Flags: 2`（verification disabled），`Algorithm: NONE` `[B]` | 12,288 B，`SHA256_RSA4096`，2 chain descriptor `[B]` | 131,072 B `[B]` |
| `vbmeta_system` | 4096 B，与 `vbmeta.img` 同哈希 `[B]` | 4,096 B `[B]` | 131,072 B `[B]` |

**判读**：三方的固件层互不通用。**任何把 madrid 固件刷进 thyme 的方案都是明确禁止项。** `[B]`

---

## 7. 三方结构地图总结（一图流）

```
                         ┌─────────────────────────────────────────────┐
                         │  A 层：Android 17 / HyperOS 4 系统框架        │
                         └─────────────────────────────────────────────┘
   SUCC (Known-Good)  ──▶  madrid/missi  XEOCNXM  OS4.0.15  (2026-09-25)   ★ 同线
   MADRID 4.0.19      ──▶  madrid/missi  XEOCNXM  OS4.0.19  (2026-10-04)   ★ 同线
   Legacy C47         ──▶  dada          XOCCNXM  OS4.0.0.8 (2026-09-02)   ✗ 异线

                         ┌─────────────────────────────────────────────┐
                         │  B 层：vendor / odm / HAL / VINTF            │
                         └─────────────────────────────────────────────┘
   SUCC               ──▶  thyme 官方 A13 底座 + 重打包为 ext4 + mod_device=thyme
   MADRID 4.0.19      ──▶  madrid mivendor (EROFS, 6.18 kernel era)
   Legacy C47         ──▶  官方 thyme A13 vendor/odm（推测与 SUCC 同底座）

                         ┌─────────────────────────────────────────────┐
                         │  C 层：kernel / boot / firmware              │
                         └─────────────────────────────────────────────┘
   SUCC               ──▶  4.19.325-cxk        + thyme 固件包 + 官方 thyme vendor cmdline
   MADRID 4.0.19      ──▶  6.18.21-android17   + madrid 固件      (不可移植)
   Legacy C47         ──▶  4.19.325-perf (locally built) + 未改固件   + 自建 vendor_ramdisk
```

**核心结论**：
1. C47 与 SUCC 的**差距不在 kernel，而在 A 层 donor 线与 B 层 vendor 一致性**。 `[B]`+`[D]`
2. SUCC 的价值集中在 **B 层（thyme adaptation layer）** 与 **C 层的 boot/vendor_boot 组合**；A 层可以直接换成官方 madrid 4.0.19。 `[B]`
3. C47 的 `libnetd_*` NOP 链**是否仍需保留**，取决于第 4 节第 3 条那个开放问题的答案。在答案出现前，**不构建 Legacy C48**。 `—`
