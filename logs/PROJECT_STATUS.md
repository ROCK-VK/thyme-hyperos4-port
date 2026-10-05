# THYME-OS4 项目当前状态

更新时间：2026-10-05 11:05 HKT（M00 Madrid Intake 完成后）

## 项目目标（本轮已正式重定义）

将 **Xiaomi 18 Pro Max（`madrid`）HyperOS 4 / Android 17 官方 OS4.0.19.0.XEOCNXM** 移植到
**Xiaomi 10S（`thyme` / Snapdragon 870 / SM8250-AC）**。

- **最终 donor：madrid**（不再是 Xiaomi 15 / `dada`）
- **Known-Good 参照：THYME Mi18PM Known-Good Port Baseline**
  （`10S系统\BB解密-261002_移植Mi18pm-_HyperOS_4.0.15-for_thyme_A17`，社区多名用户实测可进入 HyperOS 4）
- **Legacy 线：C1–C47**，正式定性为 `Legacy THYME Android-17 Compatibility Research Line`，**不废弃、不删除**，
  但**新实验不再沿用 C 编号**，madrid 主线改用 **M01 / M02 / M03 …**

## 阶段目标

**M00（madrid intake）已完成**：恢复状态、核验成功包 donor、解包官方 madrid 4.0.19、建立三方结构地图、
生成受控刷写脚本（未执行）。

**下一步 M01 = Known-Good 实机验证**：受控刷入成功包 → 建立同机成功态 baseline。

## 一、本轮已确证的关键事实

### 1. 成功包 donor 身份 = madrid（A 级结论）

- `product_a:/etc/build.prop` → `ro.product.product.name=miproduct_madrid`，
  `ro.product.build.fingerprint=Xiaomi/madrid/miproduct:17/CP2A.260605.016/OS4.0.15.0.XEOCNXM:user/release-keys`
- `mi_ext_a:/etc/build.prop` → `ro.mi.os.version.incremental=OS4.0.15.0.XEOCNXM`，
  `ro.vendor.build.ab_ota_partitions` 与官方 madrid 4.0.19 **逐字符完全相同**（70 项 madrid 专属分区布局）
- 官方 OTA `META-INF/com/android/metadata` → `pre-device=madrid`，
  `post-build=Xiaomi/madrid/madrid:17/CP2A.260605.016/17OS4.0.261004.020338398.QCPECN.S:user/release-keys`
- 完整报告：`reports\m00_madrid_intake_20261005\SUCCESS_PORT_DONOR_IDENTITY.md`

**注意（防止后续误判）**：成功包与官方 madrid 的 `system` 分区都写着
`ro.product.system.device=missi`。`missi` 是 madrid 所基于的平台/SSI 代号，**不是替代机型**，
机型身份由 odm / product / mi_ext 承载。详见上述报告第二节。

### 2. 成功包是三层拼合（已确证）

| 层 | 内容 |
| --- | --- |
| A 系统框架 | madrid/missi 的 `OS4.0.15.0.XEOCNXM`（EROFS） |
| B 供应商层 | **thyme 自己的 vendor/odm/mi_ext，重打包为 ext4**，`mod_device` 改写为 `thyme` |
| C 底层固件 | 第三方 thyme 固件包（与 `OurSky_Mi10s_OS3.0.318.0.WPBCNXM_A16_b3334` 逐字节相同） |

→ **B 层就是这个 port 的 "thyme adaptation layer"，是最该整体复用的资产。**

### 3. 成功包 `super.img` 的真实结构（此前所有工具都解析失败）

- 9,126,805,504 B（8.5 GiB 整），SHA256 `D05DC8DFDD7DCD54A319D0051BDD1BB9942F3E162C52B2272DFC585E0B314496`
- **不是 sparse**；LP 元数据是**非 AOSP 布局**：geometry @0x1000、geometry 副本 @0x2000、
  真正的 `LpMetadataHeader`（magic `0x414C5030`）在 **0x3000** → `lpdump`/`lpunpack` 因此拒绝解析
- 已写工具 `tools\extract_success_super.py`（只读）完成提取，6 个 extent 已落地到
  `work\reference_thyme_success_mi18pm_20261005\`

### 4. kernel 事实（**推翻了一个重要假设**）

| 目标 | kernel |
| --- | --- |
| 成功包 boot | `4.19.325-cxk-lxsclnb-g33d88af64048`（ZyC clang 16.0.6） |
| 官方 madrid 4.0.19 boot | `6.18.21-android17-5-…`（clang 22，**不可用于 thyme**） |
| Legacy C47 boot | `4.19.325-perf-g45b9b954f074`（clang 21.0.0，root@[LOCAL_HOST]，自建） |
| 官方 thyme OS1.0.4.0 boot | `4.19.157-perf-…`（clang 10，**缺 BPF_LSM / EROFS**） |

- **C47 与成功包的 kernel 同属 4.19.325 谱系，且两者都已启用 `CONFIG_BPF_LSM`、`CONFIG_EROFS_FS`、
  `CONFIG_ANDROID_VENDOR_HOOKS`。**
- → **"旧 4.19 内核没有 BPF 能力导致 netd 必失败"这一假设不成立。**
- → 回退到官方 thyme 4.19.157 内核会同时丢掉 BPF LSM 与 EROFS，**不可行**。

### 5. Legacy C47 的 donor 身份（新发现）

C47 的 `system/build.prop`：
`ro.system.build.fingerprint=Xiaomi/custom_thyme/thyme:17/CP2A.260605.016/OS4.0.0.8.XOCCNXM`，
`ro.build.version.incremental=17OS4.0.260902.005534479.QCPECN.S`

- 版本线是 **`XOCCNXM`（Xiaomi 15 / dada 线）**，而 madrid 是 **`XEOCNXM`**。
- → **C47 是 dada 系统层 + 官方 thyme A13 vendor/odm 的跨线、跨版本组合**；
  成功包是 madrid 系统层 + thyme vendor。**这是两者最本质的差别。**

### 6. 成功包的 AVB 状态

`vbmeta.img` 与 `vbmeta_system.img` 均为 4096 B、`Algorithm: NONE`、`Flags: 2`
（verification disabled）、`Descriptors: (none)`，且两者 SHA256 相同。
→ 与 C47 的现状同语义，**不会引入 madrid 的 AVB 公钥信任链，无 rollback index 抬升风险**。

### 7. 官方 madrid 4.0.19 基线的关键结构事实

- **该 OTA 内没有 `super.img`**；super 几何在 `DeltaArchiveManifest` field 15：
  group `qti_dynamic_partitions`，`max_size` 18,779,996,160 B，
  **super 分区本身 18,790,481,920 B（17.50 GiB）**，成员恰 9 个
  （odm / product / system / system_dlkm / system_ext / vendor / vendor_dlkm / mi_product / mi_ext），
  **`mi_ext` 属同一 group**。全部 EROFS / 4096B 块 / `LZ4_0PADDING` / 元数据声明 **"required kernel 5.4"**。
- **`abl` 与 `devcfg` 不在该 payload 中。**
- **madrid 的身份是分裂的**：
  - madrid 专属 → `odm`（`M154FF` / `Xiaomi 18 Pro Max`）、`product`（`miproduct_madrid`）、
    `mi_ext`、`system_dlkm`、`vendor_dlkm`、`dtbo`、`vendor_boot`、`boot`、`pvmfw`
  - 平台通用 → `system` / `system_ext` / `init_boot` 是 **`missi`**；`vendor` 是 **`mivendor`**
  - 同 OTA 内并存两条版本线：`OS4.0.19.0.XEOCNXM` 与 `OS4.0.17.1.XEOCN`
- **SoC 平台 = `art`（SM8950 级）**；`dtbo.img` 只有 1 个 entry；vendor_boot 的 4 个 DTB 全部
  `qcom,board-id <0x00 0x00>` → **madrid 侧无 board-id 面板/变体选择机制**。
- `boot.img` = header v4、**ramdisk 0**、内含 Google GKI `6.18.21-android17-…`。
- **对 thyme 的决定性含义**：madrid super 17.50 GiB **放不进** thyme 的 8.5 GiB super，
  **M02 必须以"重裁 dynamic partition 尺寸"为前提**，不能假设可直接复用。

### 8. 成功包的启动链组织方式（与 C47 根本不同）

- 成功包 `boot_noroot.img` 的 50,637,560 B ramdisk 实读 `prop.default` 为
  `ro.product.system.name=twrp_thyme`、`Xiaomi/twrp_thyme/alioth:15/SP2A.220405.004/sekaiacg12132152:eng/test-keys`，
  含 `twrp_ramdisk-timestamp`、`twres/`、`init.recovery.qcom.rc`、`customzip/Magisk/`、
  `magisk_prebuilt-timestamp`、`miui_prebuilt-timestamp`、`ramdisk-files.txt`(110,955 B)。
  → 这是社区作者 `sekaiacg` 的 **TWRP/Magisk 派生自包含 ramdisk**。
- 成功包 `vendor_boot` 的 ramdisk 仅 **2,180 B**；C47 的 vendor_boot ramdisk 是 **23,340,130 B**。
- **两种启动链组织方式互不兼容**，刷写时必须把 `boot` + `vendor_boot` + `dtbo` + `super` **当作一个整体替换**。

### 9. netd / tethering 的关键事实（纠正了旧归因）

- 成功包 `libnetd_updatable.so`（CAPEX 内）：103,648 B，
  SHA256 `2C811151E99F227BC8E180F64F0B686E8D696B5323CE2F81313914CC597277AD`，
  与 dada 参考副本 **`cmp` IDENTICAL**，且 `0x11534` 处**仍是未修补的 `cbnz w8, 0x115d8`**。
- 成功包 `libnetd_resolv.so`：2,482,912 B，
  SHA256 `FF9E1619C298A787748B8BB9ABFFBC3A9065E2CD8216B4C328EEECA192D737B5`，
  `0x1a92b8` 处**仍是未修补的 `cbnz w0, 0x1a9388`**（即 Legacy-C48A 计划旁路的那一条）。
- 成功包 `/system/bin/netd`：695,816 B，
  SHA256 `5B316597C9AD3FBB6B3E35DF04A10AEAC8C5A3730FDAE18E4060CE93F362661`，未见 NOP 补丁特征。
- **归因纠正**：「成功包因为打了补丁所以 netd 能跑」**不成立**。
  结合 C44 真机日志 `netd: library "libnetd_updatable.so" not found` 推断：
  **tethering CAPEX 未激活时 netd 根本不加载该库，因而永远走不到那两个 gate。**
- **AOSP 源码实读确认**该 gate 是**纯内核版本号比较**（`work\BpfHandler.cpp` 行 105）：
  `if (isAtLeast25Q2 && !isAtLeastKernelVersion(5, 4, 0)) return Status("25Q2+ platform with kernel version < 5.4.0 is unsupported");`
  → **不做任何 BPF 能力探测**；无论 4.19 内核 backport 多少 BPF 特性，该 gate 都不会因此通过。
  → 是否仍需该旁路，**只能由真机证据回答**。

### 10. 成功包 vs 官方 madrid 4.0.19 的 A 层差分（APEX 逐包哈希矩阵）

- `system/apex` 下 **36 个包中 35 个 SHA256 完全相同**；唯一差异是 `com.android.virt.apex`
  （两者**同为 93,360,128 B**，哈希不同，属构建/签名差异，非结构差异）
- `com.android.tethering.capex`（含上述两个未修补 gate）两包**哈希相同**
- `com.android.runtime.apex`（含 `linker64`）两包**哈希相同**
- `system_ext/apex`：`art.compatible` / `compos` / `vndk.v34` 相同；
  **成功包多出 `com.android.vndk.v30.apex`（114,769,920 B），madrid 没有**
- → 支持「Known-good 4.0.15 port → upgrade to official madrid 4.0.19」的可行性：
  A 层替换**不需要重做架构**；但替换时必须**同步评估 VNDK 组合**（v30 APEX 对应 A13 vendor 底座）
- 数据来源：`work\madrid_m01_audit\apex_hash_matrix.txt`

## 二、Legacy C1–C47 资产分类（用户要求的 A/B/C 分类）

### 继续复用（第一类：thyme 硬件相关，大概率仍有价值）

- C40 media codec variant（`ro.media.xml_variant.codecs=_V1_0`）
- C42 DisplayDeviceConfig 最低亮度修复（`0.000854597`）
- 全部工程基础设施：super 拆包/重包、EROFS 工具链、AVB、APEX/CAPEX 构造、
  Fastboot controlled flash、retry budget 管理、Standalone RAM diag、`THYME_DIAG` 全量备份、
  pstore 分析、GitHub 增量归档、sanitization、hash/manifest gate
- 真机故障数据库（early boot / APEX / CAPEX / AVB / DisplayDeviceConfig / media /
  SurfaceFlinger / Zygote / SystemServer / netd / BPF / DNS resolver / framework-vendor ABI）

### 仅作参考（第二类：研究价值，未必进入 madrid 最终版）

- C43 `libnetd_updatable.so` `0x11534` 4 字节 NOP（BpfHandler 版本门旁路）
- C47 `/system/bin/netd` `0x761c0` 4 字节 NOP（`Controllers::init()` `exit(2)` 旁路）
- Legacy-C48A 假设：`libnetd_resolv.so` `0x1a92b8` `cbnz w0` → NOP（**当前明确不构建**）
- 判断前提：若成功包证明"换成正确的 userspace compatibility stack 后原版 `libnetd_*` 可正常工作"，
  则放弃继续 NOP 链。

### 应废弃（第三类：仅属历史制包错误）

- 错误的 `originalApexDigest`
- inner APEX payload 未按 4096 对齐
- inner / outer / payload manifest 版本号不一致
- → 这些 **bug 不继承**，但经验必须固化进构建 Gate

## 三、当前设备与宿主状态

- 设备：Xiaomi 10S `[REDACTED_DEVICE_ID]`，最后一次已知状态为 Standalone RAM 诊断环境导出的取证就绪态，
  **本轮未连接、未刷写、未重启、未执行任何 adb/fastboot 命令**（收尾复查 `fastboot devices` 为空）
- 最后一次 Fastboot 只读快照：`current-slot=a`、`unlocked=yes`、`is-userspace=no`
- 宿主磁盘（收尾实测）：C=80.22 GiB、D=172.68 GiB、E=130.88 GiB（均 > 50 GiB 门禁）
- Docker / WSL 数据零触碰

## 四、红线纪律（永久）

- 严禁 Bootloader relock
- 严禁写入：`persist` / `modemst1` / `modemst2` / `fsg` / EFS / NV / calibration / identity 分区
- 严禁把 madrid 固件（xbl/abl/tz/hyp/aop/modem/dsp 等）刷入 thyme
- 任何刷写完成后**必须停在 Fastboot**；首次开机需用户明确授权
- **当前明确不构建 Legacy C48**
- 设备当前未连接；未经用户指令不与设备交互

## 五、当前阻塞 / 未验证

1. **成功包真机可启动性尚未在本机验证**（仅社区口述）。这是 M01 要闭合的。
2. **最高优先级开放问题**：成功包在真机上 **tethering CAPEX 是否实际激活**？
   - 若**未激活** → netd 以"缺库"方式运行，两个 gate 都不会被执行到，
     则"成功包仍需 userspace 旁路"这一命题无法证实，且成功包本身带网络子系统降级；
   - 若**已激活** → 则说明存在我们尚未识别的机制让那两个 gate 通过，需重新定位。
   **在答案出现前不构建任何新 Candidate（含 Legacy C48 与 M01-bundle）。**
3. madrid 4.0.19 的 super（17.50 GiB）如何裁剪进 thyme 的 8.5 GiB super —— 完全未设计
4. madrid 4.0.19 的 EROFS（元数据声明需 5.4 内核）能否在 thyme 的 4.19.325 上挂载 —— 未验证
5. Fastboot 写回 / 失败回滚**从未演练**，回退仍是条件性判断而非保证
6. EDL / 9008 救援路径未验证
7. super 内各 logical 分区的**设备端实际 LV 尺寸**未知（payload 无 LP 元数据）

## 六、本轮产出的文件

- `reports\m00_madrid_intake_20261005\SUCCESS_PORT_DONOR_IDENTITY.md`
- `reports\m00_madrid_intake_20261005\THYME_SUCCESS_REFERENCE_ARCHITECTURE.md`
- `reports\m00_madrid_intake_20261005\MADRID_PAYLOAD_INVENTORY.md`
- `reports\m00_madrid_intake_20261005\CONTROLLED_FLASH_MATRIX_AND_RISK.md`
- `reports\m00_madrid_intake_20261005\THREE_WAY_STRUCTURE_MAP.md`
- `tools\controlled_thyme_success_flash.ps1`（DRY-RUN 已 PASS，**未执行**）
- `tools\controlled_thyme_success_flash.constants.json`
- `tools\extract_success_super.py`、`tools\parse_lp_metadata.py`、
  `tools\scan_identity_strings.py`、`tools\read_ext4_props.py`
- `work\reference_madrid_os4_0_19\`（官方 madrid 4.0.19 payload 解包，**66 个镜像，14.9424 GiB**）
- `work\madrid_m00_intake\`（madrid 清单：`IMAGE_INVENTORY.csv/.json` + 12 份原始证据）
- `work\madrid_m01_audit\`（内核 config 实解 4 份 + `apex_hash_matrix.txt`）
- `work\reference_thyme_success_mi18pm_20261005\`（成功包 6 个 dynamic partition 提取）

## 七、下一步（等待用户决策）

**M01：受控刷写成功包，建立 Known-Good**

1. 用户明确发出"**刷入成功包**"指令
2. 执行前：备份当前 A 槽 `boot_a` / `vendor_boot_a` / `dtbo_a` / `vbmeta_system_a` 与 `metadata`，
   并记录回退资产哈希
3. 执行 `tools\controlled_thyme_success_flash.ps1 -Serial <serial> -Execute`
   （默认只写 `super` / `vbmeta_system` / `boot` / `vendor_boot` / `dtbo`；
   **不写固件层、不写 `vbmeta`、不清 `userdata`/`metadata`**）
4. **停在 Fastboot**，向用户报告
5. 用户明确发出"**开始启动成功包**"指令后才允许重启
6. 若首启成功 → 执行 M01-B：Known-Good 成功态完整取证（建立 `THYME_OS4_KNOWN_GOOD_BASELINE\`）
