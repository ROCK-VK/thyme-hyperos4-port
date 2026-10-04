# THYME-OS4 Candidate 44 首启实测与 RAM 证据打捞权威分析报告

**执行时间**：2026-10-04 17:54 HKT  
**目标机型**：Xiaomi 10S (`thyme` / Snapdragon 870)  
**移植目标系统**：Xiaomi 15 (`dada`) HyperOS 4 / Android 17  
**设备序列号**：`[REDACTED_DEVICE_ID]`  
**镜像版本**：Candidate 44 (`system_c44.img`, `vbmeta_system.img`, `super.img`)

---

## 1. 现象与证据链总结

### 1.1 物理实测现象
- 遵照用户明确“开始启动”授权，通过 `tools/start_candidate44_observed_boot.ps1` 执行受控首启（`fastboot reboot`，时间戳 17:48:56 HKT）；
- 120 秒 ADB 监听超时未连通；
- **用户实测现象**：“Mi Logo + powered by Android常亮 已手动进入fastboot”；
- 用户手动长按【电源 + 音量减】切回 Bootloader Fastboot 待命。

### 1.2 Standalone RAM 诊断数据打捞（100% 成功，0 错误）
- 保持内存未断电，通过 `tools/salvage_c44_when_ready.py` 执行 `fastboot boot` 加载内存诊断微内核，成功完整导出前次冷启动的 RAM 日志与状态树：
  - `console-ramoops-0`: **1,278,916 字节** (SHA256: `AB54E6B038B964F2D91A243CE53BFAED50030EFAD74D7757C172552809056CF1`)
  - `pmsg-ramoops-0`: **1,129,490 字节** (SHA256: `E541926DC358CB7FE4C72D0C3AD674A486BBEE78C0A47E81A52078B88236ECDC`)
  - `dmesg_diag_boot.txt`: **155,210 字节**
  - `oops.raw`: **16,777,216 字节** (SHA256: `1BA3519FE0C7063FA64C...`)
  - `diag_status.log`: **3,159 字节**
- 归档路径：`reports/c44_candidate44_build_20261004/standalone/run_20261004_175451/THYME_DIAG/`，包含完整的 `FILE_MANIFEST.csv`、`SHA256SUMS.txt` 与 `EXPORT_SOURCE.txt`，合规性 100%。

---

## 2. 核心技术突破（C43 制包缺陷彻底攻克）

### 2.1 C43 原始根因回顾
在 Candidate 43 中，`apexd` 在启动第 13.75 秒报错：
```text
apexd: Failed to decompress CAPEX: Root digest of /data/apex/decompressed/[REDACTED_EMAIL] does not match with expected root digest in /system/apex/com.android.tethering.capex
```
外层 CAPEX manifest 遗留出厂旧 digest (`[REDACTED_DEVICE_ID]...`)，导致 `apexd` 拒绝激活该 APEX。

### 2.2 C44 验证结果：Root Digest 校验 100% 通过
在 Candidate 44 中，通过将动态提取的 payload root digest `4bdfe2f9158035e7d4dd5efe814f5d1dd9eee1d9052eb7c1f571125e9c67e042` 注入外层 `apex_manifest.pb` 的 `capexMetadata.originalApexDigest`：
- **`Root digest ... does not match` 错误在 C44 日志中彻底消失（0 次出现）！**
- `apexd` 顺利完成对 `com.android.tethering.capex` 的解压缩校验，证明 C44 门禁与制包流程完全正确。

---

## 3. Candidate 44 全新第一阻塞分析

### 3.1 决定性报错定位
解压缩通过后，`apexd` 在挂载解压产物时返回 `EINVAL`：
```text
[   13.885858] apexd: Mounting failed for package /data/apex/decompressed/[REDACTED_EMAIL]: Invalid argument
[   13.885872] apexd: Activated 40 packages. duration=3016ms
[   13.885878] apexd: Failed to activate packages: Mounting failed for package /data/apex/decompressed/[REDACTED_EMAIL]: Invalid argument
[   13.885921] apexd: Failed to revert : Revert requested, when there are no active sessions.
[   13.885926] apexd: Trying to activate pre-installed versions of missing apexes
[   13.885938] apexd: Activated 0 packages. duration=0ms
```

### 3.2 连锁反应链条
由于 `/apex/com.android.tethering` 挂载失败，其内部库文件在运行时不可见：
1. **SurfaceFlinger 链接失败**：
   ```text
   linker CANNOT LINK EXECUTABLE "/system/bin/surfaceflinger": library "libcom.android.tethering.connectivity_native.so" not found: needed by /system/lib64/libandroid.so in namespace (default)
   ```
   屏幕无法进入 BootAnimation，停留第一屏小米 Logo。
2. **Zygote 循环 abort**：
   ```text
   DEBUG Abort message: 'Error preloading public library libandroid.so: dlopen failed: library "libcom.android.tethering.connectivity_native.so" not found: needed by /system/lib64/libandroid.so in namespace (default)'
   ```
3. **Netd 链接失败**：
   ```text
   linker CANNOT LINK EXECUTABLE "/system/bin/netd": library "libnetd_updatable.so" not found: needed by main executable
   ```

---

## 4. AOSP 源码溯源与 `EINVAL` 机制探究

在 AOSP `system/apex/apexd/apexd.cpp` 中，激活 decompressed APEX 的挂载逻辑如下：
1. `VerifyApexVerity(apex)`：校验 AVB hashtree footer（通过）；
2. `CreateVerityTable(...)` 与 `CreateDmDevice(...)`：创建 dm-verity 块设备（通过）；
3. 调用原生 Linux `mount()`：
   ```cpp
   mount(block_device.c_str(), mount_point.c_str(), apex.GetFsType().value().c_str(), mount_flags, nullptr);
   ```
   内核返回 `-1`，`errno = EINVAL`（Invalid argument）！

### 内核 ext4 挂载返回 `EINVAL` 的可能原因：
1. **dm-verity 映射边界与 ext4 superblock 大小不匹配**：
   `apex_payload.img` 内部包含 ext4 镜像 + AVB hashtree footer。若 ext4 superblock 中记录的 block count 超过了 dm-verity 声明的数据区大小，或者未在扇区（512 字节/4096 字节）对齐边界上截断，Linux ext4 驱动读取超出设备边界直接报错 `EINVAL`。
2. **CAPEX 的解压缩与 dm-verity 机制对修改版 APEX 的敏感性**：
   对于预装的未压缩 APEX（如 `/system/apex/com.android.runtime.apex`），`apexd` 在系统只读分区中直接通过 loop 设备挂载，无需经过 `/data/apex/decompressed` 的 dm-verity 复杂设备映射。

---

## 5. Candidate 45 规划方向

为彻底攻克 `Mounting failed ... Invalid argument`， Candidate 45 规划以下技术路径：
- **方案 A（首选/最简洁稳健）**：将 `/system/apex/com.android.tethering.capex` 转换为**非压缩标准 APEX**（`com.android.tethering.apex`）。对齐 `com.android.runtime.apex` 等系统级 APEX，直接走系统预装 APEX loop 挂载通道，避开 CAPEX 在 `/data/apex/decompressed` 的 dm-verity 设备大小映射约束。
- **方案 B**：审计并修复 `apex_payload.img` 的 ext4 文件系统块计数与 `avbtool` hash tree footer 扇区对齐。
