# Candidate 46 构建与刷写就绪报告：统合 Manifest 版本 (370399999) 与对齐 CAPEX 双重门禁验证

**设备**：Xiaomi 10S (`thyme` / Snapdragon 870)  
**基线目标**：Xiaomi 15 (`dada`) 官方 HyperOS 4 / Android 17  
**Candidate 版本**：Candidate 46 (Unified Manifest Version & Aligned CAPEX Tethering)  
**构建日期**：2026-10-04  
**构建状态**：100% 成功，全门禁验证 PASS，已就绪待刷写  

---

## 1. 四方 Tethering APEX 结构与 Manifest 版本对照

针对 C45 首启实测打捞确证的核心事实：
- **突破已固化**：4096 字节对齐彻底消除了内核虚拟 loop 设备 `loop9 sector 0 I/O error` 与 `EXT4-fs unable to read superblock`，EXT4 文件系统成功被内核 Direct I/O 挂载（`EXT4-fs (dm-11): mounted filesystem without journal`）；
- **新阻断点锁定**：`apexd` 在挂载后执行 `VerifyManifestMatches()`，因容器外层 `apex_manifest.pb`（版本 `370400000`）与 `apex_payload.img` 内部 `/apex_manifest.pb`（版本 `370399999`）存在 2 字节版本号差异，判定包体不匹配并拒绝激活（`Manifest inside filesystem does not match manifest outside it`）。

本项目实施了定点四方 Tethering APEX 全层级比对：

| 维度 / 指标 | 1. 小米 15 (dada) 官方原始 | 2. K40 (alioth) Milo 移植成功包 | 3. Candidate 45 (挂载突破但校验失败) | 4. Candidate 46 (本次统合修复包) |
| :--- | :--- | :--- | :--- | :--- |
| **容器格式** | `.capex` (17,248,810 B) | `.capex` (17,248,810 B) | `.capex` (17,314,320 B) | **`.capex` (17,314,320 B)** |
| **inner APEX 格式** | 普通 APEX (36,724,736 B) | 普通 APEX (36,724,736 B) | 普通 APEX (36,692,626 B) | **普通 APEX (36,692,626 B)** |
| **inner payload offset** | **4096 字节** | **4096 字节** | **4096 字节** | **4096 字节** |
| **offset % 4096** | **0 (ALIGNED: True)** | **0 (ALIGNED: True)** | **0 (ALIGNED: True)** | **0 (ALIGNED: True)** |
| **payload compress_type** | 0 (STORED) | 0 (STORED) | 0 (STORED) | **0 (STORED)** |
| **inner manifest version** | `370399999` | `370399999` | `370400000` | **`370399999` (已统合)** |
| **outer manifest version** | `370399999` | `370399999` | `370400000` | **`370399999` (已统合)** |
| **payload 内部 manifest** | `370399999` | `370399999` | `370399999` | **`370399999` (已统合)** |
| **AndroidManifest.xml** | `370399999` | `370399999` | `370399999` | **`370399999` (已统合)** |
| **内外 Manifest 字节一致性** | 100% 恒等 | 100% 恒等 | 不一致 (差 2 字节) | **100% 字节级恒等 (PASS)** |
| **payload AVB digest** | `[REDACTED_DEVICE_ID]...` | `[REDACTED_DEVICE_ID]...` | `[REDACTED_DEVICE_ID]...` | **`[REDACTED_DEVICE_ID]...`** |
| **outer originalApexDigest** | `None` (内置基线) | `None` (内置基线) | `[REDACTED_DEVICE_ID]...` | **`[REDACTED_DEVICE_ID]...`** |
| **zipalign -c 4096** | PASS | PASS | PASS (OK) | **PASS (OK)** |

---

## 2. 核心技术决策与根本成因关闭

1. **为什么坚决统合为 `370399999`**：
   - 官方小米 15 基线、K40 移植包、`apex_payload.img` 内部 ext4 文件系统 inode 93（`/apex_manifest.pb`）、以及 `AndroidManifest.xml` 的 `versionCode` **均恒为 `370399999`**；
   - 此前 C43 在外部 manifest 人为将其递增至 `370400000`，由于未修改且不应修改 payload 文件系统镜像内部，导致内外 manifest 产生不可调和的 2 字节分歧（offset 24-25：`\x80\xb6` vs `\xff\xb5`）；
   - AOSP `apexd` 的 `VerifyManifestMatches()` 强制核验内外 manifest 的所有字段（名称、版本、导出库、依赖库），发现外部版本大于内部版本立即拒绝激活；
   - C46 将 inner 与 outer manifest 统一恢复为 `370399999`，实现了跨 4 个层级（AndroidManifest.xml、inner manifest、outer manifest、payload ext4 内部 manifest）的 100% 绝对一致。

2. **保留 Aligned CAPEX 架构的决定性依据**：
   - C45 真机启动证据已经确凿证明：只要满足 4096 字节 ZIP 数据偏移对齐，Linux 内核的 Direct I/O 能够瞬间以 0 错误正常挂载 dm-verity 与 ext4 文件系统；
   - 这一突破证明 CAPEX 架构在当前移植系统上完全成立，无需破坏 Android 17 原生 CAPEX 机制。

---

## 3. Candidate 46 核心指标与门禁验证（100% PASS）

### 1. 资产与补丁完全继承
- **`apex_payload.img` SHA256**：`cf284e425f8c7b9f30dbb09e7ab6010791e69f32cc943d4a2630a98f0b75d347`（与 C45/C44/C43 **100% 字节级恒等**）；
- **patched `libnetd_updatable.so` SHA256**：`a70a3176b82d792cdea3ed876c90980c1d459fbcdb859d5e21f12c3a5eaf92f5`（严格保留 4 字节 NOP 补丁）；
- **Payload AVB root digest**：`4bdfe2f9158035e7d4dd5efe814f5d1dd9eee1d9052eb7c1f571125e9c67e042`；
- **Outer originalApexDigest**：`4bdfe2f9158035e7d4dd5efe814f5d1dd9eee1d9052eb7c1f571125e9c67e042`（严格相等）；
- **既有修复继承**：C40 media codecs variant (`ro.media.xml_variant.codecs=_V1_0`) 与 C42 display configuration (`0.000854597`) 100% 保持生效。

### 2. 4096 字节对齐与签名保护
- **Inner APEX payload offset**：`4096` 字节（`4096 % 4096 == 0`，ALIGNED PASS）；
- **`zipalign -c 4096`**：验证返回 `apex_payload.img (OK)`；
- **`apksigner` v3 签名**：启用 `--alignment-preserved`，签名后数据偏移严格保持 4096 字节。

### 3. EROFS 回读与单变量隔离门禁
- **单变量隔离**：System Tree 与 C40 基线比对严格仅有 1 处差异：`/system/apex/com.android.tethering.capex`；
- **EROFS 回读双重校验**：
  - Staging CAPEX SHA256：`93BEF0A01EE69CFE5F19B8642C47B9CB9361789FBAEE7A2979129DA45BE048C9`；
  - `system_c46.img` 回读 CAPEX SHA256：`93BEF0A01EE69CFE5F19B8642C47B9CB9361789FBAEE7A2979129DA45BE048C9`（**100% 恒等**）；
  - 回读解包 inner APEX 再次通过 `zipalign -c 4096` 验证（OK），内外 Manifest 一致性 100% PASS。

---

## 4. 镜像构建清单与 SHA256

| 镜像文件 | 分区大小 (Bytes) | 实际文件大小 (Bytes) | SHA256 哈希值 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| `system_c46.img` | 1,092,616,192 | 1,092,616,192 | `B84A852E38AA56C0A80E549C4DF4D82E85D75794D775A826EB5BFF0BCB7FC126` | EROFS+AVB (Root Digest: `[REDACTED_DEVICE_ID]...`) |
| `vbmeta_system.img` | 131,072 | 131,072 | `6F8B29322ECBE5BD527505E1444D0E7304A0F56D669475A9529FDA65C48AAFF7` | 更新 system hashtree descriptor |
| `super.img` | 9,126,805,504 | 7,703,526,364 | `A3F39E0771ED23D011E05F31E52643480B2CE960EEBD7D5418B495C7B906E73F` | 包含 system_c46, vendor_c42 等 |
| `vendor_c42.img` | 1,510,998,016 | 1,510,998,016 | `615FC15C287CF81E2871D1BC00A85F5435FF29BA0C49F5D14085198D691924DE` | 继承 C42 屏幕最低亮度修复 |

---

## 5. 刷写前检与受控流程

1. **DRY-RUN 门禁检验**：
   - 执行 `tools/flash_candidate46.ps1 -Serial [REDACTED_DEVICE_ID]`（未带 `-Execute`）；
   - `super.img` 与 `vbmeta_system.img` 大小与 SHA256 校验 100% PASS；
2. **刷写限制红线**：
   - 仅限刷写 `super` 与 `vbmeta_system_a`；
   - 严禁清除 `userdata` / `metadata`；
   - 严禁 Bootloader relock；
   - 刷写完成后严格停留在 Bootloader Fastboot，等待用户明确指令：**“开始启动 C46”**。
