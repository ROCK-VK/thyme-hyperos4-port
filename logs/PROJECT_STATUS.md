# THYME-OS4 项目当前状态

更新时间：2026-10-04 20:40 HKT

## 项目目标与阶段

将 Xiaomi 15（`dada`）HyperOS 4 / Android 17 移植到 Xiaomi 10S（`thyme` / Snapdragon 870）。  
当前阶段：**Candidate 45 首启实测与 Standalone RAM 证据打捞完成；确证 4096 字节对齐彻底消除了内核 loop9 扇区读取错误与 superblock 挂载失败，EXT4 文件系统成功挂载；精准定位全新第一阻塞为 Manifest 版本内外不匹配（内部 370399999 vs 外部 370400000）；正在执行文档闭环与 GitHub 增量同步，准备推进 Candidate 46**。

## 核心有效事实与突破证据

1. **C45 核心突破：内核 Loop 挂载与 Superblock 彻底攻克**：
   - **验证事实**：C44 的 `loop9 sector 0 I/O error`、`EXT4-fs unable to read superblock`、`apexd: Mounting failed: Invalid argument` 在 C45 中 **彻底消除（0 次复现）**；
   - **挂载成功日志**：`[13.903044] EXT4-fs (dm-11): mounted filesystem without journal. Opts:`；
   - 证明 4096 字节扇区对齐假说完全成立且工程修复完全奏效，成功打通了内核块驱动 Direct I/O 屏障。

2. **C45 捕获全新第一阻断点：Manifest 版本内外不匹配**：
   - **真实错误日志**：`apexd: Failed to verify /data/apex/decompressed/[REDACTED_EMAIL]: Manifest inside filesystem does not match manifest outside it`；
   - **根因确认**：`debugfs` 提取 `apex_payload.img` 内部 inode 93（`apex_manifest.pb`）反解，内部版本为 **`370399999`**（来自 dada 官方基线）；而容器外层 manifest 编码为 **`370400000`**（此前人为递增 1 所致）。AOSP `apexd` 的 `VerifyManifestMatches()` 强制比对内部与外部 manifest，因版本号不一致判定文件被篡改并拒绝激活；
   - **连锁故障**：由于 Tethering APEX 激活被拒，其提供的 `libcom.android.tethering.connectivity_native.so` 缺失，导致 Zygote 预加载 `libandroid.so` 循环 abort、SurfaceFlinger 停留在第一屏、netd 无法链接。

3. **Candidate 46 解决路线**：
   - 将 inner 与 outer manifest 的版本统一修正为 **`370399999`**，与 `apex_payload.img` 内部保持 100% 字节一致；
   - 保持 4096 字节对齐与 `--alignment-preserved` 签名机制；
   - 预期实现 Tethering APEX 顺利通过校验并完成 `activate`，首次真正检验 patched netd 运行表现。

4. **历史有效资产 100% 保持有效**：
   - C40 media codecs variant (`ro.media.xml_variant.codecs=_V1_0`) 保持有效；
   - C42 DisplayDeviceConfig 最低亮度修复 (`0.000854597`) 保持有效；
   - C43 netd 4 字节 NOP 兼容性补丁保持有效；
   - C44 originalApexDigest 动态注入逻辑保持有效。

## 当前设备物理状态

- **设备**：Xiaomi 10S (`[REDACTED_DEVICE_ID]`)
- **当前模式**：Bootloader Fastboot（已完成 C45 首启与 RAM 证据打捞，切回 Fastboot 待命）
- **当前槽位**：A 槽（健康）
- **宿主空间门禁**：C 盘 81+ GiB, D 盘 172+ GiB, E 盘 350+ GiB（全绿，远超 50 GiB）
- **Docker/WSL 数据**：100% 零触碰

## 已排除的错误方向与红线纪律

- 严禁清除 `userdata` / `metadata`；
- 严禁修改内核（Kernel）；
- 严禁 Bootloader relock；
- 严禁将 Tethering APEX 改为非压缩格式（dada 和 K40 均保持 CAPEX，C45 已证实内核挂载成功）；
- 固定闭环纪律：查完日志后先进行 GitHub 增量上传和修改 readme，严禁在同步前草率修改下一个 Candidate。

## 下一步最优先任务

1. 完成公开仓库增量同步与 push，提交 C44-C45 证据与分析报告；
2. 推进 Candidate 46 构建与验证。
