# M03 滑动掉帧修复模块审计

日期：2026-10-06 HKT
范围：只读检查用户提供的 MI10s OS4.0.15 Magisk 模块，并与 MADRID-M02 OS4.0.19 的已记录文件清单比较。没有构建、刷写、安装、重启或修改设备。

## 结论

模块里用于缓解重启后惯性滑动掉帧的代码，可以单独转成 ROM 内置的开机一次性服务。它不是 GPU、CPU governor、触控采样率或刷新率调参，而是短暂修改 Android BatteryService 的模拟电量状态，再锁屏/亮屏一次，最后恢复真实电池状态。用户报告该完整模块在当前 MADRID-M02 OS4.0.19 上重启后改善了惯性滑动；这是真机用户观察，但目前没有该次启动的服务日志、前后测量或单变量对照，尚不能证明电量序列是唯一有效成分或已查明底层原因。

本审计建议：若纳入新包，只移植电量状态恢复序列；不要将通信修复部分一并搬入。ROM 内集成应改为 init 触发的一次性服务，不能原样复制 Magisk 的 `service.sh` 期待它自行运行。命令权限、SELinux 域和屏幕键事件仍须在集成候选上验证。

**后续状态（2026-10-06）：**这是一项初步 workaround 集成建议，现已由 [M03_SCROLL_ROOT_CAUSE_INVESTIGATION.md](M03_SCROLL_ROOT_CAUSE_INVESTIGATION.md) 中发现的 PowerKeeper 帧率方法空实现候选取代。当前先验证该代码差异；在单变量真机测试完成前，不把 battery-only workaround 作为 ROM 主线修复。

## 包与脚本证据

- 用户提供包：`MI10s-4.0.15.0针对修复-v1.0.zip`，SHA256 `0f175d1db8467c949eb46673b210ea6ca662982adc340c8852155d3c5897cc12`。
- `module.prop` 标识模块 `mi10sfix`；`META-INF/com/google/android/update-binary` 调用 `/data/adb/magisk/util_functions.sh` 的 `install_module`。这是 Magisk 模块格式，不是可直接并入系统镜像后自动运行的普通 ZIP。
- `service.sh` 等待 `sys.boot_completed=1`，然后确认 uptime 至少 27 秒；接着调用 `cmd battery set ac 1`、`status 2`、`level 100`，发送 `KEYCODE_SLEEP` 和 `KEYCODE_WAKEUP`，约 2 秒后 `cmd battery reset`。脚本还包含 120 秒恢复看门狗、旧状态清理、自检和 Magisk 模块目录日志。
- 时序细节：代码先等 `sys.boot_completed`，再等 uptime 不早于 27 秒。因此在正常启动耗时已超过 27 秒时，动作会在 `sys.boot_completed` 后立即执行，并非固定延迟到开机第 27 秒。
- Android AOSP BatteryService 将 `battery set` 定义为强制设置并冻结电池状态，`battery reset` 则解除冻结、恢复硬件值；因此它确实在操作 framework 模拟状态，不是直接写电池计或调 CPU/GPU。[AOSP BatteryService](https://android.googlesource.com/platform/frameworks/base/+/a7ce4e3/services/core/java/com/android/server/BatteryService.java)
- `service.sh` 未写入 governor、devfreq、刷新率、触控节点、SurfaceFlinger 参数或内核 sysfs。更准确的分类是“触发 framework/显示状态重置的 workaround”，而不是已证明的掉帧根因修复。

## 与通信修复的边界

同一模块还包含独立 IMS 变更：覆盖 `system_ext/priv-app/ims/ims.apk` 和 6 个 IMS `.so`，并在首次运行时执行 `pm clear org.codeaurora.ims`。README 声称这些客户端文件来自 OS3 / Android 16，用于接回 thyme vendor 的 HIDL IMS HAL。

该 IMS 组件不是滑动修复所需。清单显示，MADRID-M02 所基于的 Madrid OS4.0.19 `ims.apk` 为 914,699 B、SHA256 `aba5867d302548594d232f80e2bfa649f91e4900ee1e70227e16d1fbecae1732`；模块内 OS3 文件为 1,594,635 B、SHA256 `56f103215b1aa301e65b6ecde29bb67318cba07f3f3d91d2196372fd14d44172`。它们不是同一 APK。模块配套 IMS libraries 也与 M02 清单不同。没有单独 IMS/通话兼容性证据前，不应将旧 IMS APK、6 个库或 `pm clear` 纳入 M02 滑动修复。

## 对 M02 的实机证据与限制

- 用户确认测试对象是当前 MADRID-M02 OS4.0.19，并报告安装此模块、重启后惯性滑动恢复顺畅。该信息记录为用户提供的真机观察；本次没有读取模块 `/data/adb/modules/mi10sfix/last_run.log`，也没有独立验证模块服务是否完整执行。
- 本次只读检查时，主机 `adb devices -l` 没有列出设备，因此无法核验当前 live boot/root 状态或读取模块日志。
- 整个模块同时包含电量 workaround 和 IMS 文件覆盖，因此该次结果证明“完整模块与用户观察到的改善相关”，不能单独隔离电量序列的因果作用。此前的无模块 M02 启动/稳定记录也不能替代同条件前后量测。
- 冻结 M02 r3 使用 `boot_noroot.img`。本模块依赖 Magisk；用户此次安装后，当前设备的 boot/root 运行状态与 r3 冻结镜像是否仍一致尚未通过只读设备检查确认。OS4.0.19 指纹仍是此前确认值，但不得据此默认当前 boot image 未变。

## 集成建议

1. 作为独立 M02 修订，只带入 battery-only 代码；保留短时模拟、屏幕睡眠/唤醒、最终 `reset`、异常恢复和可辨认日志。
2. 由 Android init 在 `sys.boot_completed=1` 后触发一次，不依赖 Magisk/root 管理器，也不修改 Known-Good kernel、DTBO、vendor/ODM、firmware 或 IMS 文件。
3. 先完成静态构建门禁，再在设备上验证命令是否成功、真实电量是否恢复、启动/解锁流程是否受影响，以及惯性滑动是否改善。当前 M02 SELinux permissive 的来源未确认，不能以此推断 enforcing 下权限一定正确。
4. 将其标注为经过用户实机观察支持的 workaround；只有后续取得分离测试与机制证据，才升级为根因修复结论。

本次审计没有修改 Candidate、设备或原始模块包。M02 修订的构建/刷写尚未开始。
