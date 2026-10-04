# Candidate 45 构建与刷写就绪报告：Aligned CAPEX 4096 字节对齐修复与多重门禁验证

**设备**：Xiaomi 10S (`thyme` / Snapdragon 870)  
**基线目标**：Xiaomi 15 (`dada`) 官方 HyperOS 4 / Android 17  
**Candidate 版本**：Candidate 45 (Aligned CAPEX Tethering & System Integration)  
**构建日期**：2026-10-04  
**刷写状态**：已完成受控物理刷写，严格停留在 Bootloader Fastboot，等待人工启动指令  

---

## 1. K40 / dada / C44 三方 Tethering APEX 定点对照

针对此前 C44 首启捕获的 `apexd` 挂载解压 APEX 报 `Invalid argument (EINVAL)`、内核虚拟 loop 设备 `dev loop9, sector 0: I/O error` 以及 `dm-11: unable to read superblock`，本项目实施了定点三方 APEX 容器与 payload 对齐解构对比：

| 维度 / 指标 | 1. 小米 15 (dada) 官方原始 | 2. K40 (alioth) Milo 移植成功包 | 3. Candidate 44 (当前失败包) | 4. Candidate 45 (本次修复包) |
| :--- | :--- | :--- | :--- | :--- |
| **容器格式** | `.capex` (17,248,810 B) | `.capex` (17,248,810 B) | `.capex` (17,297,936 B) | **`.capex` (17,314,320 B)** |
| **解包 inner APEX 格式** | 普通 APEX (36,724,736 B) | 普通 APEX (36,724,736 B) | 普通 APEX (36,704,909 B) | **普通 APEX (36,692,626 B)** |
| **inner payload offset** | **4096 字节** | **4096 字节** | **52 字节** | **4096 字节** |
| **offset % 4096** | **0 (ALIGNED: True)** | **0 (ALIGNED: True)** | **52 (ALIGNED: False)** | **0 (ALIGNED: True)** |
| **offset % 512** | **0 (ALIGNED: True)** | **0 (ALIGNED: True)** | **52 (ALIGNED: False)** | **0 (ALIGNED: True)** |
| **payload compress_type** | 0 (STORED) | 0 (STORED) | 0 (STORED) | **0 (STORED)** |
| **inner manifest version** | `370399999` | `370399999` | `370400000` | **`370400000`** |
| **outer manifest version** | `370399999` | `370399999` | `370400000` | **`370400000`** |
| **payload AVB digest** | `[REDACTED_DEVICE_ID]...` | `[REDACTED_DEVICE_ID]...` | `[REDACTED_DEVICE_ID]...` | **`[REDACTED_DEVICE_ID]...`** |
| **outer originalApexDigest** | `None` (内置基线) | `None` (内置基线) | `[REDACTED_DEVICE_ID]...` | **`[REDACTED_DEVICE_ID]...`** |
| **zipalign -c 4096** | PASS | PASS | FAIL (BAD - 52) | **PASS (OK)** |

### 对照结论与架构决策

1. **为什么最终坚决选择保留 CAPEX 架构，而不改成非压缩 `.apex`**：
   - 小米 15 官方基线与 K40 成功移植包**均完全保持原生 `.capex` 压缩包架构**；
   - 证明 `apexd` 在 Android 17 / HyperOS 4 下完全支持且原生依赖 CAPEX 机制；
   - C44 的真正失败诱因并非 CAPEX 机制本身，而是 inner APEX 重新封装时遺漏了 4096 字节扇区对齐。未对齐的 loop 虚拟块设备执行 Direct I/O 时直接被内核驱动层拒绝（`sector 0 I/O error`）；
   - 只要修复 inner APEX 的 4096 字节 ZIP 对齐，即可在不破坏系统 APEX 架构的前提下实现无缝激活。

---

## 2. 工具链深层机制发现与修复方案

### AOSP `apksigner` 对齐破坏机理
在测试 `zipalign -f 4096` -> `apksigner sign` 流程时，发现了一个关键隐蔽陷阱：
- Android SDK build-tools 36.0.0 的 `apksigner` 在对 APK/APEX 执行 v3 签名时，其参数 `--alignment-preserved` 默认值为 `false`；
- 当 `--alignment-preserved false` 时，`apksigner` 会主动剥离除 `.so` 以外所有条目的对齐填充，将普通未压缩文件（包括 `apex_payload.img`）强制重置为 4 字节对齐！
- 这正是 C43 与 C44 在重构 inner APEX 时对齐丢失的根本原因。

### Candidate 45 闭环工艺
1. **构造无签名 inner APEX**：将 `apex_payload.img` 作为首个条目以 `ZIP_STORED` 写入；
2. **执行 4096 对齐**：`zipalign.exe -f 4096 unsigned.apex aligned.apex`，生成数据偏移为 4096 字节（Local Header 30B + 文件名 16B + 填充 4050B = 4096B）；
3. **启用对齐保护签名**：`apksigner.bat sign --key ... --cert ... --v2-signing-enabled false --v3-signing-enabled true --alignment-preserved --out signed.apex aligned.apex`；
4. **双重硬核门禁核验**：
   - `signed.apex` 数据偏移实测为 4096（`4096 % 4096 == 0`）；
   - `zipalign -c 4096 signed.apex` 严格验证返回 0（`apex_payload.img (OK)`）；
   - `apksigner verify --verbose` 确证 v3 签名有效。

---

## 3. Candidate 45 核心指标与门禁验证

### 1. 资产与补丁完全继承
- **`apex_payload.img` SHA256**：`cf284e425f8c7b9f30dbb09e7ab6010791e69f32cc943d4a2630a98f0b75d347`（与 C44/C43 **100% 字节级恒等**）；
- **patched `libnetd_updatable.so` SHA256**：`a70a3176b82d792cdea3ed876c90980c1d459fbcdb859d5e21f12c3a5eaf92f5`（严格保留 4 字节 NOP 补丁，零重复修改）；
- **Payload AVB root digest**：`4bdfe2f9158035e7d4dd5efe814f5d1dd9eee1d9052eb7c1f571125e9c67e042`；
- **Outer originalApexDigest**：`4bdfe2f9158035e7d4dd5efe814f5d1dd9eee1d9052eb7c1f571125e9c67e042`（严格相等，完全消除 C43 错误）；
- **既有修复继承**：C40 media codecs variant (`ro.media.xml_variant.codecs=_V1_0`) 与 C42 display configuration (`0.000854597`) 100% 保持生效。

### 2. 版本号事实纠正与统合
- **查明事实**：经对 C43、C44、C45 的 `apex_manifest.pb` 原始 protobuf 字节流（varint 字段 tag 2 值为 `\x80\xb6\xcf\xb0\x01`）反解，其实际真实编码版本号均为 `370400000`；
- **纠正说明**：此前个别文档推算的 `370400128` 确认为历史推算误记，C45 统一保持内部与外部 manifest 真实编码 `370400000`。

### 3. EROFS 回读与单变量隔离门禁
- **单变量隔离**：System Tree 与 C40 基线比对严格仅有 1 处差异：`/system/apex/com.android.tethering.capex`；
- **EROFS 回读双重校验**：
  - Staging CAPEX SHA256：`ACCB09B26FE97166F1FAE46FC5F9F95722154AB39EF9C360E7CE8538BABA4843`；
  - `system_c45.img` 回读 CAPEX SHA256：`ACCB09B26FE97166F1FAE46FC5F9F95722154AB39EF9C360E7CE8538BABA4843`（**100% 恒等**）；
  - 回读解包 inner APEX 再次通过 `zipalign -c 4096` 验证（OK）。

---

## 4. 镜像构建清单与 SHA256

| 镜像文件 | 分区大小 (Bytes) | 实际文件大小 (Bytes) | SHA256 哈希值 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| `system_c45.img` | 1,092,616,192 | 1,092,616,192 | `EA8235C2059527D0098C8D4CF0FFCB75EA60E01DB5616581450D448DD0106ECE` | EROFS+AVB (Root Digest: `[REDACTED_DEVICE_ID]...`) |
| `vbmeta_system.img` | 131,072 | 131,072 | `AB36B0D874EC18870EA0FADE77F4923496F13FD5C33CFCA5581A1FEE54B6A837` | 更新 system hashtree descriptor |
| `super.img` | 9,126,805,504 | 7,703,526,364 | `A4DD2E0A59492E297586CAD7FE2E3DC31847163EBE507A991808EFB0D8CB5AB3` | 包含 system_c45, vendor_c42 等 |
| `vendor_c42.img` | 1,510,998,016 | 1,510,998,016 | `615FC15C287CF81E2871D1BC00A85F5435FF29BA0C49F5D14085198D691924DE` | 继承 C42 屏幕最低亮度修复 |

---

## 5. 受控物理刷写与设备驻留状态

刷写工具：`tools/flash_candidate45.ps1`  
日志文件：`reports/c45_candidate45_build_20261004/C45_FLASH_20261004_121152_440.txt`  

1. **前置安全审计**：
   - 目标设备：`[REDACTED_DEVICE_ID]`（唯一在线）
   - `product`: `thyme`
   - `unlocked`: `yes`
   - `current-slot`: `a`
   - `is-userspace`: `no`（Bootloader Fastboot）
2. **启动预算恢复**：
   - 执行 `fastboot set_active a`，成功将 A 槽启动重试预算（`slot-retry-count:a`）从 6 恢复为 **7**；
3. **受控写入分区**：
   - `super`：10 个 sparse 分片依次写入，耗时 201.1s，退出码 0；
   - `vbmeta_system_a`：写入耗时 12.4s，退出码 0；
4. **刷写后状态回读快照**：
   - `product`: `thyme`
   - `current-slot`: `a`
   - `unlocked`: `yes`
   - `is-userspace`: `no`
   - `slot-unbootable:a`: `no`
   - `slot-successful:a`: `no`
   - `slot-retry-count:a`: **7**
   - `slot-unbootable:b`: `no`
   - `slot-retry-count:b`: `7`
5. **红线纪律执行**：
   - 未执行 `fastboot reboot`；
   - 未擦除 `userdata` 或 `metadata`；
   - 永久禁止 Bootloader relock；
   - 设备安全驻留在 Bootloader Fastboot 待命。

---

## 6. 人工确认节点与后续行动

当前 Candidate 45 已 100% 完成构建、双重 EROFS 回读门禁与物理受控刷写，设备当前处于 Bootloader Fastboot 模式。

根据第八步唯一人工确认节点要求，**严格等待用户下达明确指令**：

> **“开始启动 C45”**

收到指令后将立即触发 `tools/start_candidate45_observed_boot.ps1` 执行受控首启并进行 120s ADB 监听与现场观测。
