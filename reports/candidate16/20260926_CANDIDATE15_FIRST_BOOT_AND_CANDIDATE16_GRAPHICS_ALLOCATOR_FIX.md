# THYME-OS4 Candidate 15 首启结果与 Candidate 16 图形权限修复

日期：2026-09-26（Asia/Hong_Kong）

## 结论

Candidate 15 没有进入启动动画、设置向导或桌面，屏幕一直停留在小米 Logo。用户手动将设备带回 Bootloader Fastboot。C15 的 ramoops/pmsg 证明 Android 正常 first stage、second stage、enforcing SELinux、APEX Bootstrap 和 `/data` 挂载均已发生；因此本轮不是 First Stage、Recovery、APEX 或 userdata 初始化故障。

C15 在保留 `persist.graphics.egl=angle` 的系统配置下仍反复记录 SurfaceFlinger `no suitable EGLConfig found`。日志没有证明系统是否实际选择了 ANGLE。另一个在 C14、C15 均出现的具体 SELinux AVC 显示 `hal_graphics_allocator_default` 对 `ion_device` 仅缺少 `{ read }`。这是可直接修正的权限拒绝，但它在 C15 首次 EGLConfig abort 之后出现，尚不能认定它是 EGLConfig 故障的唯一根因。

基于该重复 AVC，已构建 Candidate 16：只向 `system_ext_sepolicy.cil` 加入一条精确 `{ read }` allow，保留 C14 BPF 绕过、C15 ANGLE 配置和 C13 Keymaster/Gatekeeper 规则。C16 仅完成主机侧静态验证，尚未刷写或实机验证。

## C15 启动与取证

主机观察器于 09:37:43 UTC 进入 ARMED；Fastboot reboot 命令于 09:37:57 UTC 发出。USB 时间线记录 Fastboot 消失约 14 秒后，约 180 秒时重新出现；用户报告屏幕持续显示小米 Logo 并手动进入 Fastboot。用户报告时间与实际按键时间并非同一测量点，因此不据此判断设备何时自动或手动切回 Fastboot。

随后通过已准备的 Standalone RAM 诊断链导出了 `THYME_DIAG` 卷现存文件。六项导出源文件与主机副本的 SHA-256 均一致：诊断状态、Standalone 自身 dmesg、oops 原始文件及校验文件、console-ramoops、pmsg-ramoops。Standalone dmesg 只代表诊断内核；`oops.raw` 为可能混有旧现场的 16 MiB 数据，不作为 C15 启动日志。原始取证材料仅保存在本地独立目录：

`work/reports/20260926_CANDIDATE15_FIRST_BOOT/standalone/run_20260926_174212/`

C15 可归属的 console 中有一个 Android kernel 启动实例：

- first-stage init：1.895211 秒；
- second-stage init：3.168030 秒；
- SELinux enforcing：约 3.158 秒；
- APEX Bootstrap 激活 4 个 Bootstrap APEX：3.541 秒；
- 内核 console 记录延伸至约 156.295 秒；
- pmsg 设备时间覆盖约 150.682 秒。

C15 记录没有出现 C13 的 `NetBpfLoad` / `bpfloader-failed`，与 C14 已证实的 BPF 重启绕过继续有效相符。没有 ADB、启动动画、锁屏、设置向导或桌面证据。pmsg 中 keystore2 的“monitoring for sys.boot_completed=1”是等待属性的日志，不能作为属性已变成 1 的证据。

## 存储与数据状态

C15 console 记录 `/dev/block/mapper/userdata` 的 F2FS 挂载成功；pmsg 记录 vold `Mounted /data`、`format:0`，并创建/安装了用户 0 的 DE/CE 密钥。此次无需为复现当前图形问题擦除 `userdata` 或 `metadata`。本轮没有数据擦除或其他持久分区操作。

## 当前实机阻塞证据

pmsg 记录 28 次 SurfaceFlinger 以 `no suitable EGLConfig found` 中止，时间从设备时钟 01:39:13.809 至 01:41:26.362。C15 的 ANGLE 属性与 ANGLE 库存在于镜像，但这些日志没有 ANGLE 加载标记；所以只能确认 C15 系统仍有 EGLConfig 故障，不能断言 ANGLE 已实际接管或证明 ANGLE 本身失败。

C15 console 在 18.483556 秒记录：

`avc: denied { read } ... scontext=u:r:hal_graphics_allocator_default:s0 tcontext=u:object_r:ion_device:s0 tclass=chr_file`

同一轮还记录相机域读取同一节点被拒绝。C14 也有图形分配器和相机的相同读取 AVC。图形分配器权限是可以直接按证据修复的缺口；C16 仅处理图形分配器，不把相机或其他未证明与当前屏幕故障相关的权限一起放宽。

pmsg 也有重复 netd SIGABRT，但没有证据表明它触发了整机复位。本轮不将 netd 加入 C16，避免把非启动关键或未证明相关的问题打包进来。

## Candidate 16 改动与验证

C16 唯一相对 C15 的策略修改为：

```cil
(allow hal_graphics_allocator_default ion_device (chr_file (read)))
```

系统用户空间保留 C14 BPF bypass、C15 `persist.graphics.egl=angle`、C13 Keymaster/Gatekeeper 的 `ion_device` 规则及 thyme 原有硬件底层。新建 `system_ext` EROFS、对应 `vbmeta_system` 描述符和 `super`；不重建或更换 boot、vendor_boot、dtbo、顶层 vbmeta。未清 userdata/metadata。

主机侧验证结果：新 EROFS fsck 和重新读取规则通过；既有 C13 规则及 `/dev/ion` 文件上下文保留；`vbmeta_system` 仍描述 product/system/system_ext，只有 system_ext 摘要变化；LP dump 包含 `product_a`、`system_a`、`system_ext_a`、`vendor_a`；受限刷写脚本通过 PowerShell 解析与默认 Dry-Run。以上是静态/主机验证，不是设备验收。

待刷镜像：

| 分区目标 | 镜像 | 字节数 | SHA-256 |
|---|---|---:|---|
| `vbmeta_system_a` | `vbmeta_system.img` | 131,072 | `24AA0C2971ECA3E2B88F01DBB4E7285834A30AA20498713712DEF8333BC8AAEC` |
| `super` | `super.img` | 7,684,274,964 | `888988A0D9E5307F751B718D573032A14DE4B80A2F47223FB34D5BC8EFEFC6C8` |

本地镜像目录：`work/stage_f_thyme_os4_candidate_16_graphics_allocator_ion_run1/images/`。完整六镜像清单在该目录的 `BUILD_MANIFEST.json`；准备刷写的只有上表两项。脚本 `tools/flash_candidate16_graphics_allocator_ion.ps1` 默认 Dry-Run；实际写入需要显式参数。本报告生成时没有执行 C16 写入或启动。

## 当前设备与下一步

最新只读 Fastboot 查询：`product=thyme`、`current-slot=a`、`unlocked=yes`、`is-userspace=no`；ADB 不在线。没有正在运行的 Fastboot 刷写或项目自动恢复/观察进程。设备由用户手动保持在 Fastboot。

当前持久化状态仍是 C15 `vbmeta_system_a`、`super` 和继承的 C13 引导分区基线；PixelOS A0′ 未在 C15 后恢复或验证在线。Bootloader 保持解锁。未触及 `persist`、`modemst`、EFS/NV、misc/BCB、userdata 或 metadata。

下一实验建议使用 C16，仅刷 `vbmeta_system_a` 与 `super`，保留当前 C15 其余分区，不清数据。若用户授权刷写，写完保持 Fastboot；首次启动仍需单独授权。启动观察重点：该图形分配器 AVC 是否消失、SurfaceFlinger EGLConfig abort 是否变化、屏幕能否进入 HyperOS 启动动画，以及是否出现更后续的实际错误。C16 是否能根治 EGLConfig 仍待实机验证。