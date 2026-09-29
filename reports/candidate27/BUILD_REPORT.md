# Candidate 27 netd/Zygote 重启耦合实验与构建报告

## C26 根因证据

C26 中 netd（PID 1046）因 25Q2+ 对 Linux <5.4 的检查 SIGABRT。约 94 ms 后 init 向首次 Zygote（PID 1060）进程组发送 SIGKILL，并对 secondary Zygote（PID 1061）做同样处理。随后两个服务状态从 running 转 stopping，netd 转 restarting。实际 C26 `netd.rc` 含 `onrestart restart zygote` 和 `onrestart restart zygote_secondary`，与顺序一致。保存日志能证明 init 发出 SIGKILL，但没有 waitpid status，故 Zygote 最终 wait status/exit code 未知；没有捕获归属 Zygote 的 fatal 或 tombstone。

## C27 改动

以 C26 为基线，只从 netd.rc 移除上述两条反向重启回调；netd 的 Android 25Q2/Linux 4.19 检查、崩溃与自身重启行为保留。因此网络服务可能仍不可用。此项修复/实验直接针对 C26 已观察到的 init SIGKILL 链，目标是让 Zygote 和 system_server 不再因 netd 重启被 init 一并杀掉。

同时用有界 logger 替代 C26 旋转式 logcat：post-fs-data 后启动，捕获 crash/main/system/events，单一 metadata 文件，无轮转/删除；最长 8 分钟，容量为可用空间扣 12 MiB（为 C25 sampler 8 MiB、C27 event/tail 约 1.5 MiB 与 2.5 MiB 余量）后最多 24 MiB，状态文件记录真实子进程退出码、信号、stderr、时长、字节数和停止原因。Zygote watcher 仍使用现有 shell 域和 SELinux policy，不读取此前触发 AVC 的 `init.svc_debug_pid.zygote*`。

## K40 对照及边界

指定的 K40 OS4.0.0.8 包中 netd 二进制与 netd.rc 均与 C26 相同；包内 boot kernel 字符串是 Linux 4.19.325，但这不是 K40 正在运行时的 uname。K40 成功运行与静态 25Q2 内核门槛之间仍有未解决差异，不用推测填补。现有证据不足以把该回调删除归因于 K40 移植做法；C27 是基于 C26 的直接事件链做隔离验证。

## 构建/设备边界

若构建成功，只重建 system、配套 vbmeta_system 和 super，继承 boot、vendor_boot、dtbo、vbmeta。预定刷写范围为 `super` 与 `vbmeta_system_a`。本任务不启动 C26/C27，不运行 set_active，不刷写或改 A/B 元数据；首次启动前需另行取得 A 槽预算恢复授权。
