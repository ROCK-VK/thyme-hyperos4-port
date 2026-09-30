# THYME-OS4 项目当前状态

更新时间：2026-09-30 16:40 HKT

## 项目目标与阶段
将 Xiaomi 15（dada）HyperOS 4 / Android 17 移植到 Xiaomi 10S（thyme）。当前主线是依据 C30 真实启动证据定位 PID 1 panic 的上游触发条件；第三方 Milo 包已完成离线评估，不作为当前 Candidate。

## 当前 Candidate 与设备状态
- C30 的 super 与 vbmeta_system_a 已刷入 A 槽并启动过一次；用户观察到静止 Xiaomi 第一屏，ADB 未上线。
- C30 console-ramoops 在约 32.922 秒记录 PID 1 init 经 write_sysrq_trigger 主动触发 kernel panic。上游 init fatal 条件仍未闭环；不能归因于 netd/Zygote。
- C30 pmsg 证明 /data、fscrypt 与 keystore2 初始化推进；netd 多次 SIGABRT。诊断 helper 的 canary/events/logcat 未留下有效内容，不能据此断定 system_server/Zygote 状态。
- 最近一次只读设备查询（2026-09-30 13:09 HKT）：Bootloader Fastboot；product=thyme，A 槽，unlocked=yes，is-userspace=no；A no/no/retry=3，B no/no/retry=7。此次第三方离线审计没有查询或操作手机；状态未被本轮改变。
- C30 本地镜像与 Unified First-Response Standalone 取证资产保持不变。没有再次启动 C30、刷写、set_active、清除数据或恢复 PixelOS。

## 第三方 Milo HyperOS4 包离线审计
- 本地目录：10S系统/小米10s-MiloHyperOS-4.0.0.44TGNCNXM。49 个文件，总计 7,602,127,591 B（约 7.08 GiB）。
- 类型：自定义 Windows Fastboot 包与面向 muyu 的 Recovery updater/不一致 OTA metadata 混合；不能认定为可靠 thyme 发布包。
- BAT 会 erase frp、刷 super 与多项底层/启动分区（含 modem）、对 vbmeta A/B 写入、set_active a、自动 reboot；菜单选项 2 会 erase userdata/metadata。Recovery updater 直接写很多 _a/_b 节点，且引用六种包内缺失固件源。
- boot/vendor_boot/dtbo/vbmeta/vbmeta_system 与本地 10S Android 13 官方基线逐字节相同；低层固件与 10S stock lineage 相符。super 的 LP 结构与 C30 不同，vbmeta 是 Android 13 基线，不能直接视为 C30 兼容产物。
- system/system_ext 指向 generic missi Android 17 build；product 指向 thyme；vendor 指向 thyme Android 13。仅凭元数据无法证明精确供体为 dada。
- netd.rc 保留 netd→primary/secondary Zygote restart；netbpfload 和 libnetd_updatable 与 C30/K40 对应二进制相同。未发现解决 C30 当前 PID 1/Zygote 问题的新增兼容修复。
- 用户转述作者承认此前分区映射有误，因为忽略 10S 的 A/B 分区。未收到修订包/准确映射。项目本地 10S 官方 fastboot 脚本也使用 boot_ab/vendor_boot_ab 等目标名，因此具体错项尚不能从这句话独立确定；当前包仍因写入范围、Recovery 来源、LP/AVB 不一致而不适合作为实机 Candidate。
- External Candidate：不通过。本轮未生成 staging/Dry-Run，第三方 exe/bat/apk 均未运行，未向手机发送命令。
- 报告与清单：work/reports/third_party_milo_hyperos4_audit_20260930/THIRD_PARTY_PORT_STRATEGY.md 及同目录 CSV/diff。

### Milo system 与 C30 四方启动链定点比较（2026-09-30）
- Milo、C30 实际 system、Xiaomi 15 donor、K40 Android 17 system 的定点比较未发现可解释 C30 PID 1/Zygote 启动故障的 Milo 专属补丁；未构建 C31、未操作设备。
- Milo 的 Zygote rc、ART/runtime APEX、classpath、linker config、VINTF 文件与其他三方指定文件逐字节相同。其 netd callbacks 和 stock Android 17 netbpfload 仍存在；C30 的两项差异是已有工程修复，Milo 不提供替代方案。
- Milo `services.jar`、`framework-res.apk`、`libandroid_runtime.so` 有版本字节差异，尚无证据映射到当前 PID 1 fatal。C30 `surfaceflinger.rc` 的 ANGLE 属性段是旧实验遗留，不是 Milo 修复。
- 最新报告与文本清单见 `reports/third_party_milo_c30_startup_diff_20260930/`。未上传 ROM/镜像/第三方程序。

## 安全、磁盘与公开仓库
- Bootloader 保持解锁；禁止回锁及擅自修改 persist 硬件分区、modemst、EFS/NV、射频校准或设备身份资料。
- 最近记录的 C/D/E 空间均高于 50 GiB；Docker 永远排除。此次为定点离线检查，无清理。
- 原始 ROM、镜像、设备 raw metadata/misc 及未脱敏硬件身份资料不得公开。第三方包仅公开审计文档、CSV 清单与小型文本差异，不公开其 exe/apk/镜像。

## 下一步
1. 若作者提供修订包及逐项 A/B 分区映射，对新版本单独进行静态复核；不复用旧包结论替代新包证据。
2. 当前主线仍是定点分析 C30 PID 1 panic 前的 init fatal 条件与诊断留证。
3. 新 Candidate 启动前等待用户现场确认；本状态不授权设备操作。

## 最新公开同步
- 第三方 Milo 离线审计材料已推送至公开仓库 main；审计首发提交 9e7ff9dc3cb7b1648a849de0290f38080692cba0。匿名 raw 报告、manifest、PROJECT_STATUS 与 reports 索引均返回 HTTP 200。
- 公开目录 reports/third_party_milo_hyperos4_audit_20260930/ 仅含报告、CSV 和文本 diff；未包含第三方 EXE/APK/ROM 镜像或设备 raw 分区副本。
