# THYME-OS4 Candidate 24 首次实机取证报告

日期：2026-09-28（香港时间）

## 结论

C24 在唯一一次受控启动后运行了约 16 分 43 秒，用户始终看到第一屏：中央小米 Logo，下方 `powered by Android`；没有看到第二屏的 `Xiaomi HyperOS` Logo 和三个进度点。随后用户手动进入 Fastboot。ADB 未上线，未出现 Recovery。

pmsg 证明 Android 的 BootAnimation 代码路径曾运行，并记录 `BootAnimationShownTiming start time: 41015ms`。这不证明 HyperOS 动画层已显示，也不证明 SurfaceFlinger/HWC 成功向物理面板 present。C24 采样脚本的 `C24BootDiag` 标记在完整 pmsg 和 console 中均为 0；因此采样服务是否启动、是否成功写入 logd、是否被 pmsg 保留都不能区分。不能由此断言 system_server、WMS 或 SystemUI 不存在。

本轮没有得到 Framework/UI 或物理显示链的最终断点；不构建图形修复 Candidate。下一步应先让诊断服务的启动和输出通道可验证，再定点检查本轮重复出现的 SurfaceFlinger→`IMiHwcExtension` 查找拒绝。

## 实验记录

| 项目 | 实际结果 |
|---|---|
| 启动前设备 | 唯一设备 `1384e684`，`product=thyme`，A 槽，Bootloader 解锁，非 userspace Fastboot |
| A/B 启动状态（启动前） | A：unbootable=no、successful=no、retry=4；B：no、no、retry=7 |
| 观察器 | `C24-framework-display-diag`；启动前已 ARMED。第一观察器保持运行，第二观察器覆盖启动后 1400 秒 |
| 启动命令 | 2026-09-28 19:49:44.233 HKT，唯一一次 `fastboot -s 1384e684 reboot`，返回 `OKAY` |
| 用户画面 | 20:01:58 报告第一屏静止、无进度点、显示 `powered by Android`；20:04:25 澄清第二屏才是 HyperOS Logo+三点，本轮未见第二屏 |
| 返回 Fastboot | 主机于 20:06:26.904 HKT 再次识别 Bootloader；用户确认是手动切入，约为启动后 16 分 43 秒 |
| ADB | 全程未上线；观察器 `logcat_all_monotonic.txt` 为 0 字节 |
| 启动后 A/B | A：unbootable=no、successful=no、retry=3；B：no、no、retry=7 |
| 当前设备 | 最近只读 Fastboot 查询（20:09:54 HKT）：thyme、A、unlocked=yes、is-userspace=no；A retry=3。没有执行 set_active |

设备仍是 C24 实验状态；本轮没有恢复 PixelOS、刷写、清 userdata/metadata、改 BCB 或修改其他分区。

## Standalone 全量取证

2026-09-28 20:07:22 HKT 使用已核验的 Standalone 镜像 RAM 临时启动。动态识别 `THYME_DIAG`，完整复制所有可访问文件与目录至独立目录。8 个源文件均完成大小与 SHA-256 比对，0 个复制错误，总计 20,977,071 字节。原件未修改。

本地取证目录：

`work/reports/20260928_C24_FRAMEWORK_DISPLAY_DIAG/standalone/run_20260928_200722/`

完整清单：`FILE_MANIFEST.csv`、`SHA256SUMS.txt`。核心文件如下：

| 文件 | 大小 | SHA-256 |
|---|---:|---|
| `THYME_DIAG/pstore/console-ramoops-0` | 2,097,140 | `FC58483EA9B964C44387B945FF20C25DCCCBF6188BBEA1EED453BE230EAD8C52` |
| `THYME_DIAG/pstore/pmsg-ramoops-0` | 1,944,347 | `4FAB54A0C983CB53CA872FBD3D1697EE8A71145619076B4C435F83296046EE1C` |
| `THYME_DIAG/oops.raw` | 16,777,216 | `7D1E254BBEB4803D79FDF96F673EF4DC9C7D0EAE68DF3019C2384B3439E4BB66` |
| `THYME_DIAG/dmesg_diag_boot.txt` | 155,035 | `1272129524267EFFCE502F888469DDB51C7F34F0C122D677B3C75C369C87EEDE` |
| `THYME_DIAG/diag_status.log` | 3,159 | `07FF59A412D98ED844D2C735DC65FF1E6FB1DABE2EFDE76D22FA0C91B9A44842` |

`oops.raw` 的 SHA-256 与 C13–C23 多轮历史副本一致，属于旧记录，不归属 C24。`dmesg_diag_boot.txt` 的时间/内核属于 Standalone 自身，不是 C24。Standalone 状态文件确认本轮只复制到两条 pstore 记录（console、pmsg），并以只读方式读取旧 oops 区域。

console 仅覆盖 kernel uptime 412.175396–992.841320 秒（约 580.7 秒）；未发现 kernel panic/Oops 标志，也没有 `C24BootDiag`。这不是首次启动全程 console。pmsg 时间戳覆盖约 03:50:55.219–04:07:22.453（设备时钟），约 16 分 27 秒。

## Framework、BootAnimation 与显示判定

| 问题 | C24 可确认结果 |
|---|---|
| `C24BootDiag` 服务是否真实运行 | 未确认。最终 pmsg 和 console 均无服务启动/采样标记；无法区分 init 未启动服务、服务/`log` 调用失败、或诊断输出未持久化 |
| 可验证采样轮数 | 0 轮持久采样；这不等于证明脚本执行次数为 0 |
| system_server 是否稳定、最后阶段 | 未知。pmsg 中两条 `system_server artifacts on /system OK` 来自 odrefresh，不是 system_server 进程存活证据 |
| WMS 是否 enable screen | 未知；无 C24 dumpsys 样本或 WMS 阶段记录 |
| SystemUI / SetupWizard / HOME | 未知；没有直接的启动、存活或失败状态样本 |
| BootAnimation | pmsg 有 BootAnimation tag 和 `BootAnimationShownTiming ... 41015ms`；只能证明相关代码路径运行，不能证明 layer 已呈现 |
| `service.bootanim.exit` | 未采到属性值，不能判定为 0 或 1 |
| `sys.boot_completed` | 没有实际属性值。唯一匹配文本是 keystore2 的 `monitoring for sys.boot_completed=1`，这是等待说明，不是属性已置 1 |
| BootAnimation layer / HWC present / 物理 display | 未知；无有效层列表、present/fence 或面板更新证据 |
| 屏幕分类 | 用户明确报告仍为第一屏 splash（小米 Logo + `powered by Android`）；未看到 C23/C24 product 中 HyperOS Logo+三点的第二屏。BootAnimation 代码运行与屏幕仍停在第一屏可以同时成立 |

pmsg 中本轮没有再出现 C19 以来的 EGLConfig fatal、Vulkan RenderEngine 初始化 fatal、`output buffer not gpu writeable` 或 graphics allocator `ion_device` AVC。该结果与此前 C23 观测一致，不代表 Framework 已完成启动。

发现一个与显示服务相关但非 C24 新引入的 AVC：SurfaceFlinger 对 `vendor.xiaomi.hardware.display.mihwcextension.IMiHwcExtension/default` 的 service-manager `{ find }` 被拒绝一次，目标类型为 `default_android_service`、`permissive=0`。C23 pmsg 有同一条拒绝；缓存的 K40/C23 service-context 文件中未找到该服务的精确条目。它可能导致 Xiaomi HWC 扩展不可查询，但没有日志证明它阻止了必需的物理 display present。SurfaceFlinger 查询 `vendor.qti.hardware.perf2.IPerf/default` 也有重复 `{ find }` 拒绝；这些错误同样需与致命显示故障区分。

因此，当前不能回答 system_server/WMS/SystemUI 是否启动，不能确认 BootAnimation 是否退出，也不能确认物理 present。用户看到的第一屏与第二屏资源差异说明本轮未获得可见启动动画进展，但不能单独定位是 Framework 停住还是 HWC 没有提交新帧。

## 下一步决策

1. 不再重复相同 C24 启动，不切换图形属性，不清数据，不恢复 PixelOS。
2. 暂不构建图形修复版 C25。下一版若必要，应先只修复诊断可观测性：必须有可从 pstore/Standalone 回读的明确 init 服务启动、首样本、持续采样及结束标志。当前运行的是 `ro.build.type=user` 路线，不能未经核验就套用只在 userdebug/eng 启用的 `stdio_to_kmsg` 选项。[Android 17 init README](https://android.googlesource.com/platform/system/core/%2B/android17-release/init/README.md) 对该限制有说明。
3. 只读定点核实 `IMiHwcExtension` 的注册进程、service_contexts 类型、实际客户端调用及 K40 是否具有同一接口；在服务类型和必需性得到证据前，不新增宽泛 SELinux allow。
4. 下一次正常启动前仍需用户现场确认；任何 Candidate 刷写或数据操作按现有授权边界执行。

## 证据路径

- 主机启动前观察：`observations/run_20260928_192502/`
- 主机启动后观察：`observations_postboot/run_20260928_195017/`
- Standalone 全量副本：`standalone/run_20260928_200722/`
- 设备启动前后 Fastboot 原始输出、导出源信息、文件 manifest 和 SHA-256 均保存在上述目录。
