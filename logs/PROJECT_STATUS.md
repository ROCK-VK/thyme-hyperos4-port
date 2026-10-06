# THYME-OS4 项目当前状态

更新时间：2026-10-06（HKT）

## 最终目标

将 Xiaomi 18 Pro Max（`madrid`）HyperOS 4 / Android 17 官方 OS4.0.19.0.XEOCNXM 移植到 Xiaomi 10S（`thyme` / Snapdragon 870 / SM8250-AC）。社区 Known-Good madrid OS4.0.15 → thyme 是已验证的恢复基线。

## 阶段状态

| 阶段 | 当前事实 |
| --- | --- |
| M00 Madrid Intake | 完成；Known-Good donor 确认为 madrid OS4.0.15，目标为官方 madrid OS4.0.19 |
| M01-R1 / R2 | Known-Good 安全子集分别未启动成功；无可归属到当次启动的 pstore，最早失败阶段未知 |
| M01-R3 | clean userdata/metadata 后 Known-Good Android framework 启动成功；ADB 持续在线 900 秒 |
| MADRID-M02 r3 | 首次实机启动成功；ADB `device`、`sys.boot_completed=1`，用户确认设备稳定 |
| M03 Port Provenance Audit | 静态审计完成；报告待用户审阅；设备保持 MADRID-M02 r3 运行 |

## MADRID-M02 r3 当前设备状态

- 设备正在运行 MADRID-M02 r3；不要自动重启、切 Fastboot、进 Standalone、rollback 或刷写。
- 首启前 Fastboot gates 通过，六个部署镜像 SHA256 与冻结 manifest 一致；仅执行过一次正式 `fastboot reboot`。
- ADB 于启动后 T+207.2 秒上线。运行 fingerprint 为 `Xiaomi/thyme/thyme:17/CP2A.260605.016/OS4.0.19.0.XEOCNXM:user/release-keys`；实际 kernel 为 `4.19.325-cxk-lxsclnb-g33d88af64048`，与 Known-Good boot stack 一致。
- `com.android.tethering` APEX 已挂载；netd、INetd 与 Tethering service 可见；netd updatable init 成功；Tethering 报告 BPF enabled，主要 maps 状态为 OK。真实 hotspot/上游转发流量尚未测试。
- 用户确认开机成功且设备稳定，并要求停止 10 分钟观察。停止前约 121 秒的末次只读轮询为 ADB online、Fastboot absent、`sys.boot_completed=1`；没有第二次 reboot。未取得屏幕录像，具体物理 UI 阶段不细分。
- 待调查运行现象：`vendor.ir-hal-1-0` service restarting；当前没有证明其根因或用户可见影响，且未阻止 framework boot complete。
- 生产 user build 拒绝普通 shell 读取 `/proc/cmdline`、`/proc/bootconfig` 和 netd process maps；没有尝试 adb root。
- 后续用户报告：在 M02 OS4.0.19 安装评论区提供的 Magisk 模块并重启后，惯性滑动掉帧改善。模块审计见 [M03_SCROLL_FIX_MODULE_AUDIT.md](../reports/m03_scroll_fix_module_audit/M03_SCROLL_FIX_MODULE_AUDIT.md)。模块安装后的 live boot/root 状态未重新只读核验，不能默认仍与冻结 `boot_noroot` r3 完全一致。
- 本次 `adb devices -l` 没有列出设备；未读取模块运行日志或当前 boot 状态。
- 脱敏运行报告：[M02_FIRST_BOOT_RUNTIME_REPORT.md](../reports/m02_runtime/M02_FIRST_BOOT_RUNTIME_REPORT.md)。完整 raw runtime capture 仅在私有工作区。

## M02 构建与来源

- Exact Official madrid OS4.0.15、Known-Good thyme 4.0.15 与 Official 4.0.19 已完成三方对照。MADRID-M02 r3 保留 Known-Good boot/vendor_boot/dtbo/vbmeta/vbmeta_system 和 thyme vendor/odm/mi_ext 适配，叠加受控的 Official 4.0.19 system/system_ext 更新及 allowlisted release properties。
- 12-image inventory/hash、EROFS/ext4、EROFS 全树 round-trip、property allowlist、LP metadata checksums 与 A/B extent gates 均通过。静态 gate 与本轮 framework boot complete 证据分开记录。
- 首次 OS4.0.19 base 前清理过 userdata 与 metadata。未刷 Madrid firmware、DLKM、B 槽或保护分区。
- 当前 Candidate 及构建报告：[M02 adaptation delta](../reports/m02_adaptation_delta/M02_ADAPTATION_DELTA_REPORT.md)、[build report](../reports/m02_adaptation_delta/M02_CANDIDATE_BUILD_REPORT.md)、[staging report](../reports/m02_adaptation_delta/MADRID_M02_STAGING_REPORT.md)。

## M03 Port Provenance Audit

- 报告：[M03_PORT_PROVENANCE_AND_METHOD_REPORT.md](../reports/m03_port_provenance/M03_PORT_PROVENANCE_AND_METHOD_REPORT.md)；[Component Provenance Matrix](../reports/m03_port_provenance/PORT_PROVENANCE_MATRIX.md)。
- 结论：Known-Good package adaptation stack 已由 M01-R3 真机验证。M02 保留 Known-Good boot/kernel 与 thyme vendor/odm hardware layer，将官方 4.0.19 的 219 个 system、60 个 system_ext 变更及两处 build.prop 合并重基，重建 EROFS/super/LP；vbmeta 继承自 Known-Good。
- 百分比仅是六个 dynamic filesystem regular-file 的 bytes/files 构成估算，不代表工程工作量。Kernel 来源、精确 stock vendor/odm ancestry、SELinux Permissive 来源及个人作者归属未证实。
- 本轮只读分析，设备没有重启或修改；M02 仍运行。等待用户审阅报告后再决定下一阶段。

## 滑动掉帧模块审计

- 用户报告完整 Magisk 模块在 M02 OS4.0.19 重启后改善惯性滑动。Battery workaround 短暂模拟 AC/充电/100% 状态并睡眠/唤醒屏幕，再 reset；没有直接调 governor、GPU、刷新率或触控 sysfs。
- 下一步建议若集成，只带 battery-only 的 ROM init 一次性服务；模块里的 OS3/A16 IMS APK、6 个库及首次 `pm clear` 不与滑动 workaround 混合。
- 这是用户现场观察，无模块日志或单变量对照。集成权限、SELinux 和 battery reset 仍待实机验证；本次没有构建或刷写。

## Known-Good 与 Legacy 边界

- M01-R3 已实机确认 Known-Good OS4.0.15 thyme stack、4.19.325-cxk kernel、Tethering APEX、netd/INetd、BPF runtime 可启动；未刷 success firmware。R1/R2 空 pstore 不代表 kernel 未执行。
- M01-R3 同时清除了 userdata 与 metadata，因此 clean-data 与启动成功强相关，但没有拆分两者单独作用。
- Legacy C1–C47 保留为兼容性研究数据库；Legacy-C48/netd NOP、旧 netd patch 和 firmware bundle 不在当前主线。

## 下一步与安全边界

- M03 provenance audit 已完成，等待用户审阅后确定下一任务。vendor.ir-hal-1-0 restarting 仍未解释，但不属于本轮范围。
- 保持当前 Android 运行。任何新正式启动实验都必须等候该轮唯一启动确认；模块安装后的确切 boot/root 状态尚未核验。
- 不 relock；不写 `persist`、`modemst*`、`fsg/EFS`、NV、RF calibration、identity 或 FRP。不公开 ROM、镜像、专有二进制、raw device logs 或设备标识。
