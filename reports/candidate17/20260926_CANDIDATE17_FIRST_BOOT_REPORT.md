# THYME-OS4 Candidate 17 首次启动故障现场取证结果

日期：2026-09-26（Asia/Hong_Kong）

## 结论

用户报告：最新刷入的 Candidate 17 首次启动时小米 Logo 持续亮屏，随后由用户手动进入 Fastboot。该屏幕观察没有主机侧启动观察器或命令时间线佐证，因此候选归属依据是“C17 为最后一次持久分区写入”及用户随后报告；不把时间、循环次数或屏幕状态扩展成未记录事实。

故障后按既有授权使用 Standalone Diag RAM 临时启动，并只读导出 `THYME_DIAG`。导出路径：`work/reports/20260926_CANDIDATE17_FIRST_BOOT/standalone/run_20260926_194616/`。该流程没有写入任何持久分区，没有擦除、重启 Candidate 或执行 PixelOS 恢复。

## 导出完整性

- Standalone 镜像：201,326,592 字节，SHA-256 `8A5803F09CBCB11056D8356F8D235C3C4450846244FA1B4033ABAAACB213E98B`。
- 唯一 `THYME_DIAG` 卷被动态识别；目录及可访问文件共 7 个，源与副本大小及 SHA-256 逐项相同，零复制错误。
- 清单：`FILE_MANIFEST.csv`、`SHA256SUMS.txt`；Standalone 自身状态：`THYME_DIAG/diag_status.log`。
- `dmesg_diag_boot.txt` 是 Standalone 诊断内核日志，不能归属为 C17 Android 启动日志。

## C17 可见的启动证据

- `pstore/console-ramoops-0`：165,019 字节，SHA-256 `93E00AB86DC9910A6CEF490BAE367BBAD5D7715D6F4FAA6DE5B89BC0A414AE8D`。
- 内容包含一个 Linux kernel 启动记录，内核为 thyme 使用的 4.19.325-perf。命令行含 `androidboot.force_normal_boot=1`、`androidboot.slot_suffix=_a`；这与正常 A 槽启动相符。
- 该记录从 uptime 0.000 秒开始，最后可见内核输出约 168.466 秒。文件内未发现 `init first stage started`、Second Stage、SELinux AVC、SurfaceFlinger/EGL、zygote、bootanimation、panic 或 reboot 记录。
- `pstore-ramoops` 本轮只导出 console 文件；没有 `pmsg-ramoops`。因此不能判断 init/用户空间的真实错误，也不能验证 C17 新增的 allocator `open` 权限、EGLConfig、ANGLE/Vulkan 或启动服务状态。
- `oops.raw` 为 16,777,216 字节，SHA-256 `7D1E254BBEB4803D79FDF96F673EF4DC9C7D0EAE68DF3019C2384B3439E4BB66`；该哈希与 C14、C15、C16 导出的原始文件一致，属于重复旧内容，不能作为 C17 新崩溃证据。

## 工程判断

当前唯一可信的新现场是：C17 归属下可见的 kernel console 没有 first-stage init 标记，日志止于约 168.466 秒；pmsg 缺失，且没有 C17 预启动观察记录。若该 console 确属用户所述启动，它提示 Android init 尚未在保存的 console 中出现，但现有证据不足以确认发生了哪个故障，也不足以将其归因于 SELinux 规则。C17 的图形权限效果仍未实机验收。

不据此继续改 SELinux、EGL、ANGLE、HAL 或 super；不构建 C18。下一步保持当前已刷入的 C17，待设备可见且用户在场后，先启动带 C17 标签的只读观察器，再进行一次受控观察启动。观察器若取得 ADB，应立即保留 logcat/属性/服务/内核与可读 pstore；若 ADB 不上线且用户返回 Fastboot，再按既有授权导出 Standalone 诊断卷。启动前不擦 userdata/metadata，不刷写镜像。用户需要再次确认准备观察后才发起启动。

## 设备状态

RAM 诊断导出后，主机未枚举 ADB、Fastboot 或 `THYME_DIAG` 卷；设备离开 Fastboot 的 RAM 诊断引导后的物理模式未由主机确认。没有后续设备操作。最后已知持久分区写入仍为 C17 的 `vbmeta_system_a` 与 `super`；本轮未改变其他分区。
