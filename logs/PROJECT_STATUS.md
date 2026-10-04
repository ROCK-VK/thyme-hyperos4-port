# THYME-OS4 项目当前状态

更新时间：2026-10-04 12:40 HKT

## 项目目标与阶段

将 Xiaomi 15（`dada`）HyperOS 4 / Android 17 移植到 Xiaomi 10S（`thyme` / Snapdragon 870）。  
当前阶段：**Candidate 43 最小外科手术修复、APEX v3 重签、系统构建与 6 重深度静态门禁 100% 验收全绿通过；就绪等待手机切入 Fastboot 刷入并等待用户开机授权**。

## 核心有效事实与突破证据

1. **C42 历史性成果 100% 继承并保持有效**：
   - `/vendor/etc/displayconfig/display_id_4630946545580055169.xml` 屏幕亮度下界修复（`<value>0.000854597</value>`）；
   - `DisplayDeviceConfig` 异常彻底归零，内置屏幕成功注册，`SF.setDisplayPowerMode` 生效，`BootAnimation` (PID 2082) 成功拉起；
   - 系统跨越 Phase 100 推进至 **Boot Phase 200**，用户 0 加密存储（CE Storage）成功解锁。

2. **C43 目标：解除全新第 1 致命阻断点（Netd eBPF Abort 死循环 & Watchdog 击毙）**：
   - **根本原因**：`netd` 在启动时由于 `/apex/com.android.tethering/lib64/libnetd_updatable.so (libnetd_updatable_init)` 中检测 4.19 内核 (< 5.4.0) 触发 `abort()`（C42 运行中死循环崩溃 62 次），导致 `INetd` 无法注册，SystemServer 主线程在 `NetdService.get()` 死等 67 秒遭 Watchdog 处决。
   - **C43 外科手术修复方案（方案 A）**：
     - 在 `libnetd_updatable.so` 偏移 `0x11534` 将分支指令 `cbnz w8, 115d8` (`0x28 0x05 0x00 0x35`) 改为 `nop` (`0x1f 0x20 0x03 0xd5`)，严格仅修改 4 个字节；
     - 正常执行 `InitLogging`、`LOG(INFO)` 与 `sBpfHandler.init`，失败时安全释放内存并恒等返回 0（成功）；
     - `BpfHandler` 后续方法具有 `!mCookieTagMap.isValid()` 空安全检查，零内存越界风险；
     - `apex_manifest.pb` 版本号递增至 `370400128`，强制 `apexd` 开机淘汰 `/data/apex/decompressed` 旧缓存；
     - 使用 RSA-4096 密钥与 Android SDK 36 `apksigner` 完成双层 APK Signature Scheme v3 签名校验（v3: true）；
     - `system_tree` 与 C40 基线相比严格仅 `com.android.tethering.capex` 发生单变量变动。

3. **6 重深度静态门禁验证结果（100% PASS）**：
   - Gate 1 (SO 二进制/ELF/CFG): PASS（严格 4 字节，AArch64，7 项动态依赖无变化）；
   - Gate 2 (APEX 容器与 APK v3 签名): PASS（外层与内层 v3 scheme: true，版本 370400128）；
   - Gate 3 (System EROFS 回读): PASS（`build.prop` 包含 `ro.media.xml_variant.codecs=_V1_0`，capex 回读哈希一致）；
   - Gate 4 (AVB 签名树): PASS（Root Digest 精准对齐 `[REDACTED_DEVICE_ID]...`）；
   - Gate 5 (Super LP 元数据): PASS（动态分区完整，内置 vendor 确认包含 C42 屏幕修复点 `0.000854597`）；
   - Gate 6 (单变量隔离度): PASS（系统树 diff 严格仅 1 个文件，vendor 哈希恒等）。

## 当前关键文件与构建镜像 (C43)

- `super.img`: `7,703,526,364` 字节 (SHA256: `D22390FA17B50909F6C87DA495DD35CF5EA962F8A7094CFD73F056D92626B778`)
- `system_c43.img`: `1,092,616,192` 字节 (SHA256: `78EDD0C2AB18C06056B3C5B92FD79E7B6E6305B7504785B239BF0C5EB19E3574`)
- `vbmeta_system.img`: `131,072` 字节 (SHA256: `0C00581C29E7888E473BF4B97F2F88DA2DD08CA188A776B7C06BC4B22854ECCF`)
- `vendor_c42.img`: `1,510,998,016` 字节 (SHA256: `615FC15C287CF81E2871D1BC00A85F5435FF29BA0C49F5D14085198D691924DE`)
- 刷写工具：[`tools/flash_candidate43.ps1`](file:///[LOCAL_PROJECT_ROOT]/tools/flash_candidate43.ps1) (Dry-run 已通过)

## 当前设备物理状态

- **设备**：Xiaomi 10S (`[REDACTED_DEVICE_ID]`)
- **当前模式**：Standalone RAM 诊断环境（宿主机挂载为只读磁盘 `G:\`，保存有完整 C42 首启取证数据）
- **槽位健康度**：A 槽当前 `retry=1`（`unbootable=no`），将在刷写时通过受控 `fastboot set_active a` 恢复至 `retry=7`
- **宿主空间门禁**：C=82.13 GiB, D=177.89 GiB, E=369.00 GiB（全绿，远超 50 GiB 安全门禁）

## 已排除的错误方向与红线纪律

- 严禁粗暴将整个 `libnetd_updatable_init()` 替换为 `mov w0,#0; ret`（必须保留日志与探测过程）；
- 严禁修改内核（Kernel）；
- 严禁修改 `NetworkManagementService` 或关闭 Watchdog；
- 严禁触碰 `persist/modemst/efs/nv/radio/identity` 分区；
- **首启纪律**：刷写后严格保留在 Bootloader Fastboot，未收到用户“开始启动 C43”明确授权前，**绝对不执行 `fastboot reboot`**。

## 下一步最优先任务

1. 提示用户手动长按手机【电源键 + 音量下键】退出 Standalone 诊断环境，重新切入 Bootloader Fastboot 模式；
2. 运行 `tools/flash_candidate43.ps1 -Serial "[REDACTED_DEVICE_ID]" -Execute -RestoreRetryBudget`：
   - 执行受控 `fastboot set_active a`（恢复 A 槽预算至 7）；
   - 刷写 `super` 与 `vbmeta_system_a`；
   - 重新读取并验证 Slot A 状态；
3. 停留在 Bootloader Fastboot，汇报就绪，等待用户指令：“开始启动 C43”。
