# THYME Mi18PM Known-Good — 受控刷写矩阵与风险评估

- 对象：`10S系统\BB解密-261002_移植Mi18pm-_HyperOS_4.0.15-for_thyme_A17`（THYME Mi18PM Known-Good Port Baseline）
- 脚本：`tools\controlled_thyme_success_flash.ps1`（**已生成，未执行**）
- 生成时间：2026-10-05
- 状态：**等待用户明确授权"刷入成功包"**。在此之前不执行任何写入。

**证据级别标注**：`[A]` 真机直接证据 / `[B]` 静态文件证据 / `[C]` Known-Good 对照 / `[D]` 推断。

---

## 一、第三方原版脚本写了什么（`YT_shuaji_xianshua.bat`，GBK 读取）[B]

原脚本执行顺序（逐条抄录，共 **24 个 fastboot 写入 + 1 个 erase**）：

| # | 命令 | 目标分区 | 文件 | 备注 |
| --- | --- | --- | --- | --- |
| 0 | `fastboot erase boot_ab` | boot (A+B) | — | **先擦除再写入** |
| 1 | `fastboot flash boot_ab` | boot (A+B) | `boot_noroot / magisk / alpha / ksu / apatch .img` | 用户二选一 |
| 2 | `fastboot set_active a` | — | — | 强制切 A 槽 |
| 3 | `flash dsp_ab` | dsp | `dsp.img` | 固件层 |
| 4 | `flash xbl_config_ab` | xbl_config | `xbl_config.img` | 固件层 |
| 5 | `flash modem_ab` | modem | `modem.img` | 固件层（308 MB） |
| 6 | `flash vbmeta_system_ab` | vbmeta_system | `vbmeta_system.img` | 4096 B，verification disabled |
| 7 | `flash tz_ab` | tz | `tz.img` | 固件层 |
| 8 | `flash vbmeta_ab` | vbmeta | `vbmeta.img` | 4096 B，verification disabled |
| 9 | `flash bluetooth_ab` | bluetooth | `bluetooth.img` | 固件层 |
| 10 | `flash abl_ab` | abl | `abl.img` | **bootloader 组件** |
| 11 | `flash cmnlib_ab` | cmnlib | `cmnlib.img` | 固件层 |
| 12 | `flash cmnlib64_ab` | cmnlib64 | `cmnlib64.img` | 固件层 |
| 13 | `flash dtbo_ab` | dtbo | `dtbo.img` | 设备树叠加 |
| 14 | `flash featenabler_ab` | featenabler | `featenabler.img` | 固件层 |
| 15 | `flash vendor_boot_ab` | vendor_boot | `vendor_boot.img` | 100 MB |
| 16 | `flash keymaster_ab` | keymaster | `keymaster.img` | 固件层（TEE） |
| 17 | `flash uefisecapp_ab` | uefisecapp | `uefisecapp.img` | 固件层 |
| 18 | `flash qupfw_ab` | qupfw | `qupfw.img` | 固件层 |
| 19 | `flash xbl_ab` | xbl | `xbl.img` | **bootloader 组件** |
| 20 | `flash devcfg_ab` | devcfg | `devcfg.img` | 固件层 |
| 21 | `flash hyp_ab` | hyp | `hyp.img` | 固件层（Hypervisor） |
| 22 | `flash imagefv_ab` | imagefv | `imagefv.img` | 固件层 |
| 23 | `flash aop_ab` | aop | `aop.img` | 固件层（Always-On） |
| 24 | `flash cust_ab`（条件） | cust | `cust.img` | 包中不存在该文件，实际不执行 [B] |
| 25 | `fastboot flash super` | super | `super.img` | 9,126,805,504 B，**非 sparse**，耗时最长 |
| 26 | `erase frp`（用户选 y） | frp | — | 可选 |
| 27 | `erase userdata`（用户选 y） | userdata | — | **破坏性** |
| 28 | `erase metadata`（用户选 y） | metadata | — | **破坏性** |
| 29 | `set_active a` + **`fastboot reboot`** | — | — | 自动重启 |

原脚本额外行为（已排除，不采纳）：
- 从未备份现有分区，**无回退路径**；
- 未校验任何镜像哈希；
- 直接 `fastboot reboot`，不给现场观测窗口；
- 完整覆盖 XBL/ABL/TZ/HYP/AOP/CMNLIB/MODEM 等 **SoC 级固件**（约 320 MB），一旦中断或版本不匹配即可能变砖。

---

## 二、本项目受控脚本的刷写矩阵（默认计划）

脚本：`tools\controlled_thyme_success_flash.ps1`
默认计划 = **5 项**（`-Execute` 且不带任何可选开关时）：

| 顺序 | 目标分区 | 文件 | 大小 (B) | SHA256 (已冻结，本地校验 PASS) | 分组 | 理由 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `super` | `super.img` | 9,126,805,504 | `D05DC8DFDD7DCD54A319D0051BDD1BB9942F3E162C52B2272DFC585E0B314496` | ROM-content | SUCC 的实际系统内容（system/system_ext/product/vendor/odm/mi_ext）[B] |
| 2 | `vbmeta_system` | `vbmeta_system.img` | 4,096 | `D2E1979739EC67076A90B0FC625DAE84A1AA2ED72D05D2B55D52539E3462B442` | ROM-content | AVB verification disabled；与 C47 现状同语义 [B] |
| 3 | `boot` | `boot_noroot.img` | 134,217,728 | `B059E885DAAA11F0032E05FF5B16C7EE6A13D84B8CDBD51033AC2B4999C3FA0F` | ROM-content | 无 Root 内核；内含该 port 的 kernel + ramdisk [B] |
| 4 | `vendor_boot` | `vendor_boot.img` | 100,663,296 | `ED5391F9AD2BE11A0636657968972D005600658C45FF631E5462CE9779840B07` | ROM-content | 首阶段 ramdisk / DTB / modules [B] |
| 5 | `dtbo` | `dtbo.img` | 33,554,432 | `A0F550A32C15B95A6BA0BBE141976BAD905D23FC74367E3E3FF0F41BC90C6D3A` | ROM-content | 与 OS1.0.4.0 thyme 官方 dtbo 逐字节相同 [B] |

**硬门禁（脚本强制执行）**：
- `product` 必须 = `thyme`
- `current-slot` 必须 = `a`（本轮只规划 A 槽）
- `unlocked` 必须 = `yes`
- `is-userspace` 必须 = `no`（必须是 Bootloader Fastboot，不能是 fastbootd）
- `slot-unbootable:a` 必须 = `no`
- `slot-retry-count:a` 必须 ≥ `-MinRetryBudget`（默认 **3**）
- 所有镜像 SHA256 必须与冻结值一致，否则直接拒绝
- 写完后**不执行 `reboot`**，设备停在 Bootloader Fastboot

### 2.1 为什么这 5 项必须**成组**刷入，不能只刷 `super`

这是本轮新取得的架构证据，直接决定刷写矩阵的形状。 `[B]`

| 证据 | 内容 |
| --- | --- |
| SUCC `boot_noroot.img` 的 50,637,560 B ramdisk | 解包实读 `prop.default`：`ro.product.system.name=twrp_thyme`、`ro.system.build.fingerprint=Xiaomi/twrp_thyme/alioth:15/SP2A.220405.004/sekaiacg12132152:eng/test-keys`；含 `twrp_ramdisk-timestamp`、`twres/`、`init.recovery.qcom.rc`、`customzip/Magisk/`、`magisk_prebuilt-timestamp`、`miui_prebuilt-timestamp`、`ramdisk-files.txt`(110,955 B) |
| SUCC `vendor_boot.img` 的 vendor ramdisk | **仅 2,180 B（近空）**，cmdline 为官方 thyme 原版 |
| SUCC `dtbo.img` | 与官方 thyme `OS1.0.4.0` 包 **SHA256 全等** |
| C47 的布局 | boot ramdisk 3,564,549 B（legacy-LZ4），vendor_boot ramdisk **23,340,130 B**，cmdline 大幅扩展 |
| madrid 4.0.19 的布局 | vendor_boot header **v4**，vendor ramdisk **76,143,885 B** 三段式（`vendor_ramdisk00` 22.4 MB / `01` recovery 30.0 MB / `02` "16K" 23.8 MB） |

**结论**：SUCC 的启动链是 **"TWRP/Magisk 派生自包含 ramdisk 放在 `boot`，由它自己挂载 super 的 dynamic partitions"**，
而 C47 走的是 **"AOSP GKI 分工，first-stage ramdisk 放在 `vendor_boot`"**。
两种组织方式互不兼容：

- 只刷 `super` 而保留 C47 的 `boot` + `vendor_boot`：C47 的 boot ramdisk 只有 3.5 MB、
  vendor_boot ramdisk 有 23.3 MB，与 SUCC 的 super 布局假设不一致 → 高概率在 first-stage 挂载阶段失败。
- 只刷 `boot` 而保留 C47 的 `vendor_boot`：C47 的 vendor cmdline（含 `androidboot.fstab_suffix=qcom`、
  `androidboot.init_fatal_panic=true` 等）与 SUCC 的 super 组合未经验证。
- → **必须把 `boot` + `vendor_boot` + `dtbo` + `super` 当作一个整体替换**，这正是受控脚本默认计划的做法。
- 由于 SUCC 与 C47 的内核版本串不同（`4.19.325-cxk-…` vs `4.19.325-perf-…`），
  **kernel 与 vendor_dlkm/system_dlkm 的模块 ABI 必须一致**；而 SUCC 的 `system_dlkm` / `vendor_dlkm`
  位于其 `super` 内，因此同组替换 `super` 也就同时替换了模块——这是一致的。 `[D]`

**永久禁止分区（脚本内含黑名单，任何开关都无法写入）**：
`persist`、`modemst1`、`modemst2`、`fsg`、`fsc`、`ssd`、`devinfo`、`oem`、`frp`、`keystore`、`misc`、`logfs`、`logdump`、`spunvm`、`apdp`、`msadp`、`limits`、`dip`、`multiimgoem`、`multiimgqti`、`sti`、`tzsc`、`uefivar`、`cust`、`countrycode`、`rescue`，以及所有 `_b` 槽目标。

**Bootloader 永不 relock。**

---

## 三、固件层（XBL/ABL/TZ/HYP/AOP/MODEM…）的处理决定

### 3.1 事实

SUCC 包内的固件镜像与 `10S系统\OurSky_Mi10s_OS3.0.318.0.WPBCNXM_A16_b3334\firmware-update\` 下的对应文件 **SHA256 逐字节相同**；`abl / dtbo / imagefv` 与 `10S系统\thyme_images_OS1.0.4.0.TGACNXM_13.0\images\` 下对应文件**逐字节相同**。[B]

→ 结论：**SUCC 的固件层不是 donor 内容，而是社区 thyme 固件包**。它不是这个 port 能启动的原因，也不携带 madrid 的任何东西。

### 3.2 决定

- 默认 **不刷固件层**（`-IncludeFirmwareLayer` 未开启）。理由：任务书要求"如果不需要，优先保留现有 firmware"。
- 需要判断"当前设备是否真的需要这些底层 firmware"。**该判断目前无法从 Fastboot 只读变量得出**，因为 Fastboot 不提供固件的字节级读取。可用的判定途径（按优先级）：
  1. **Standalone DIAG 会话**：本项目的 `THYME_DIAG` 环境可导出分区数据，可比对 `xbl/abl/tz/hyp/aop/modem/dsp` 的实际内容哈希 [C]；
  2. **ADB root 会话**：若设备当前可进入系统或 recovery，可 `dd` 读取对应块设备并比对哈希；
  3. 若两者都不可用，则**默认不刷**，先只刷 ROM-content 层做一次实验；若首启失败且证据指向固件不匹配，再单独评估。
- 若将来确实需要刷固件层：**必须单独一次授权**，且必须**逐分区**执行、每个分区后立即读回校验，中断即停止。

### 3.3 为什么本脚本把 `xbl` / `abl` 放在 opt-in 而不是默认

`xbl` 与 `abl` 属于 **bootloader 链本身**。写入过程掉电或写入不完整会直接导致无法进入 Fastboot（需 EDL/9008 救援，而本项目 EDL 路径**未验证**）。相较之下，`super` / `boot` / `vendor_boot` / `dtbo` 写入失败仍可回到 Fastboot 重刷。**风险收益不对称**，因此默认排除。

---

## 四、AVB 处理

| 镜像 | 大小 | 状态 | 语义 |
| --- | --- | --- | --- |
| SUCC `vbmeta.img` | 4,096 B | `Algorithm: NONE`、`Authentication Block: 0`、`Descriptors: (none)`、**`Flags: 2`** | AVB 校验**已禁用** [B] |
| SUCC `vbmeta_system.img` | 4,096 B | 同上，且**与 `vbmeta.img` SHA256 完全相同** | AVB 校验**已禁用** [B] |
| 官方 madrid `vbmeta.img` | 12,288 B | `SHA256_RSA4096`、2 个 chain descriptor、20+ 个 `com.android.build.*.fingerprint` prop、`Flags: 0` | 厂商签名链 [B] |

结论：
- 刷 SUCC 的 **`vbmeta_system`** 是必要的（否则 system 侧 AVB 校验会拒绝被替换的 dynamic partitions）。
- 刷 SUCC 的 **`vbmeta`（A 槽，非 `_ab`）** 在本脚本中**默认关闭**（`-IncludeVbmeta` 才开启）。理由：`vbmeta` 是引导链校验入口，改用未签名版本会改变 bootloader 的校验行为；C47 的前 47 轮实验**从未写过 `vbmeta`**，而设备始终能进入内核与 userspace [A]，说明当前 `vbmeta` 状态已允许未校验启动，**没有必要扩大变更面**。
- 刷 SUCC 不会引入 madrid 的 AVB 公钥信任链，因此**不存在 rollback index 抬升导致无法回退**的风险。

---

## 五、userdata / metadata

- 原脚本默认询问"是否需要清除数据（y/n）"，选 y 则 `erase frp` + `erase userdata` + `erase metadata`。
- 本脚本默认**不清除**。需要清除时必须**同时**传 `-FormatUserData` **和** `-ConfirmUserDataWipe`（两个独立开关是刻意设计，防止单参数误触发）。
- **是否需要的判断依据**：
  - SUCC 的 `mi_ext_a` / `vendor_a` / `odm_a` 是 **ext4**，而当前设备上（C47 遗留）的对应分区也来自同一谱系 [D]；`data` 分区本身不在本脚本写入范围内。
  - SUCC `super` 是 **9,126,805,504 B（8.5 GiB 整）**，而 C47 候选 `super` 是 **7,703,526,364 B** [B]——**两者布局尺寸不同**，这是 `metadata` 可能需要重建的**实质理由**。
  - 官方 madrid 4.0.19 的 super 更极端：**18,790,481,920 B（17.50 GiB）** [B]。这从反面说明：thyme 的 super **物理上只有约 8.5 GiB**，任何 madrid 侧方案都必须重裁 dynamic partition 尺寸，
    而这些尺寸信息就存在设备的 `metadata` 分区里。
  - 但 `erase metadata` 会连带清除 `data` 的加密元数据引用（`/metadata/vold/metadata_encryption`），实际效果接近丢数据。
- **建议**：首刷**先不清除**。若首启证据显示卡在 `first-stage mount` / `metadata` 相关环节，再单独授权 `erase metadata`。若首启进入系统但异常重启，再评估 `userdata`。
- 用户已表示可接受个人数据丢失；即便如此，"可接受"不等于"必须清除"，故保持默认不清除。

---

## 六、风险矩阵

| 风险 | 触发条件 | 影响 | 可回退性 | 级别 |
| --- | --- | --- | --- | --- |
| 首启卡第一屏（Mi Logo） | port 内部兼容问题 | 无系统 | 可回 Fastboot 重刷 | **中高**（C1–C47 已多次实测此现象）[A] |
| 首启进入但异常重启 | framework/HAL 不匹配 | 不稳定 | 可回 Fastboot 重刷 | 中 |
| `super` 写入中断（8.5 GiB，约 3–5 分钟） | USB 掉线 / 断电 | 动态分区损坏 | 可回 Fastboot 重刷；**`metadata` 可能需要重建** | 中 |
| `boot`/`vendor_boot`/`dtbo` 写入失败 | USB 掉线 | 无法进入内核 | 可回 Fastboot 重刷 | 中 |
| `vbmeta_system` 写入失败 | USB 掉线 | AVB 校验失败 | 可回 Fastboot 重刷 | 低 |
| **固件层写入失败（默认不刷）** | 若开启 `-IncludeFirmwareLayer` 时中断 | **可能无法进入 Fastboot** | 仅 EDL/9008，而该路径**未验证** | **高** |
| Bootloader relock | — | **不在任何路径中** | — | 已排除 |
| persist / EFS / NV 损坏 | — | **不在任何写入范围内** | — | 已排除 |
| 设备当前固件版本与包内固件不一致 | 若固件层确实需要更新而未更新 | 外设（modem/display/指纹）异常 | 功能性问题，通常不影响启动 | 待评估 |

**磁盘门禁**：C/D/E 需保持 > 50 GiB（任务书要求）。当前 C=81.32 GiB、D=172.68 GiB、E=157.33 GiB（在 14.94 GiB donor 解包后）——**全绿**。Docker/WSL 数据零触碰。

---

## 七、回退路径

1. **刷前必备份**（当前**尚未创建**，需在执行前完成）：
   - 当前 A 槽 `boot_a` / `vendor_boot_a` / `dtbo_a` / `vbmeta_system_a` 的现有镜像（经 Standalone DIAG 或 recovery `dd` 导出）；
   - 现有 `super` 内容（若无法整读，至少保留 C47 候选 `super`：`work\stage_c47_netd_exit2_bypass_20261004\images\super.img`，7,703,526,364 B）；
   - 现有 `metadata` 备份。
2. 回退动作：`fastboot flash super <C47_super.img>` + `fastboot flash boot_a <备份>` + `fastboot flash vendor_boot_a <备份>` + `fastboot flash dtbo_a <备份>` + `fastboot flash vbmeta_system_a <备份>`，设备停在 Fastboot，等待开机授权。
3. **未验证项**：上述回退流程**从未实际演练**（本项目的 Fastboot 写回演练仍是 UNVERIFIED）。因此"可回退"是**条件性**判断，不是保证。`[C]`

---

## 八、执行前置条件（全部满足才可执行）

- [ ] 用户明确发出"刷入成功包"指令
- [ ] 设备处于 Bootloader Fastboot，`product=thyme`，`current-slot=a`，`unlocked=yes`，`is-userspace=no`
- [ ] `slot-retry-count:a` ≥ 3
- [ ] 刷前状态快照已写入 `reports\m00_madrid_intake_20261005\preflash_state\`
- [ ] 刷前回退资产已备份并校验（见第七节第 1 条）
- [ ] `pwsh -File tools\controlled_thyme_success_flash.ps1 -Serial <serial>` DRY-RUN 全 PASS
- [ ] 用户接受：首刷不清除 `userdata` / `metadata`

执行完成后：**停止在 Fastboot**，向用户报告，等待用户明确发出"开始启动成功包"指令后才允许重启。
