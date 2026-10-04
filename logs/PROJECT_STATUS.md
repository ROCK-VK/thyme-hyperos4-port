# THYME-OS4 项目当前状态

更新时间：2026-10-04 15:40 HKT

## 项目目标与阶段

将 Xiaomi 15（`dada`）HyperOS 4 / Android 17 移植到 Xiaomi 10S（`thyme` / Snapdragon 870）。  
当前阶段：**Candidate 43 完成受控首启与 RAM 证据打捞；设备停留在第一屏（Mi Logo），根本原因 100% 闭环确证为 CAPEX 外层 manifest 缺少更新后的 originalApexDigest，导致 apexd 拒绝激活 Tethering APEX 并阻断 SurfaceFlinger/Zygote；当前正在构建 Candidate 44 彻底消除该阻断**。

## 核心有效事实与突破证据

1. **C42 历史性成果 100% 保持有效**：
   - 内置屏幕 DisplayDeviceConfig 最低亮度修复（`<value>0.000854597</value>`）；
   - 内置屏幕成功连接并置供电 `state=ON`。

2. **C43 首启实测与根本原因分析（闭环确认）**：
   - **现象**：设备停留在第一屏（Mi Logo + powered by Android），未进入第二屏 BootAnimation。用户手动切入 Fastboot，通过 Standalone RAM 诊断无损打捞出 1.57MB `console-ramoops-0` 与 1.46MB `pmsg-ramoops-0`。
   - **根本原因**：
     * `[ 13.758144] apexd: Failed to decompress CAPEX: Root digest of /data/apex/decompressed/[REDACTED_EMAIL] does not match with expected root digest in /system/apex/com.android.tethering.capex`；
     * `apexd` 拒绝激活 `com.android.tethering`，导致 `/apex/com.android.tethering/` 未挂载；
     * `surfaceflinger` 报 `library "libcom.android.tethering.connectivity_native.so" not found` 无法启动；
     * `zygote` 在 preload `libandroid.so` 时因同样缺失该库直接 `abort()` 崩溃；
   - **AOSP 标准机制溯源**：
     * 依据 AOSP `apex_compression_tool.py` 官方源码：CAPEX 容器外层的 `apex_manifest.pb` 中定义了 `capexMetadata.originalApexDigest`，其值必须由 `avbtool print_partition_digests --image apex_payload.img` 动态计算并注入；
     * C43 构建时外层 manifest 保留了出厂旧 digest (`[REDACTED_DEVICE_ID]...`)，而实际重新签名的 `apex_payload.img` 的 root digest 是 `4bdfe2f9158035e7d4dd5efe814f5d1dd9eee1d9052eb7c1f571125e9c67e042`，导致 `apexd` 校验失败抛弃激活。

3. **Candidate 44 解决方案**：
   - 严格按照 AOSP `apex_compression_tool.py` 标准：
     * 从最新的 `apex_payload.img` 提取 `root_digest = 4bdfe2f9158035e7d4dd5efe814f5d1dd9eee1d9052eb7c1f571125e9c67e042`；
     * 将 `capexMetadata.originalApexDigest` 正确写入外层 `apex_manifest.pb`；
     * 版本号递增至 `370400129`（强制 `apexd` 清除所有解压缓存并重新生效）；
     * 重新打包并完成双层 APK v3 签名、EROFS 与 AVB 完整流程；
   - 保持单变量原则：仅且仅修复 `originalApexDigest` 与版本号。

## 当前设备物理状态

- **设备**：Xiaomi 10S (`[REDACTED_DEVICE_ID]`)
- **当前模式**：Bootloader Fastboot（已完成 RAM 证据导出，安全待命）
- **槽位健康度**：A 槽（健康）
- **宿主空间门禁**：C/D/E 盘空间充足（均 > 80 GiB）

## 已排除的错误方向与红线纪律

- 严禁使用未包含 `originalApexDigest` 的外层 CAPEX manifest；
- 严禁修改内核（Kernel）；
- 严禁粗暴关闭 Watchdog 或触碰底层硬件/基带分区；
- 未经用户授权前绝不执行非受控重启。

## 下一步最优先任务

1. 编写 Candidate 44 构建脚本（遵循 `apex_compression_tool.py` 注入正确的 `originalApexDigest`）；
2. 执行 Candidate 44 构建并跑通 6 重深度静态门禁；
3. 将构建与门禁结果向用户汇报，征求刷写授权。

