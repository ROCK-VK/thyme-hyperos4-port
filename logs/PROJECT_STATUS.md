# THYME-OS4 项目当前状态

更新时间：2026-10-04 18:15 HKT

## 项目目标与阶段

将 Xiaomi 15（`dada`）HyperOS 4 / Android 17 移植到 Xiaomi 10S（`thyme` / Snapdragon 870）。  
当前阶段：**Candidate 44 已完成首启实测与 Standalone RAM 证据打捞；确证 C43 Root Digest 制包错误 100% 修复；锁定全新第一阻塞为 `apexd` 挂载解压 APEX 报 `Invalid argument` (EINVAL)；正在准备 Candidate 45 修复方案**。

## 核心有效事实与突破证据

1. **C42 历史性成果 100% 保持有效**：
   - 内置屏幕 DisplayDeviceConfig 最低亮度修复（`<value>0.000854597</value>`）；
   - 内置屏幕成功连接并置供电 `state=ON`。

2. **C44 核心突破：C43 Root Digest 错误彻底根除**：
   - **验证事实**：C43 中的 `Root digest of ... does not match with expected root digest in /system/apex/com.android.tethering.capex` 在 C44 中 **100% 消除**（0 次复现）；
   - `apexd` 成功校验并解压缩 `com.android.tethering.capex`，证实动态注入 `originalApexDigest` (`[REDACTED_DEVICE_ID]...`) 的制包逻辑完全正确。

3. **C44 捕获全新第一阻断点**：
   - **错误现象**：`apexd: Mounting failed for package /data/apex/decompressed/[REDACTED_EMAIL]: Invalid argument`；
   - **连锁故障**：由于 Tethering APEX 挂载失败，SurfaceFlinger 无法加载 `libcom.android.tethering.connectivity_native.so` 导致屏幕停留在第一屏 Mi Logo；Zygote 预加载 `libandroid.so` 循环 abort；Netd 无法链接 `libnetd_updatable.so`；
   - **取证保全**：通过 Standalone RAM 诊断微内核完整打捞出 1.28MB `console-ramoops-0` 与 1.13MB `pmsg-ramoops-0`，全量归档于 `reports/c44_candidate44_build_20261004/standalone/run_20261004_175451/THYME_DIAG/`。

4. **Candidate 45 技术路线**：
   - 目标：攻克 `apexd` 挂载 `com.android.tethering` 的 `EINVAL` 错误；
   - 首选方案 A：将 `/system/apex/com.android.tethering.capex` 转换为非压缩标准 APEX（`com.android.tethering.apex`），对标 `com.android.runtime.apex` 直接由 loop 设备挂载，彻底规避 CAPEX 在 `/data/apex/decompressed` 下的 dm-verity 映射对齐约束。

## 当前设备物理状态

- **设备**：Xiaomi 10S (`[REDACTED_DEVICE_ID]`)
- **当前模式**：Bootloader Fastboot（已完成 RAM 取证并切回 Fastboot 待命）
- **当前槽位**：A 槽（健康）
- **宿主空间门禁**：C 盘 81+ GiB, D 盘 172+ GiB, E 盘 358+ GiB（全绿，远超 50 GiB）
- **Docker/WSL 数据**：100% 零触碰

## 已排除的错误方向与红线纪律

- 严禁清除 `userdata` / `metadata`；
- 严禁修改内核（Kernel）；
- 严禁 Bootloader relock；
- 固定闭环纪律：查完日志后先进行 GitHub 增量上传和修改 readme，严禁在同步前草率修改下一个 Candidate。

## 下一步最优先任务

1. 完成公开仓库增量同步与 push，提交最新证据与报告；
2. 推进 Candidate 45 构建与验证。
