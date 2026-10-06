# M03 滑动掉帧根因调查

日期：2026-10-06 HKT

范围：静态检查模块、对比 Known-Good/M02 与官方 PowerKeeper、核对已有 M02 运行记录，并准备可撤销的单变量代码候选。未安装模块、未修改设备、未重启或刷写。

## 当前结论

评论区模块目前只能定性为状态重触发 workaround，不能说已经修复根因。它不依赖手机真实充满电：脚本通过 Android BatteryService 短暂伪造 AC 接入、充电状态和 100% 电量，随后让屏幕睡眠/唤醒，再恢复真实电池状态。模块将电量变化与显示状态变化合并执行，因此用户观察到的改善尚未隔离到其中某一个动作。

现在发现了一个比“电池到 100%”更直接、且可真机验证的源码候选：Known-Good/M02 的 PowerKeeper 把完整的显示帧率策略方法 `DisplayFrameSetting.setScreenEffect(String,int,int)` 改成了空方法；官方 Madrid OS4.0.15 与 OS4.0.19 中该方法均保留完整实现。它属于强静态候选，与 60/90Hz 和 app FPS 策略直接相关，但现有材料仍不能证明它就是用户所见惯性滑动掉帧的唯一根因。

## 证据

### 模块实际动作

`10S系统/修复通信和重启后滑动掉帧模块/service.sh` 在 `sys.boot_completed=1` 后短暂执行：

1. `cmd battery set ac 1`、`status 2`、`level 100`；
2. 发送 `KEYCODE_SLEEP`，约一秒后发送 `KEYCODE_WAKEUP`；
3. 两秒后执行 `cmd battery reset`。

没有改 CPU/GPU governor、devfreq、触控采样率、刷新率节点或内核参数。因此，这段脚本本身没有直接修补帧率控制实现；它促使电源和显示状态机重新收到状态变化。AOSP BatteryService 对 `set`/`reset` 的定义也符合“冻结模拟值、再恢复硬件值”的行为。[AOSP BatteryService](https://android.googlesource.com/platform/frameworks/base/+/a7ce4e3/services/core/java/com/android/server/BatteryService.java)

### PowerKeeper 精确对比

| 文件 | SHA256 | 含义 |
| --- | --- | --- |
| 官方 Madrid OS4.0.15 PowerKeeper.apk | `4847e9aaabee508e6ac8dd848d521900e4483d0a302ffa4cf66446aae3baa5ab` | 与官方 OS4.0.19 完全相同 |
| 官方 Madrid OS4.0.19 PowerKeeper.apk | `4847e9aaabee508e6ac8dd848d521900e4483d0a302ffa4cf66446aae3baa5ab` | 目标版本原 APK |
| Known-Good 4.0.15→thyme PowerKeeper.apk | `d900a0767b3008a7356c83a812fbbcbef029e77b7b16084efbfdb4aeddcd1f59` | 移植者修改版 |
| MADRID-M02 r3 PowerKeeper.apk | `d900a0767b3008a7356c83a812fbbcbef029e77b7b16084efbfdb4aeddcd1f59` | 原样继承 Known-Good 修改版 |

两个 APK 压缩包的条目对比显示，差异只有 `classes.dex`。对 DEX 方法指令流作符号化比较后，6,197 个类中只发现一个方法的指令不同：

- Known-Good/M02：`DisplayFrameSetting.setScreenEffect(String,int,int)` 的 `insns size` 为 1，只剩 `return-void`。
- 官方 Madrid：同一方法为 539 个 16-bit code units；它根据 `mUserFps`、当前帧率和策略处理 `applyFpsViaPowerkeeper`、`DisplayFeatureManager.setScreenEffect` 及 SurfaceFlinger FPS 通知。

这证明了该方法被移植版明确停用，但不证明停用的动机，也不证明它与用户报告的具体卡顿之间存在唯一因果关系。M02 r3 与 Known-Good APK 哈希相同，故这项修改确实存在于当前 OS4.0.19 Candidate。

### 已有运行记录的边界

私有 M02 runtime capture 记录到启动期间 DisplayModeDirector 从 60Hz 策略切换到 90Hz 策略，并出现 SetupWizard 阶段的 PowerKeeper jank 记录；捕获时 Display 状态报告 active mode 2 / 90Hz。它表明启动期策略和帧耗时值得继续检查，但不等同于用户在日常界面惯性滑动时的实测，也不能据此宣称屏幕一直锁在 60Hz。

用户报告完整模块在 MADRID-M02 OS4.0.19 上重启后滑动改善，属于实机观察；没有该次 `last_run.log`，也没有单独开关电量伪造与睡眠/唤醒的 A/B 数据。本轮 `adb devices -l` 仍未发现设备，因此没有新增 live runtime 证据。

## 下一步最小复验

已在本机准备仅供诊断的 Magisk 更新 ZIP：

- 文件：`work/scroll_source_audit/MI10s-PowerKeeper-Source-Test-v1.zip`
- SHA256：`049d327613f6de065360920b8f2398c13f076b49a4987f5276eb91b85c7300fa`
- 构建器：`tools/build_scroll_source_test_module.ps1`

测试 ZIP 沿用原模块 ID，保留原有 IMS APK/库 overlay 不变；把 PowerKeeper 替换为哈希固定的官方 Madrid OS4.0.19 APK，并以只读日志脚本替代原滑动 workaround。新脚本只记录 boot 完成后的电池读数、刷新率设置、PowerKeeper 路径/hash 和 display mode，不伪造电量、不睡眠/唤醒屏幕、不清 IMS 数据。ZIP 条目校验确认原模块其他文件保持不变；shell 语法检查及 ZIP 完整性检查通过。

该 ZIP 尚未安装。设备 ADB 未连接，当前 root/Magisk live 状态没有被重新检查。安装后应只进行一次观察启动，并由用户在同样的惯性滑动场景检查现象，同时采集 `root_cause_test.log` 和有限的 display/PowerKeeper 日志。启动仍需遵守项目的唯一首启确认点。

### 结果解释

- 若去掉电量/屏幕状态触发后，官方 PowerKeeper 候选仍能稳定消除卡顿，则“移植版 PowerKeeper 空方法”得到强实机支持；下一步再把单方法恢复方案做成正式 M02 修订并完成完整镜像门禁。
- 若卡顿仍在，先不把 PowerKeeper 定为根因；随后分开测试 battery state transition 与 sleep/wake，最后再检查 thyme display/power/touch 配置和内核输入/调度路径。
- 若结果不稳定或条件变化，结论保持未定，不重复做无控制重启。

## 尚未确认

- 该空方法为何由原移植者加入，以及它是否是有意规避其他设备上的不兼容行为。
- 卡顿对应的实际 display refresh mode、SurfaceFlinger frame timeline、触控事件、CPU/GPU/thermal 状态。
- 电量伪造、睡眠/唤醒、PowerKeeper 空方法三者各自的因果贡献。
- 测试 APK overlay 在当前 Magisk/live boot 上的实际挂载和 PackageManager 接受结果。

本报告的结论等级：APK/DEX 精确差异为 B 级静态证据；旧 M02 运行记录为既有设备运行证据但与症状的关联有限；用户模块改善反馈为用户提供的实机观察；具体根因仍待单变量真机复验。
