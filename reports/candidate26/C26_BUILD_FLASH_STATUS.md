# THYME-OS4 Candidate 26 构建与刷写状态

时间：2026-09-29（香港时间）

## 结论

C26 已基于 C25 完成主机构建，并已刷写 `super` 与 `vbmeta_system_a`。刷写脚本结束后设备仍处于 Bootloader Fastboot。C26 尚未启动；诊断服务效果、Zygote 退出原因及后续启动阶段均未验证。

## K40 定点对照

项目缓存中的 Redmi K40（alioth）OS4.0.0.8 Android 17 成功移植包与 Xiaomi 15 供体及 C25 对照结果：`init.zygote64.rc`、`init.zygote64_32.rc`、`app_process32/64`、`libandroid_runtime.so`、`bootclasspath.pb`、`systemserverclasspath.pb`、ART `com.android.art.capex` 和 `com.android.runtime.apex` 均逐字节一致；相关 `dalvik.vm` 参数也没有可解释 C25 Zygote 重启的新差异。未发现可直接移植的 K40 Zygote/ART 修复，因此没有替换供体运行时或 K40 设备专属组件。

## C26 诊断增量

- 保留 C25 的持久启动阶段采样。
- 新增 `c26_zygote_diag`：init `post-fs-data` 后启动连续 logd buffer 采集，输出到 `/metadata/thyme_os4_diag`，每份最多 1 MiB、保留当前文件及三个轮转文件。
- 新增属性等待监视器，最多运行 15 分钟，观察 zygote、zygote_secondary、采集服务等状态；检测到 Zygote restarting/stopped 时记录可见进程 cmdline/status，并采集最多 8 份 crash/system/main 日志尾部。
- 使用现有 shell SELinux 域和 C25 metadata 诊断目录策略；未改 platform CIL、GPU/HWC、ART、内核、fstab、加密路径或设备硬件分区。
- K40 对照文件：`runtime_comparison.txt`。

## 构建验证

- 构建脚本：`tools/build_candidate26_zygote_diag.py`。
- C26 helper 使用 Android NDK r29 编译为 Android AArch64 PIE，并通过 `-Wall -Wextra -Werror` 编译；依赖 `liblog.so`，C++ 运行库静态链接。
- 构建器报告 system EROFS 内容检查、system AVB footer 验证、`vbmeta_system` 描述符更新、LP extent/逻辑输入校验及六镜像清单完成。
- manifest 中 `system_build.final_erofs_readback["/system/bin/c26_zygote_diag"].bytes` 是构建器将 `dump.erofs --cat` 输出按文本读取后保存的输出长度，不能解释为 ELF 原始文件大小；该项用于检查 ASCII 标记。原始 helper 大小和 SHA-256 记在 manifest 的 `runtime_helper`。刷写脚本对实际 `super.img` 和 `vbmeta_system.img` 大小/SHA-256 重新核验。

## 实际镜像与刷写范围

| 分区目标 | 镜像 | 大小 | SHA-256 | 实际结果 |
|---|---|---:|---|---|
| `super` | `super.img` | 7,703,583,704 B | `601FF7548F658442B9F17176FB2AC391791E1453660E55A41D8B292E1E290E62` | 10/10 sparse chunks 均发送、写入成功 |
| `vbmeta_system_a` | `vbmeta_system.img` | 131,072 B | `194000046E3FA288322D4D9D01B65559042DBCB27E3E354C986796888ABA40A3` | 发送、写入成功 |

刷写前只读预检确认唯一目标为 thyme、A 槽、Bootloader 已解锁、非 userspace Fastboot；A 槽 `unbootable=no`、`successful=no`、`retry=2`。刷写脚本结束后再次确认设备仍在 Bootloader Fastboot。未读取分区回读，因此上述结果表示 Fastboot 命令成功，不代表逐字节回读验证。

本次没有执行 reboot、slot 操作、数据清除、BCB/misc 修改、PixelOS 恢复或 Bootloader 回锁。

## 下一步

等待用户在手机旁准备观察后，先启动 C26 只读观察器并确认 ARMED，再执行一次受控启动。若 ADB 不上线，用户手动返回 Fastboot 后通过既有 Standalone 流程完整导出 THYME_DIAG 与 metadata 诊断目录，先备份校验再分析 Zygote 首次退出原因。
