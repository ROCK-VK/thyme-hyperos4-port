# M01 Known-Good 首启失败：RAM 现场取证与 M01-R2 决策

- 日期：2026-10-05（HKT）
- 设备：Xiaomi 10S / thyme；设备序列号已省略
- 实验：M01-R1；madrid OS4.0.15 Known-Good → thyme 安全子集
- 结论：故障现场打捞完成；R1 根因未确定

## 结论摘要

M01-R1 刷入的五分区安全子集没有成功启动到 Android framework UI。随后通过既有 Standalone RAM 诊断环境完整复制 THYME_DIAG 卷，归档完整性验证通过。但 pstore 挂载成功后记录数为 0；归档中没有 M01-R1 的 console-ramoops、pmsg-ramoops 或其他 kernel log。

Standalone 自身的 dmesg 显示其运行的是 4.19.325-perf 内核，不能证明 Known-Good 4.19.325-cxk 内核是否开始执行。只读导出的 oops.raw 与 C47 既有归档散列相同，属于旧残留。没有本次 M01 证据能够确认 AVB、kernel、dtbo、vendor_boot/ramdisk、super、firmware 或 userspace 中的任何一项为根因。

当前首选 M01-R2 单变量实验是只补刷 Known-Good top-level vbmeta_a。该项仍是待验证的强假说，不是 R1 根因结论。R2 尚未刷写或启动。

## M01-R1 结果

- 实际写入 vbmeta_system_a、boot_a、vendor_boot_a、dtbo_a、super；五项 fastboot flash 均返回 OKAY。
- 未刷 top-level vbmeta_a 或底层 firmware；未清除 userdata/metadata；未 relock。
- 用户观察到 Mi Logo 与黑屏交替，之后回到 Fastboot；ADB 从未出现。
- A 槽 retry 从 7 降到 0、unbootable 状态变为 yes，之后通过 set_active a 恢复。
- 每轮约 20 秒与早期失败相容，但没有 kernel log，不能定位具体失败阶段。
- R1 是 Known-Good 的安全子集试验，不是社区包原始完整刷机矩阵；R1 失败不否定原成功包完整方案。

## RAM 现场归档与完整性

归档：reports/m01_known_good_runtime/failure_salvage_20261005_142437/

- Standalone 只通过 fastboot boot RAM 启动，没有写入诊断分区。
- THYME_DIAG 完整目录树共 6 个文件、16,937,642 字节。
- 原打捞脚本逐文件核对源/副本大小和 SHA256：6/6 通过，复制错误 0。
- FILE_MANIFEST、SIZE_MANIFEST、SHA256SUMS 已生成；归档后复算通过。
- pstore 挂载成功但记录数为 0。
- dmesg_diag_boot.txt 是 Standalone 自身 4.19.325-perf 内核日志。
- oops.raw 与 C47 Standalone 归档散列相同；此原始分区数据没有公开上传。
- 诊断卷没有 bootloader log 文件。主机观察器仅记录 USB/Fastboot/ADB 状态。

## 证据逐项判断

| 项目 | 当前判断 |
| --- | --- |
| 是否有 M01 kernel banner | 没有。归档中只有 Standalone 自身 banner。 |
| Known-Good kernel 是否开始执行 | 未知，当前没有证据。 |
| 是否进入 init / first-stage init | 未知，无 M01 log。 |
| 是否尝试 mount super | 未知，无 M01 log。 |
| 是否出现 dm / AVB 错误 | 未知，无 M01 log，不能据此确认或排除 AVB。 |
| 是否出现 dtbo/device-tree 错误 | 未知，无 M01 log。 |
| kernel panic / watchdog | 未知，无 M01 log。 |
| SELinux / init failure | 未知，无 M01 log。 |
| vendor_boot / ramdisk mount failure | 未知，无 M01 log。 |
| firmware dependency | 未知，无 M01 log。 |
| 是否存在当前 M01 pstore | 没有；本次 pstore 记录数为 0。 |

C47 的旧 console-ramoops / pmsg-ramoops 仅属于 C47，不能视为 M01 证据。

## M01-R2 单变量预检

| 角色 | 大小 | SHA256 |
| --- | ---: | --- |
| Known-Good top-level vbmeta_a 目标 | 4,096 bytes | D2E1979739EC67076A90B0FC625DAE84A1AA2ED72D05D2B55D52539E3462B442 |
| A 槽 vbmeta 回滚镜像 | 131,072 bytes | 6D46FA9E36D2FFC9BF45F5365691A85AED488622F0254C864EFF3DD42A23FE6D |

目标 vbmeta 静态结构为 Algorithm NONE、Flags 2、无 descriptors。回滚镜像文件已在工作区存在且散列复算一致；设备分区原始内容无法通过 Fastboot 读回，因此不将镜像散列表述为设备 dump。

M01-R2 仅拟写入 Known-Good vbmeta_a。不得重刷 boot、vendor_boot、dtbo、super、vbmeta_system；不刷 firmware，不清 userdata/metadata。刷后恢复并核对 A 槽 retry budget，然后停在 Fastboot。未收到用户明确的“开始启动 M01-R2”前不得启动。

取证后主机不再枚举 Fastboot 或 ADB；需现场返回 Bootloader Fastboot，再刷新只读门禁后才能进行该单分区实验。

## 下一步与安全边界

1. 现场将设备带回 Bootloader Fastboot，复核 product、slot、unlocked、is-userspace、retry、unbootable。
2. 门禁通过后只刷 Known-Good vbmeta_a，并停留 Fastboot。
3. 等待明确启动授权；如 R2 启动后首次出现明显黑屏或自动重启，立即进入 Fastboot 并打捞，只允许一轮失败。
4. 未有证据前不刷 firmware、不擦数据、不 relock、不触碰校准/身份分区。
5. 不上传 ROM、super、boot、raw pstore、专有二进制或含设备标识的原始日志。
