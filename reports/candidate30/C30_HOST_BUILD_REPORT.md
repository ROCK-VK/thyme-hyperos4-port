# C29 零字节诊断写入审计与 C30 构建报告

## C29 metadata/ext4 与 SELinux 核验

C29 的 events、logcat status 文件 inode 均为 0 字节/0 block，实际 SELinux xattr 是 `u:object_r:c25_diag_data_file:s0`；父目录同为该 type。文件 UID/GID 为 2000:2000、mode 0660；目录 UID/GID 为 0:2000、mode 0770。C29 最终 `plat_file_contexts` 和 shell→c25 type transition 一致。实际 C29 `plat_sepolicy.cil` 对 shell 授予文件 create/open/read/write/append/getattr/setattr 与目录 search/open/read/write/add_name/getattr；C29 platform CIL 用 secilc policy version 35、neverallow enabled 验证通过。未发现应再扩大 shell 权限的证据。

同一恢复出的 metadata 中 C26 events/logcat 是非空且具有相同 c25 label，说明 shell 域对该目录/类型曾成功持久写入并同步。C29 inode 空值更符合首个 payload write 未成功、fdatasync 未成功，或 helper 在 open 后、payload 写入前退出这一组可能性；当前 inode与C29源码不能区分这些路径。没有 errno、直接 AVC 或对应 C29 pstore，因此根因仍未闭环。

## Unified First-Response Standalone

新 Standalone 在创建基本 proc/sysfs/tmpfs 和必要字符设备后，先只读挂载并复制 `/sys/fs/pstore`，随后按唯一 PARTNAME 与 major/minor/块设备/容量核验 raw metadata 并比对 source/copy SHA，再按原规则只读导出 misc。最后单独保存 `standalone_dmesg.txt`，生成 FILE_MANIFEST/SHA256SUMS，才建立 RAM FAT32 UMS。它不会 replay metadata journal，也不会对持久分区写入。主机 `salvage_c13_diag.py` 负责全卷完整复制与逐文件校验。此处为静态/构建验证，尚未 RAM 启动验证。

## C30 改动与验证

C30 使用专用 `c30_diag` 域和 `c30_diag_exec` 入口转换。helper 启动后先做独立 write、write+fdatasync、create+sync+append+sync 三个 canary；结果发到 Android log。init built-in 独立写 helper running/stopped markers。只有 canary 全部通过后才创建 ordered events/logcat；事件使用 CLOCK_BOOTTIME、boot_id、helper PID、服务属性和 system_server 首 PID，逐条 O_APPEND+fdatasync。logcat 只采 crash/system/main/events、不轮转、最多 60 秒/8 MiB。

C30 平台 CIL 的 secilc/neverallow、目标权限查询、AArch64 PIE ELF、最终 EROFS readback、fsck、AVB system/vbmeta_system 描述符和 LP 布局验证结果记录在 BUILD_MANIFEST.json。此为主机侧构建/静态验证；没有刷写或启动 C30，canary、真实 service 事件、PID 顺序、system_server 及 critical escalation 尚未实机验证。

构建时磁盘门禁：`{'C_free_gib': 75.02, 'D_free_gib': 201.63, 'E_free_gib': 239.08}`。C29 非系统 LP 输入与 C30 对照一致。

| 镜像 | 字节 | SHA-256 |
|---|---:|---|
| `boot.img` | 201326592 | `E5A016056D5C93C7A886980A7C062617EC44DC06A48417D7DD0F4476708A6368` |
| `vendor_boot.img` | 100663296 | `02333B82BA936F1BAAB1ECAB744632C70F8FC16688A206C7041EF319F112A137` |
| `dtbo.img` | 33554432 | `50E1AC0EDCBD333778217AA6FE8D972F6FF85ADD0DAE8A015A6642C2172DD886` |
| `vbmeta.img` | 131072 | `66A53C2EC38247193CC86B7F5DE887556864413D1142C3C1994645DE1E3BAB10` |
| `vbmeta_system.img` | 131072 | `D116F268C015382D5B7F0162959563530D1CFAFC368ED7C1D5DF0514743E5C75` |
| `super.img` | 7703591896 | `071A86171450B5832E2951E63145D0B5AB55AB622BDDEFB249781B819B1CC83C` |

C30 仅为诊断 Candidate；当前未刷写。
