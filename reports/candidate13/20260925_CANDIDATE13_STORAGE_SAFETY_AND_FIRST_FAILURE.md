# THYME-OS4 Candidate 13 存储安全与首次故障取证准备报告

日期：2026-09-25（Asia/Hong_Kong）  
执行范围：主机侧静态分析、诊断观察器修改、Candidate 13.1 数据保护变体构建与静态验证。**本轮未对手机执行 ADB/Fastboot 状态变更、刷写、重启、RAM 启动、BCB/misc 写入或数据分区操作。**

## 结论与实验决策

- 原版 C13 的正常启动 fstab 同时给 `/metadata`、`/data` 配置 `check,formattable`。结合镜像内实际 `libfs_mgr.so` 的 fsck/format 代码线索，不能安全排除进入 Recovery 前已发生自动 fsck 修复，或满足特定状态时自动格式化的可能。**原版 C13 不应直接重试。**
- 已主机侧构建 Candidate 13.1：只从正常启动的 first-stage 与 runtime fstab 中移除上述两个分区的 `check`、`formattable`，保留文件系统类型、挂载阶段、元数据加密参数、Keymaster/Gatekeeper SELinux 规则、内核及正常启动参数。它不承诺整套系统只读；挂载、F2FS 日志/检查点、vold 密钥与元数据操作仍可能写入分区。
- C13.1 改动会有意改变部分 fsck/format 触发资格与 Recovery 回退行为，因此不是“原版 C13 的完全等价重现”；它移除了 fstab 上显式的 `check,formattable` 标记，但不能排除 fs_mgr 因文件系统状态触发检查/修复，也不能保证数据分区不被普通挂载、日志回放或 vold/init 操作写入。其实际设备效果尚未验证。
- 现有 pstore/WarmDtb 及主机观察器能提高首次故障留存概率，但不能保证无 ADB 时拿到所有 Init/vold 用户空间日志。观察器已补上 Recovery ADB 状态的 pstore 尝试与 wipe 停止提示。
- PixelOS A0′ 最近一次只读验证为健康在线：thyme、A 槽、`sys.boot_completed=1`、Android 17/SDK 37、预期内核、vold running，已加密 `/data` 为可写 F2FS；Fastboot 列表为空。无恢复监听/fastboot 写入进程被当前主机进程检查命中。

## 一、C13 实际存储启动路径

实际 C13 的 vendor fstab（文件 SHA-256 `6ab9ef81d3d9218ae89b6f4ca08d23086f6ef034ba4c29464553849e5a2a5d93`）有：

- `/metadata`：ext4，含 `wait,check,fsverity,formattable,wrappedkey,first_stage_mount,metadata_csum`。
- `/data`：F2FS，含 `latemount,wait,check,fsverity,formattable`，并配置 `fileencryption=...wrappedkey_v0`、`metadata_encryption=aes-256-xts:wrappedkey_v0`、`keydirectory=/metadata/vold/metadata_encryption` 等选项。

实际 `vendor/etc/init/hw/init.target.rc` 在正常启动 `fs` 阶段调用 `mount_all /vendor/etc/fstab.qcom --early`，在 `late-fs` 调用 `mount_all ... --late`；vold 在 early-fs 启动。`/metadata` 标记 first-stage mount，`/data` 标记 late mount。system Init 的正常事件继续经过 early-fs/fs/late-fs/post-fs-data。Recovery fstab 是独立输入，不在本次数据保护补丁中修改。

从 C13 镜像提取的实际二进制：

- `system/lib64/libfs_mgr.so` SHA-256 `eb3f772f940c5eddf22e14f85b1ae68dbd36ecc668011e4709d2e9377af9d877`。从 pinned C13 `system_a` EROFS 重新提取并复核 SHA-256；ELF 为 AArch64 Android 37，动态符号表保留 `fs_mgr_mount_all`（0x317b0）、`WasMetadataEncryptionInterrupted`（0x31584）和 `fs_mgr_do_format`（0x43f84）。实际库还含 C13 特有错误字符串“Failure while mounting metadata, setting flag to needing recovery partition …”。这些证据确认对应实现/错误文案存在，并强烈指向 `/metadata` 挂载失败可请求 Recovery；但本轮控制流反汇编未闭合该字符串分支的准确调用条件，也未确认 `fs_mgr_mount_all` 到格式化函数的完整可达调用链。errno、分区状态门槛及 Xiaomi 对应 AOSP 的偏差仍未知。静态提取/反汇编中间证据保存在 WSL `[LOCAL_WSL_USER]/c13_audit/fs_mgr_probe_20260925_2329/`。
- `system/bin/vold` SHA-256 `f93d8d75894dacf39842fd349c7c271f18794dec0a3a450d56b39464b89273e4`。含 `encryptFstab`、`mke2fs`、`make_f2fs` 等格式化能力字符串。这证明格式化能力存在于镜像，不单独证明这次启动调用了它。

## 二、数据风险与证据等级

### 已在 C13 文件中确认

1. `/metadata`、`/data` 两条正常启动 fstab 确实都带 `check,formattable`；`/data` 还使用 wrapped-key metadata encryption。
2. C13 的 Recovery 日志出现 `--prompt_and_wipe_data --reason=fs_mgr_mount_all`，之后 Recovery 写入 `boot-recovery recovery`。这证明 Recovery 用户空间取得了 fs_mgr mount-all 恢复请求并写入后续 BCB；**不证明启动前已有相同 BCB，也不证明此前没有发生过 fsck/format。**
3. 本次保存的 C13 pstore 只有一个可见 Recovery 内核/Init 实例，未保存前序普通 Android 的第一条失败日志。
4. PixelOS 随后正常解密并以可写 F2FS 挂载 `/data`，因此没有证据表明发生了完整清除；这不能排除此前做过 fsck 修复、元数据写入或局部修改。

### 通用 Android 17 实现参考（不是小米 C13 分支的逐行源码证明）

Android 17 上游 `fs_mgr` 在 fstab `check`/文件系统状态满足条件时会调用文件系统检查器；ext4 路径可能执行 `e2fsck -p`，必要时执行 `e2fsck -f -y`，F2FS 路径运行 `fsck.f2fs`。这些检查可能修复文件系统，发生在是否显示 Recovery wipe 确认之前。[Android 17 fs_mgr.cpp：check_fs](https://android.googlesource.com/platform/system/fs/fs_mgr/%2B/refs/heads/android17-release/fs_mgr.cpp)

上游 `fs_mgr_mount_all` 的格式化条件是挂载错误不属于 EBUSY/EACCES、条目是 `formattable`，且分区被判定为 wiped 或 metadata encryption interrupted。对带 metadata encryption 的 `/data`，路径可请求 `vdc cryptfs encryptFstab ... shouldFormat=true`；失败后还可回退 `fs_mgr_do_format`。这属于启动时主机代码自动操作，不会先等待 Recovery UI 确认；若格式化失败，上游设置 NEEDS_RECOVERY。普通 `mountFstab` 失败则累计一般 mount error，最终可返回 `FS_MGR_MNTALL_FAIL`，它本身不同于 NEEDS_RECOVERY。[Android 17 fs_mgr.cpp：mount/format 返回路径](https://android.googlesource.com/platform/system/fs/fs_mgr/%2B/refs/heads/android17-release/fs_mgr.cpp)；vold 对 `should_format` 的格式化分支可参见 [AOSP MetadataCrypt.cpp](https://android.googlesource.com/platform/system/vold/%2B/refs/heads/master/MetadataCrypt.cpp)。

Android Init 将 NEEDS_RECOVERY 映射到进入 Recovery 的代码路径。AOSP 当前相关实现使用 `--wipe_data --reason=fs_mgr_mount_all`；小米 C13 实际 Init/Recovery 记录则使用 `--prompt_and_wipe_data`，属于本机实际观测，不能用上游参数替换。[AOSP init builtins.cpp](https://android.googlesource.com/platform/system/core/%2B/d12c75f531d1d37d54fdad8007925e031b772117/init/builtins.cpp)

### 仍未知

- 无法证明 C13 本次确实执行了 fsck 或任何 format；启动前是否满足 `partition_wiped`、`encryption_interrupted` 条件也未知。
- Keymaster/Gatekeeper/QSEECom 失败可能令 wrapped-key metadata-encryption 的 vold 调用失败，但**单独**的普通 `mountFstab` 失败在上游通常是一般 mount 错误，不足以断言它必然请求 Recovery或格式化。若同时满足 wiped/interrupted 条件，`formattable` 分支的风险不同。
- `androidboot.init_fatal_reboot_target=recovery` 在 C13 vendor_boot 命令行中存在；PID 1 fatal 可能是另一路由，但没有日志证明它发生。`--reason=fs_mgr_mount_all` 更直接支持 Init 的 mount-all Recovery 分支。
- `--prompt_and_wipe_data` 只定位到 Recovery 的确认式清数据流程，不能区分 `/metadata` 专用失败、格式化失败或其他触发 NEEDS_RECOVERY 的分支。C13 专用 `/metadata` 错误字符串使 metadata 挂载失败成为最有依据的细化假说，仍不是最终根因。

## 三、Candidate 13.1 数据保护变体

改动范围仅为以下两份正常启动 fstab 的 `/metadata`、`/data` 条目：

1. `vendor_boot` first-stage CPIO：`first_stage_ramdisk/system/etc/fstab.qcom`。
2. `super` 内 `vendor_a:/etc/fstab.qcom` runtime 副本。

只删除 `check`、`formattable`；保留 5,213 字节 runtime fstab 原长度及 ext4 文件块映射，first-stage CPIO 头、所有文件元数据/xattr及其他 payload 保持不变。CPIO 684 个条目中只有 first-stage fstab payload 改变；Recovery fstab 原样，SHA-256 `6ab9ef81d3d9218ae89b6f4ca08d23086f6ef034ba4c29464553849e5a2a5d93`。`/data` 的加密和 Keymaster/vold 调用路径没有被删除。

由于 `vendor_boot` 和 `vendor_a` payload 变化，已重建对应 AVB 描述符、vendor hashtree、LP `super.img` 及顶层 `vbmeta.img`。`boot.img`、`dtbo.img`、`vbmeta_system.img`、C13 `system_ext_a`（包含两条 ion_device allow 规则）保持原哈希；内核、SELinux enforcing、vendor cmdline、DTB、Recovery fstab 和 BCB 未改。

**诊断收益：**上述 fstab 不再通过显式 `check` 标志要求检查，也不再通过 `formattable` 进入标准自动格式化资格；仍能观察挂载、wrapped-key metadata encryption、Keymaster/Gatekeeper/QSEECom 和 vold 失败。Android 17 fs_mgr 仍可能因文件系统报告 unclean/其他状态而触发检查，因此这不是“禁用所有 fsck”的证明。

**有效性代价与剩余风险：**Android 17 first-stage 实现会把带 `formattable` 的失败挂载视作可忽略；移除 `/metadata` 的该标志可能使 first-stage mount 失败变成致命错误，不再走原本的 second-stage mount-all 分支。该行为来自 AOSP 参考实现，小米 C13 Init 的该分支尚未逐条反汇编确认。[AOSP first_stage_mount.cpp](https://android.googlesource.com/platform/system/core/%2B/6ad4d0a601485475645ddd1b23181a4c31754977/init/first_stage_mount.cpp)。此外移除 `check` 不能证明 fs_mgr 不会因 unclean 文件系统状态自动检查/修复；普通可写挂载、F2FS journal/checkpoint replay、vold/init 密钥与元数据读写也仍可能发生。它不是块级写保护。**因此，当前 C13.1 虽降低了自动格式化风险，但尚未达到可确认不会在首次失败前自动修复 userdata/metadata 的门槛。**

C13.1 镜像构建和静态核验路径：`work/stage_c_thyme_os4_candidate_13_1_data_guard/images_c13_1_attempt_04/`。构建报告：`work/stage_c_thyme_os4_candidate_13_1_data_guard/C13_1_DATA_GUARD_BUILD.txt`。预检/刷写脚本 `tools/flash_candidate13_1_data_guard.ps1` 默认 Dry-Run，本轮 Dry-Run 已对六镜像大小/SHA-256全部通过；未运行 `-Execute`，也未查询设备。

| 分区 | 镜像大小（字节） | SHA-256 |
|---|---:|---|
| `vbmeta_a` | 131,072 | `5AD1D85C2483851178FED42FB3D28BAA722466AECBDBCF947DFAD47EE01C665E` |
| `vbmeta_system_a` | 131,072 | `BF4155CD99F125B8CAD26490FD2F3412EA4389F090CE56F36FAA2BF2A759C633` |
| `boot_a` | 201,326,592 | `E5A016056D5C93C7A886980A7C062617EC44DC06A48417D7DD0F4476708A6368` |
| `vendor_boot_a` | 100,663,296 | `7A8956F056780395F6374B8C951B080A8A3DBD9987F81F35FC162CAE0F41382C` |
| `dtbo_a` | 33,554,432 | `50E1AC0EDCBD333778217AA6FE8D972F6FF85ADD0DAE8A015A6642C2172DD886` |
| `super` | 7,672,429,336 | `1DB96048CC35663CAE404C471C3DB1055AC2F4D97664ADAA8630B30F347347ED` |

写入顺序是上述顺序，`super` 最后；脚本只列出这六项，不含 reboot、lock、erase、format 或 userdata/metadata 写入目标。`vendor_a.img` 与 `system_ext_c13.img` 是本地验证/中间文件，`vendor_a` 已装入 `super.img`，均不是额外刷写目标。

## 四、首次故障取证方案与限制

A5 内核配置含 `PSTORE`、`PSTORE_CONSOLE`、`PSTORE_PMSG`、`PSTORE_RAM`，启动参数配置约 4 MiB ramoops 保留区；WarmDtb 带 `qcom,force-warm-reboot`。这能争取跨温复位保留 console/pmsg，不是磁盘日志分区，也不保证所有掉电/复位类型都保留完整首启日志；ramoops 区容量有限，后续 Recovery/Standalone 内核运行也可能让旧现场被覆盖或只剩部分记录。[Linux ramoops 文档](https://docs.kernel.org/admin-guide/ramoops.html)

现有 C13 salvage 保存的是 Recovery 的 `console-ramoops-0`，未保存普通 Android 第一轮 kernel/Init/fsmgr/vold 的完整失败现场。主机 USB/Fastboot 时间线只能证明设备何时枚举/消失或回到 Fastboot，不能代替 pre-ADB kernel console。现有 Standalone 预构建镜像可在下一轮 ADB 取证后协助导出 pstore/pmsg/oops；它本身要再启动一个 RAM 内核，因此不得抢在 Recovery ADB/pstore 读取之前运行，也不保证能够恢复已覆盖的第一轮记录。当前 `tools/build_standalone_diag.py` 是 misc 采集分支，不应假定它等同于旧预构建镜像的 pstore 导出功能。

`tools/observe_candidate13_readonly.py` 本轮改为：

- 继续每秒记录 ADB/Fastboot 发现状态，ADB 可访问时启动全 buffer monotonic logcat，并保存属性、cmdline、kernel version、dmesg、SELinux/ION、关键服务及 `/data`/`/metadata` 挂载快照。
- 在 ADB `device` **或** `recovery` 可用时立即尝试只读枚举/复制 `/sys/fs/pstore` 并在主机侧生成 SHA-256；若状态明确变为 `recovery` 或 `sideload`，提示不要触碰任何 wipe 确认。sideload 没有 shell 时只记录状态。
- 不发 ADB/Fastboot 写入、启动或重启命令。语法和调用路径只做静态检查，未在设备上运行。

**仍无法保证：**若普通 Android 在 ADB 启用前即失败/转 Recovery，且 Recovery ADB 不可用，现有主机接口拿不到完整第一轮 Init/vold 日志。此时信息收益最高的做法是先保持 Recovery 屏幕与 USB，不确认 wipe；先尝试 observer 的 Recovery ADB/pstore 读取；只有取得单独 RAM 启动授权后，再启动固定哈希核验的 Standalone 并尽早导出保留区。不要先运行自动 PixelOS 恢复程序。

## 五、下一次实验决策与阻塞

**当前决策：暂不申请 C13.1 刷写授权，暂不把现有 C13.1 产物标为可上机。**原版 C13 的自动格式化资格已从普通 fstab 去除，但 fs_mgr 因 unclean 状态触发的自动 fsck/修复未排除；移除 first-stage `formattable` 还可能把 `/metadata` 失败提前变成 first-stage fatal。这与“先确保没有无需确认的数据修改”要求仍有差距。

解除阻塞的主机侧路线：对 C13 实际 `libfs_mgr.so` 的 `prepare_fs_for_mount/check_fs` 与 `fs_mgr_mount_all` 路径做最小针对性验证，确定如何仅对 `/data`、`/metadata` 屏蔽自动修复/格式化，同时保留真实 mount、metadata-encryption、Keymaster/vold 失败返回与日志；若需要改库，形成单独的 Candidate 13.x，逐项核验 AVB、first-stage / second-stage 路径和故障语义。若无法做到足够窄，则需要在实验前建立可验证的 userdata/metadata 原始备份或接受其完整性风险；这两项均不在本轮授权范围内。当前报告不申请刷写。

解除阻塞后，实验顺序应为：

1. 只读确认 PixelOS A0′ 健康、设备身份/A 槽/Bootloader `unlocked=yes`，且无活动 Fastboot 写入/自动恢复监听。
2. 获得单独授权后，刷写最终通过数据保护核验的六镜像，串行写入、`super` 不打断，完成后保持 Fastboot。
3. 先启动只读 observer；首次正常启动另行授权，用户在视线内观察。
4. 若 Recovery 出现，不确认清数据、不自动重试、不切换模式、不启动恢复流水线；先尝试 Recovery ADB/logcat/pstore。需要 Standalone 时另取 RAM 启动授权，优先于 PixelOS 恢复导出现场。
5. 分开验收：策略加载、ION AVC、QSEECom、Keymaster/Gatekeeper、vold metadata-encryption 与 `/data` 解密挂载是不同结论。

未来仍需分别授权：最终变体六分区写入、首次启动；若失败则单独授权 Standalone `fastboot boot` RAM 取证；取证后如需恢复，再单独授权 PixelOS 六分区恢复及其正常启动。无授权包含 userdata/metadata 擦除、misc/BCB 写入、无线电/身份区改动或 Bootloader 锁定操作。
## 验证边界

- 已完成：从 pinned C13 `system_a` 重新提取实际 `libfs_mgr.so`，SHA-256 与既有哈希相同；`readelf`/`nm` 确认实际导出的 fs_mgr 函数符号，并对 `fs_mgr_mount_all`、`fs_mgr_do_format` 做有限反汇编。函数存在，但完整格式化调用链及 `/metadata` 特定错误分支条件未闭合；证据与限制见第二节。
- 已完成：host-only Candidate 13.1 构建；runtime fstab 读回；`e2fsck -fn` 对补丁后的 vendor ext4 镜像检查无错误；first-stage CPIO 解压/重压往返；CPIO 只有目标 fstab payload 改变；Recovery fstab 未变；vendor_boot header/DTB/cmdline 核对；AVB vendor/vendor_boot 描述符对应核对；lpmake sparse super 与 LP 表核对；从新 super 重新提取 vendor_a、system_ext_a，哈希分别与构建输入相同；Dry-Run 六镜像核验；Python/PowerShell 静态语法检查。
- 尚未验证：C13.1 真机刷写、首次启动、SELinux 动态编译加载、ION AVC、Keymaster/Gatekeeper/QSEECom、vold metadata-encryption 与 userdata 启动表现；修改后故障是否和 C13 完全相同。
- 本轮没有清除或重刷 PixelOS，没有重新刷入 C13，没有任何设备写操作。

