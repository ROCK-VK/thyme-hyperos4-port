# SUCCESS_PORT_DONOR_IDENTITY — 成功包 donor 身份审计

- 审计对象：`[LOCAL_PROJECT_ROOT]\10S系统\BB解密-261002_移植Mi18pm-_HyperOS_4.0.15-for_thyme_A17`（下称 **SUCC**）
- 审计时间：2026-10-05
- 审计方式：**仅只读静态分析**。未刷写、未擦除、未重启、未连接设备。
- 审计者：DSH 主窗口（接手上任 47 个 Candidate 的 Legacy 线）

## 结论（分级）

| 项目 | 结论 | 级别 |
| --- | --- | --- |
| SUCC 的 **donor 机型** | **Xiaomi 18 Pro Max = `madrid`** | **A. Confirmed madrid** |
| SUCC 的 **donor 版本线** | HyperOS 4 / Android 17，`XEOCNXM` 版本线，本包为 **OS4.0.15.0.XEOCNXM** | A. Confirmed |
| SUCC 是"官方 madrid 4.0.19 的降级版"吗 | 不是降级，是**同一 madrid(or missi 平台)源码树的更早一次构建**（4.0.15），且已叠加 thyme 适配层 | A/B. Confirmed |
| SUCC 的 vendor / odm 层 | **不是 madrid 的**，是 **thyme 自己重建的 Android 17 / HyperOS 4 vendor 层** | A. Confirmed |
| SUCC 与官方 madrid 4.0.19 的可用性关系 | 作为 **thyme 适配层 + 启动兼容栈的 Known-Good 参照**，不作为 system 内容来源 | A/B |

**不允许的表述已避免**：本报告不使用"100% 修复""权威根因""绝对解决""必然""彻底"等无证据措辞。

---

## 一、决定性证据：madrid 专属指纹出现在 SUCC 的 product / mi_ext 分区内

### 1.1 product 分区（SUCC `product_a.img` → `/etc/build.prop`）

来源：`work\reference_thyme_success_mi18pm_20261005\product_a.img`（从 SUCC `super.img` 按 LP extent 提取，方法见第四节）[B]

```
ro.product.product.brand=Xiaomi
ro.product.product.device=miproduct
ro.product.product.manufacturer=QUALCOMM
ro.product.product.model=miproduct
ro.product.product.name=miproduct_madrid          <-- madrid
ro.product.build.date=Tue Sep 29 00:54:52 CST 2026
ro.product.build.fingerprint=Xiaomi/madrid/miproduct:17/CP2A.260605.016/OS4.0.15.0.XEOCNXM:user/release-keys
ro.product.build.version.incremental=OS4.0.15.0.XEOCNXM
ro.product.build.version.release=17
ro.product.build.version.sdk=37
```

**判读**：
- `ro.product.product.name = miproduct_madrid` 是"产品分区属于 madrid"的直接命名证据。
- `ro.product.build.fingerprint` 的 `Xiaomi/madrid/miproduct` 部分与官方 madrid 4.0.19 完全同构（见 1.3 对照表），仅版本号与构建日期不同。
- 该数值**不可能**出现在任何非 madrid 机型上：Xiaomi 的 product 分区指纹是 per-device 生成的。

### 1.2 mi_ext 分区（SUCC `mi_ext_a.img` → `/etc/build.prop`）

```
ro.product.mod_device=thyme                                        <-- 已被改成 thyme（移植适配）
ro.product.build.version.incremental=OS4.0.15.0.XEOCNXM
ro.mi.os.version.code=4
ro.mi.os.version.name=OS4.0
ro.mi.os.version.incremental=OS4.0.15.0.XEOCNXM
ro.build.version.smr_baseversion=OS4.0.11.0.XEOCNXM
ro.vendor.build.ab_ota_partitions=android_esp,aop,aop_config,bl31,bluetooth,boot,countrycode,cpucp,cpucp_dtb,
  dcb,dcd_oem,dcp,dsp,dtbo,featenabler,hyp,hyp_ac_config,hyp_config,idmanager,imagefv,init_boot,keymaster,modem,
  modemfirmware,multiimgqti,odm,pdp,pdp_cdb,pmic_psi,product,pvmfw,qecp,qtvm_dtbo,qupfw,secretkeeper,shrm_lp5,
  shrm_lp6,soccp,spuservice,system,system_dlkm,system_ext,tme_config,tme_fw,tme_seq_patch,tz,tz_ac_config,
  tz_oem_config,tz_qti_config,uefi,uefi_dtb,uefisecapp,vbmeta,vbmeta_system,vendor,vendor_boot,vendor_dlkm,
  vm-bootsys,vplan,vplan_mini,xbl,xbl_ac_config,xbl_config,xbl_ramdump,mi_product,mi_ext
```

**判读**：
- `ro.vendor.build.ab_ota_partitions` 是**机型分区布局指纹**。SUCC 这份列表与官方 madrid 4.0.19 的列表**逐字符完全一致**（见 1.3），包含 `android_esp / tme_fw / tme_config / tme_seq_patch / shrm_lp5 / shrm_lp6 / vm-bootsys / vplan / vplan_mini / qtvm_dtbo / pvmfw / secretkeeper / idmanager / soccp / spuservice / dcp / dcb / pdp / qecp / bl31 / cpucp / multiimgqti / hyp_ac_config / hyp_config / tz_ac_config / tz_oem_config / tz_qti_config / xbl_ac_config / xbl_ramdump / uefi_dtb`）等一整套 **SM8950 / 新平台专属分区**。Xiaomi 10S（thyme，SM8250-AC）根本没有这些分区。
- 这证明 SUCC 的 system 侧 **直接继承自 madrid 的构建树**，而不是从 thyme 官方包改出来的。
- `ro.product.mod_device` 由 `madrid` 改为 `thyme`，是**移植适配动作**的痕迹（与 1.3 对照可见）。

### 1.3 SUCC vs 官方 madrid OS4.0.19 —— 同字段逐项对照

| 字段 | 官方 madrid 4.0.19（OTA 解包） | SUCC 成功包 | 判读 |
| --- | --- | --- | --- |
| OTA `pre-device` | `madrid` | 无 OTA（第三方线刷包） | — |
| OTA `post-build` | `Xiaomi/madrid/madrid:17/CP2A.260605.016/17OS4.0.261004.020338398.QCPECN.S:user/release-keys` | — | — |
| `ro.product.mod_device`（mi_ext） | `madrid` | `thyme` | **移植适配改动** |
| `ro.mi.os.version.incremental` | `OS4.0.19.0.XEOCNXM` | `OS4.0.15.0.XEOCNXM` | 同线更早版本 |
| `ro.build.version.smr_baseversion` | `OS4.0.17.0.XEOCNXM` | `OS4.0.11.0.XEOCNXM` | 同线更早版本 |
| `ro.mi.os.version.code` | `4` | `4` | 一致（HyperOS 4） |
| `ro.mi.os.version.name` | `OS4.0` | `OS4.0` | 一致 |
| `ro.vendor.build.ab_ota_partitions` | 见 1.2 长列表 | **逐字符相同** | **机型布局同源** |
| mi_ext AVB prop（官方 vbmeta 内） | `Xiaomi/madrid/mi_ext:17/CP2A.260605.016/OS4.0.19.0.XEOCNXM` | 同格式，版本 `OS4.0.15.0.XEOCNXM` | **同源** |
| product build fingerprint | （官方 product 分区，见 madrid vbmeta prop `Xiaomi/madrid/miproduct:17/.../OS4.0.19.0.XEOCNXM`） | `Xiaomi/madrid/miproduct:17/CP2A.260605.016/OS4.0.15.0.XEOCNXM` | **同源，仅版本号不同** |
| `ro.product.marketname`（odm） | `Xiaomi 18 Pro Max`（model `M154FF`） | `Mi 10S`（model `M2102J2SC`） | **已被替换为 thyme** |

官方 madrid 侧原文（`work\reference_madrid_os4_0_19\images\odm.img:/etc/build.prop`）[B]：

```
ro.product.odm.device=madrid
ro.product.odm.model=M154FF
ro.product.odm.name=madrid
ro.product.odm.marketname=Xiaomi 18 Pro Max
ro.odm.build.fingerprint=Xiaomi/madrid/madrid:17/CQ2A.260712.001-CP2A.260605.016/OS4.0.17.1.XEOCN:user/release-keys
```

SUCC 侧原文（`vendor_a.img:/build.prop`、`odm_a.img:/etc/build.prop`）[B]：

```
ro.product.vendor.device=thyme
ro.product.vendor.model=M2102J2SC
ro.product.vendor.name=thyme
ro.product.vendor.marketname=Mi 10S
ro.vendor.build.fingerprint=Xiaomi/thyme/thyme:13/RKQ1.211001.001/V816.0.4.0.TGACNXM:user/release-keys
ro.product.board=thyme
ro.board.platform=kona
# from device/xiaomi/thyme/special_ro.prop
```

---

## 二、`missi` 不是否定证据（关键澄清，防止后续误判）

SUCC 的 `system_a` / `system_ext_a` 里 `ro.product.system.device=missi`、`ro.build.flavor=missi-user`。官方 madrid 4.0.19 的 **system 分区也是完全相同的 `missi`**（`ro.product.system.device=missi`，`ro.system.build.fingerprint=Xiaomi/missi/missi:17/CP2A.260605.016/17OS4.0.261004.020338398.QCPECN.S:user/release-keys`）[B]。

判读 [D]：
- `missi` 是 madrid 所基于的 **Qualcomm 平台 / SSI（Single System Image）通用代号**，不是 madrid 的替代机型。Xiaomi 的 system 分区在所有该平台机型上共享同一份 SSI 内容，机型身份由 **odm / product / mi_ext / vendor** 承载。
- 因此"system 里写着 missi" **既不支持也不否证** donor 是 madrid；真正的判据是 product/mi_ext/odm 的 `madrid` 指纹与 `ab_ota_partitions` 布局。
- 同一现象在官方 madrid 包里也存在，所以它不能作为"SUCC 不是 madrid"的依据。

**证据级别说明**：`missi = madrid 的平台代号` 目前是 [D] 推断（依据：官方 madrid 包的 system 分区与 SUCC 同为 missi，且 [公开报道](https://weibo.com/2/detail/[REDACTED_LONG_ID]) 确认 Xiaomi 18 Pro Max 代号为 Madrid）。未取得 Xiaomi 内部命名表，故不升级为 [B]。

---

## 三、SUCC 的分层结构（这是本次审计最重要的工程结论）

SUCC **不是**"整包 madrid 换个 logo"，而是**三层拼合**：

| 层 | 内容来源 | 证据 | 级别 |
| --- | --- | --- | --- |
| **A. 系统框架层** (`system`, `system_ext`, `product`, 部分 `mi_ext`) | madrid / missi 的 HyperOS 4 **OS4.0.15.0.XEOCNXM** 构建（EROFS） | `miproduct_madrid`；`ab_ota_partitions` 与 madrid 逐字符相同；`ro.mi.os.version.incremental=OS4.0.15.0.XEOCNXM` | A |
| **B. 供应商/硬件抽象层** (`vendor`, `odm`, `mi_ext_a` 为 **ext4**) | **thyme 自己重建**的 Android 17 / HyperOS 4 vendor+odm（源码注释仍为 `device/xiaomi/thyme/special_ro.prop`，fingerprint 仍是 `V816.0.4.0.TGACNXM` Android 13 的字符串，平台 `kona`/`thyme`） | `ro.product.board=thyme`、`ro.board.platform=kona`、`ro.product.vendor.marketname=Mi 10S` | A |
| **C. 底层固件层** (`xbl/abl/tz/hyp/aop/modem/dsp/bluetooth/keymaster/qupfw/featenabler/devcfg/cmnlib/cmnlib64/uefisecapp/xbl_config`, `dtbo`, `imagefv`) | **第三方 thyme 固件包**，与 `OurSky_Mi10s_OS3.0.318.0.WPBCNXM_A16_b3334\firmware-update\*` **逐字节相同** | SHA256 全等（见第五节） | A |

**A/B/C 分层的工程含义**：
- 想从"已知可启动"走到"官方 4.0.19"，**只需要替换 A 层**（system / system_ext / product / mi_ext 的 system 侧内容），并把版本号从 4.0.15 提升到 4.0.19。
- **B 层就是"thyme adaptation layer"本身**，是 SUCC 最有价值的资产，应当**整体复用**而不是重造。
- **C 层不是 donor 内容**，是从 thyme 固件包搬来的；它同时也解释了为什么 SUCC 能在这台设备上点亮显示与基带。

---

## 四、SUCC `super.img` 的真实结构与提取方法（此前工具全部失败）

- 文件：`10S系统\...\images\super.img`，**9,126,805,504 bytes（= 8.5 GiB 整）**，SHA256 `D05DC8DFDD7DCD54A319D0051BDD1BB9942F3E162C52B2272DFC585E0B314496` [B]
- `simg2img` 报 `Invalid sparse file format at header magic`；`lpdump`/`lpunpack` 拒绝解析 —— 但**不是坏包**。实测其 LP 元数据采用**非 AOSP 布局**：

```
0x0000  全零填充
0x1000  LpMetadataGeometry   magic 0x616C4467 ("gDla")
0x2000  该 geometry 块的重复副本（AOSP 此处应是 header，故 lpdump 失败）
0x3000  LpMetadataHeader      magic 0x414C5030 ("0PLA"), header_size=256, LP 10.2
0x3100  partitions 表 (12 × 52B)
0x3700  extents   表 ( 6 × 24B)
0x3a00  groups    表 ( 3 × 48B)
0x3b90  block_devices ( 1 × 64B)
```

- extent 语义经**文件系统 magic 实测验证**：`num_sectors` 为 512B 扇区数，`target_data` 为 super 内绝对 LBA。
- 已生成项目工具 `tools\extract_success_super.py`（只读、无外部依赖）完成提取。

六个 extent（`work\reference_thyme_success_mi18pm_20261005\`）：

| extent | 归属分区 | 大小 (bytes) | 文件系统 | super 内偏移 | SHA256 (前 16) |
| --- | --- | --- | --- | --- | --- |
| 0 | `mi_ext_a` | 174,723,072 | **ext4** | 0x00100000 | 8B0EB84FA2A91A9D |
| 1 | `odm_a` | 2,351,104 | **ext4** | 0x0A800000 | 220135E09680838D |
| 2 | `product_a` | 4,110,647,296 | EROFS | 0x0AB00000 | E5793C9F7B15D268 |
| 3 | `system_a` | 959,201,280 | EROFS | 0x0FFC0000 | 0492A0180763414F |
| 4 | `system_ext_a` | 850,153,472 | EROFS | 0x138F00000 | 1469B7A33FAB356B |
| 5 | `vendor_a` | 2,044,887,040 | **ext4** | 0x16BA00000 | AF7E4894D9241476 |

**架构差异（重要）**：官方 madrid 4.0.19 的 `product / system / system_ext / vendor / odm / mi_ext` **全部是 EROFS**；SUCC 的 `vendor / odm / mi_ext` 是 **ext4**。这从文件系统层面再次印证第三节的分层结论：B 层是 thyme 侧重做的，且没有沿用 madrid 的 EROFS 打包方式。

---

## 五、C 层（固件）逐字节来源确认

对 SUCC `images\` 与两个 thyme 参照包做 SHA256 全等比对 [B]：

| 镜像 | vs `thyme_images_OS1.0.4.0.TGACNXM_13.0` | vs `OurSky_..._WPBCNXM_A16_b3334\firmware-update` |
| --- | --- | --- |
| abl / dtbo / imagefv | **MATCH** | MATCH |
| aop / bluetooth / cmnlib / cmnlib64 / devcfg / dsp / featenabler / hyp / keymaster / modem / qupfw / tz / uefisecapp / xbl / xbl_config | diff | **MATCH** |
| vbmeta / vbmeta_system / vendor_boot | diff | diff |

结论：SUCC 的固件层是**第三方 thyme 固件包（与 OurSky 包同源）**，不是 madrid 固件，也不是 OS1.0.4.0 那一版。 [A]

---

## 六、SUCC 的 AVB 状态（与 Legacy C47 一致，可作为交叉验证）

`images\vbmeta.img` 与 `images\vbmeta_system.img`：
- 均为 **4096 bytes**，SHA256 **两者相同**：`D2E1979739EC67076A90B0FC625DAE84A1AA2ED72D05D2B55D52539E3462B442` [B]
- `avbtool info_image`：`Authentication Block: 0 bytes`、`Auxiliary Block: 0 bytes`、`Algorithm: NONE`、**`Flags: 2`（AVB_VBMETA_IMAGE_FLAGS_VERIFICATION_DISABLED）**、`Descriptors: (none)`、`Release String: 'avbtool 1.1.0'` [B]

对照官方 madrid 4.0.19 `vbmeta.img`：12288 bytes，`SHA256_RSA4096`，含 2 个 chain partition descriptor 与 20+ 个 `com.android.build.*.fingerprint` prop，`Flags: 0`。 [B]

判读：SUCC 与 C47 一样，是**用 `avbtool` 重新生成的无签名空 vbmeta（verification disabled）**，而非厂商签名链。这是社区包的常规做法，也说明**刷 SUCC 不会引入 madrid 的 AVB 公钥信任链**，回退可控。

---

## 七、对项目目标的正式影响

1. **主线切换成立**：SUCC 的 donor 已确认为 Xiaomi 18 Pro Max / `madrid`。按任务书第九节，项目主路线正式定为：
   `官方 madrid OS4.0.19` → `复用 SUCC 的 thyme 适配层(B 层)` → `Xiaomi 10S`
2. **SUCC 升格**：正式命名为 **THYME Mi18PM Known-Good Port Baseline**（参照优先级第 1 位）。
3. **版本升级路径明确**：`MADRID 4.0.15 port (SUCC)` → `upgrade to official madrid 4.0.19`，即"换 A 层 + 抬版本号"，而不是重做整个移植。
4. **Legacy C1–C47 的 `dada` 假设被替换**：C1–C47 全部基于 Xiaomi 15 / `dada` donor。该假设**自此失效**，但 C1–C47 的真机故障数据库、thyme 适配知识与工程基础设施**继续有效**（详见 `日志\项目当前状态.md` 的资产分类）。

---

## 八、仍未验证 / 需要下一步闭合的事项

| 事项 | 状态 | 需要的证据 |
| --- | --- | --- |
| SUCC 在真机实际进入 SetupWizard / 桌面 | **未验证**（仅社区口述，无本机取证） | 任务 5：受控刷入 + 任务 6：Known-Good 取证 |
| SUCC 的 4.0.15 是否等同于官方 `madrid` 4.0.15 OTA 的内容 | **部分验证**（本机无 4.0.15 官方 OTA 可比） | 若获得官方 `OS4.0.15.0.XEOCNXM` full OTA，可做 A 层逐文件差分 |
| `missi` 与 madrid 的官方命名关系 | **[D] 推断** | Xiaomi 内部设备命名表 / 官方 4.0.15 OTA |
| SUCC 的 vendor 层是否含 4.19 内核所需 BPF 兼容补丁 | 未验证 | 子代理审计（network/BPF） |
| SUCC 的 `libnetd_resolv.so` / `netd` 是否为原版 | 未验证 | 子代理审计（对策 C47 的 `0x1a92b8` 阻塞点） |

---

## 附：本报告使用的工具（均已落地到项目 `tools\`）

- `tools\parse_lp_metadata.py` — AOSP LpMetadata 解析（可作为后续对照实现）
- `tools\extract_success_super.py` — 应对非 AOSP 布局 super.img 的只读提取器（含 FS magic 实测校验）
- `tools\scan_identity_strings.py` — 大镜像 identity 字符串定点扫描
- `tools\read_ext4_props.py` — 经 `debugfs` 只读提取 ext4 分区身份属性
