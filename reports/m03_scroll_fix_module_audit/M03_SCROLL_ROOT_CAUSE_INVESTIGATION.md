# M03 滑动掉帧根因调查

日期：2026-10-06 HKT

范围：静态检查模块、对比 Known-Good/M02 与官方 PowerKeeper、核对已有 M02 运行记录，并准备可撤销的匹配对照包。未安装模块、未修改设备、未重启或刷写。

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

已在本机准备成对的 Magisk 更新 ZIP。两包使用相同模块 ID、相同 IMS overlays 和逐字节相同的只读 `service.sh`；基线包不覆盖 PowerKeeper，候选包只新增官方 PowerKeeper overlay。

- **P0 基线包：**`work/scroll_source_audit/MI10s-PowerKeeper-Baseline-No-Workaround-v1.zip`；SHA256 `72df859431b47f04ed5f488b70f07ac18a8d2b9aa892f08ac65ccd7ac3a5c114`。它停用电量/屏幕 workaround，但不覆盖 M02 当前 Known-Good PowerKeeper（预期 hash `d900a0767b3008a7356c83a812fbbcbef029e77b7b16084efbfdb4aeddcd1f59`）。模块 versionCode=101。
- **P1 官方代码包：**`work/scroll_source_audit/MI10s-PowerKeeper-Official-No-Workaround-v1.zip`；SHA256 `720449201315cddf7b82b4c5199b4b53eb0631e8c64c4e8f54d71104dcee7713`。它在 P0 完全相同的脚本/IMS 条件下，仅增加精确官方 Madrid OS4.0.19 PowerKeeper APK（hash `4847e9aaabee508e6ac8dd848d521900e4483d0a302ffa4cf66446aae3baa5ab`）。模块 versionCode=102。
- 构建器：`tools/build_scroll_source_test_module.ps1`

P0/P1 的展开内容校验确认：除 `module.prop`/安装提示文字和 P1 新增的 PowerKeeper APK 外，其余模块文件相同；两包 IMS overlay 完全相同，`service.sh` SHA256 均为 `03b0e72cb363fb9f004ddfbe895229851758fa9aa939bd23c70b0bcaf13dbc8d`。脚本只记录 boot 完成后的电池读数、刷新率设置、PowerKeeper 路径/hash 和 display mode，不伪造电量、不睡眠/唤醒屏幕、不清 IMS 数据。两包 ZIP 完整性、APK 来源 hash 和 `sh -n` 检查通过。

两包仅在私有本地工作区准备，未纳入公开仓库；也都尚未安装。设备 ADB 未连接，当前 root/Magisk live 状态没有被重新检查。复验顺序：先安装 P0，等用户通过本轮唯一确认点后启动一次；确认 `root_cause_test.log` 中 PowerKeeper hash 为 M02 版，并在同一界面手动检查惯性滑动。只有 P0 确实重现掉帧，才安装 P1 并申请下一次启动确认；再用相同场景复测。若 P0 不复现，停止比较，不把 P1 的结果宣称为根因证明。

### 结果解释

- 若 P0 可重现而 P1 在同条件下改善，则“移植版 PowerKeeper 空方法”得到强实机支持；下一步再把该 APK/方法恢复方案做成正式 M02 修订并完成完整镜像门禁。
- 若 P0 可重现而 P1 无改善，降级 PowerKeeper 假说；随后分开测试 battery state transition 与 sleep/wake，再检查 thyme display/power/touch 配置和内核输入/调度路径。
- 若 P0 不重现，停止测试，保持根因未定；既往的完整模块改善反馈不能代替匹配对照。
- 若结果不稳定或条件变化，结论保持未定，不重复做无控制重启。

## 尚未确认

- 该空方法为何由原移植者加入，以及它是否是有意规避其他设备上的不兼容行为。
- 卡顿对应的实际 display refresh mode、SurfaceFlinger frame timeline、触控事件、CPU/GPU/thermal 状态。
- 电量伪造、睡眠/唤醒、PowerKeeper 空方法三者各自的因果贡献。
- 测试 APK overlay 在当前 Magisk/live boot 上的实际挂载和 PackageManager 接受结果。

本报告的结论等级：APK/DEX 精确差异为 B 级静态证据；旧 M02 运行记录为既有设备运行证据但与症状的关联有限；用户模块改善反馈为用户提供的实机观察；具体根因仍待单变量真机复验。
