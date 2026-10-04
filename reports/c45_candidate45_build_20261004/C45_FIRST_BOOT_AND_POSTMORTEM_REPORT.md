# Candidate 45 首启实测与深入证据分析报告：内核 Loop 挂载与 Superblock 彻底攻克，精准定位 Manifest 版本内外不匹配为新第一阻塞

**设备**：Xiaomi 10S (`thyme` / Snapdragon 870)  
**基线目标**：Xiaomi 15 (`dada`) 官方 HyperOS 4 / Android 17  
**Candidate 版本**：Candidate 45 (Aligned CAPEX Tethering & System Integration)  
**测试日期**：2026-10-04  
**证据归档**：`reports/c45_candidate45_build_20261004/standalone/run_20261004_202821/THYME_DIAG/`  

---

## 1. 实测现象与观测窗口

1. **受控首启流程**：
   - 使用 `tools/start_candidate45_observed_boot.ps1`，前置门禁全绿（A 槽预算 = 7，unlocked = yes）；
   - 执行 `fastboot reboot` 正式触发首启，进入 120 秒 ADB 监听窗口；
   - 120 秒内 ADB 未建立连接；
2. **真机物理屏幕状态**：
   - 屏幕停留在第一屏 **Mi Logo + powered by Android** 常亮；
   - 用户按无损打捞规程通过【音量下 + 电源键】手动切入 Bootloader Fastboot（RAM 未断电）；
3. **证据打捞闭环**：
   - 执行 `tools/salvage_c45_when_ready.py`，Standalone 诊断微内核无损打捞 DDR RAM 日志 100% 成功；
   - 完整保全 `console-ramoops-0` (1,398,459 字节) 与 `pmsg-ramoops-0` (1,262,381 字节)；
   - 生成完整 `SIZE_MANIFEST.txt` 与 `SHA256SUMS.txt`。

---

## 2. 关键突破：C44 的内核 Loop 扇区错误与 Superblock 挂载失败 100% 消除

对比 C44 与 C45 的 `console-ramoops-0` 内核日志，证明 4096 字节 ZIP 对齐假说完全成立且工程修复完全奏效：

| 故障指标 | Candidate 44 实机日志 | Candidate 45 实机日志 | 证据结论 |
| :--- | :--- | :--- | :--- |
| **Root digest mismatch** | 0 次复现（已修复） | **0 次复现** | C44 动态 digest 注入逻辑持续有效 |
| **`loop9 sector 0 I/O error`** | 频繁报错（Direct I/O 未对齐） | **0 次复现（彻底消失）** | 4096 字节对齐成功消除了内核块设备扇区拒绝 |
| **`EXT4-fs unable to read superblock`** | 致命报错，superblock 无法读取 | **0 次复现（彻底消失）** | 内核块驱动成功读取到 ext4 superblock |
| **`apexd: Mounting failed: Invalid argument`** | 报 EINVAL 挂载失败 | **0 次复现（彻底消失）** | Linux `mount()` 挂载系统调用成功执行 |
| **ext4 文件系统挂载状态** | 失败 | **`[13.903044] EXT4-fs (dm-11): mounted filesystem without journal. Opts:`** | **内核与 dm-verity 成功挂载 `dm-11` 文件系统！** |

---

## 3. 全新第一阻塞深度剖析：Manifest 版本内外不匹配

在 ext4 文件系统成功被内核与 dm-verity 挂载后，`apexd` 在激活前执行了标准安全校验：

### 1. 真实故障日志
```text
[   13.903044] EXT4-fs (dm-11): mounted filesystem without journal. Opts: 
...
[   14.030859] apexd: Failed to verify /data/apex/decompressed/[REDACTED_EMAIL]: Manifest inside filesystem does not match manifest outside it
[   14.030892] apexd: Activated 40 packages. duration=3003ms
[   14.030914] apexd: Failed to activate packages: Failed to verify /data/apex/decompressed/[REDACTED_EMAIL]: Manifest inside filesystem does not match manifest outside it
```

### 2. 根因机制分析（AOSP `apexd` 校验逻辑）
根据 AOSP `apexd` 源码实现，在挂载 APEX payload 文件系统到临时挂载点后，`apexd` 会执行 `VerifyManifestMatches()`：
- 读取挂载点内部的 `/apex/.../apex_manifest.pb`（存储在 `apex_payload.img` ext4 文件系统内部）；
- 读取 APEX 容器外层的 `apex_manifest.pb`（存储在 ZIP 容器根目录）；
- 逐字段比对两者（包括 `name`, `version`, `versionName` 等）；
- 若两者不一致，直接判定包体遭到篡改，报错：  
  **`Manifest inside filesystem does not match manifest outside it`** 并拒绝激活该 APEX！

### 3. 本地取证与十六进制实证
使用 `debugfs` 从 C45 `apex_payload.img` 中提取内部 inode 93（`apex_manifest.pb`），并与容器外层 `apex_manifest.pb` 逐字节比对：
```text
Payload manifest len: 598
ZIP manifest len:     598
Byte diffs count: 2
  offset 24: payload=0xff vs zip=0x80
  offset 25: payload=0xb5 vs zip=0xb6

Payload raw bytes 22..30: 6710ffb5cfb0013a -> Varint decode: 370399999
ZIP raw bytes 22..30:     671080b6cfb0013a -> Varint decode: 370400000
```
- **内部 manifest**（`apex_payload.img` 中封装的）：版本号为 **`370399999`**（来自官方 dada 基线）；
- **外部 manifest**（ZIP 容器与 CAPEX 外层）：版本号为 **`370400000`**（此前 C43 打包时人为递增了 1）；
- **比对结果**：外部版本与内部版本相差 1，触发 `apexd` 校验拒绝，导致 Tethering APEX 虽成功解压且成功 mount，但在最终激活阶段被抛弃。

### 4. 连锁故障表征
由于 `com.android.tethering` 激活被拒，其提供的库未进入链接器命名空间：
- `Zygote`: `Error preloading public library libandroid.so: dlopen failed: library "libcom.android.tethering.connectivity_native.so" not found`（循环 abort）；
- `SurfaceFlinger`: 缺失 `libcom.android.tethering.connectivity_native.so`，停留在第一屏；
- `netd`: 缺失 `/apex/com.android.tethering/lib64/libnetd_updatable.so`，导致后续网络栈阻塞。

---

## 4. Candidate 46 解决路径

由于 `apex_payload.img` 内部包含 AVB hashtree 且其文件系统内部 manifest 版本为 `370399999`，最安全、最小侵入的修复路径为：
1. **统一容器内外版本号为 `370399999`**：
   - 将 inner APEX 容器外层的 `apex_manifest.pb` 直接替换为 `apex_payload.img` 内部相同的 `370399999` 清单；
   - 将 outer CAPEX 容器外层的 `apex_manifest.pb` 也同步采用 `370399999`（附加 `capexMetadata.originalApexDigest = [REDACTED_DEVICE_ID]...`）；
   - 保持 4096 字节对齐（`zipalign -f 4096`）与 `--alignment-preserved` 签名；
2. **预期效果**：
   - 内核挂载 `dm-11` 保持成功；
   - `apexd` 比对内部 manifest 与外部 manifest 达到 100% 字节一致；
   - `com.android.tethering` 顺利通过校验并完成 `activate`；
   - `libcom.android.tethering.connectivity_native.so` 成功供 Zygote/SurfaceFlinger 加载；
   - `libnetd_updatable.so`（4 字节 NOP）首次迎来真正的实机执行检验！
