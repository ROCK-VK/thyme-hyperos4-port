# MADRID-M02 r3 首次启动与运行时报告

日期：2026-10-06（HKT）
状态：首次实机启动达到 Android framework boot complete；用户确认开机成功且设备稳定。设备保持运行。

## 启动门禁与时间线

- 首启前 Fastboot 只读状态为 `thyme`、A 槽、Bootloader Fastboot、bootloader unlocked；A 槽 retry budget 为 7。
- Candidate 静态门禁报告通过。`boot_noroot`、`vendor_boot`、`dtbo`、`super`、`vbmeta`、`vbmeta_system` 六个目标镜像的启动前 SHA256 均与冻结清单一致。
- 只发出一次 `fastboot reboot`，返回成功；本次没有重刷镜像或 firmware。
- ADB 在启动后约 T+205 秒首次显示 `unauthorized`，T+207.2 秒变为 `device`；Fastboot 未重新出现。
- `sys.boot_completed=1`。用户现场确认开机成功，之后确认设备稳定。用户要求不再等待 10 分钟观察；主机只读轮询在约 121 秒后停止，停止前 ADB 在线、Fastboot 未出现且 boot complete 仍为 1。没有第二次 reboot。
- 未保存屏幕录像，因此只报告 framework boot complete，不对 SetupWizard、锁屏或桌面作独立等级判定。

## 实际运行版本

- Fingerprint：`Xiaomi/thyme/thyme:17/CP2A.260605.016/OS4.0.19.0.XEOCNXM:user/release-keys`
- `/proc/version`：`4.19.325-cxk-lxsclnb-g33d88af64048`，与已验证 Known-Good boot stack 的 kernel banner 一致。
- 当前 slot suffix 为 `_a`。

## 关键 framework 与网络运行态

- `com.android.tethering` APEX 位于 `/data/apex/decompressed` 并挂载到 `/apex`。
- Tethering Binder service 与 `android.system.net.netd.INetd/default` 可见；netd dump 显示 updatable init 成功、Netd started。
- Tethering 运行态报告 BPF enabled；IPv4/IPv6 upstream/downstream、stats、limit、device 主要 maps 均为 OK。
- 本次没有建立 hotspot/upstream session，因此真实数据转发路径尚未验证。
- SELinux 为 Permissive。定点检查的 dmesg 未发现 kernel panic、Oops、mount 或 dm-verity failure marker。

## 尚待核实的问题与证据限制

- `vendor.ir-hal-1-0` 在 init 状态中反复 restarting，且 `sys.init.updatable_crashing=1`。它没有阻止 framework boot complete；根因和对红外功能的影响尚未确认。
- 普通 ADB shell 权限不能读取 `/proc/cmdline`、`/proc/bootconfig` 与 netd process maps；没有尝试 adb root。
- runtime capture 包含完整属性、服务、mount、dumpsys、logcat 与 dmesg 等设备运行数据，只留在私有工作区；公开仓库没有 raw logs、设备序列号、ROM 或分区镜像。

## 结论

MADRID-M02 r3 的 OS4.0.19 framework 在已验证的 Known-Good thyme boot/kernel 与硬件适配栈上完成一次实机启动，并达到 `sys.boot_completed=1`。Tethering APEX、netd/INetd 与主要 BPF map 状态正常。该结果不等同于长期稳定性或完整硬件/网络功能认证。用户反馈设备稳定后，本轮 10 分钟主机观察按要求提前结束；设备继续保持运行，不执行 reboot。
