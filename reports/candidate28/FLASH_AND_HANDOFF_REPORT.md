# THYME-OS4 Candidate 28 Recovery / Zygote 留证：构建与刷写交接报告

## 当前结论

C27 的进入 Recovery 原因仍未被历史证据唯一确定。对实际 C27 可达 init 配置的扫描发现两条显式 rebootrecovery --bad_nv 路径，均由 radio write-cache 属性触发；C27 没有保存这些触发属性或 sys.powerctl，因此只能列为候选路径。C28 在原条件和原命令前增加 init 自身写出的 marker，用于下一次启动验证实际路径。

C28 已完成主机构建并按限定范围刷写。设备当前保持 Bootloader Fastboot，C28 尚未启动；本报告不包含 C28 真机启动结果。

## C27 留证缺口与 C28 改进

C26 的 shell-domain logcat 直接读取 logd 并在 metadata 目录生成约 8.56 MB 输出。C27 使用父子进程管道捕获，状态文件先创建、但 START 要等 statvfs 和启动准备完成后才写；watcher 也先创建空事件/尾部文件，再执行若干读取，之后才写 START。C27 现场文件均为零字节，现有证据无法区分 helper 早退、写入或 fsync 失败、logcat 执行失败、突然重启等运行时原因。

C28 在状态文件打开后立即写入并 fsync START，再进行容量规划和进程创建；持久记录 helper/child PID；通过专用 errno pipe 留下 logcat exec 失败原因；记录退出码、信号、stderr、停止原因。使用单个有界 logcat 文件，不启用轮转，最长约 8 分钟、最多 24 MiB，并保留 metadata 空间余量。

此外，C28 由 init 内建 write 在 post-fs-data、netd/Zygote/bootanim/SurfaceFlinger 状态变化、sys.boot_completed、sys.powerctl、shutdown 及两条 --bad_nv Recovery action 前分别写 marker。两条 Recovery action 的触发条件和命令未改变。C27 移除的 netd onrestart Zygote callbacks 继续保持移除；没有改 netd 的内核版本检查。

## 主机侧构建与静态验证

C28 基于 C27 system tree 的硬链接克隆单独构建，没有修改 C27 原树。构建 manifest 记录的系统树变化为：替换诊断 helper/RC、file_contexts 增量，以及 init.rc 中的诊断 marker；无意外变化。没有修改 SELinux CIL、ART、netd、Zygote、GPU、HWC、Framework、fstab、加密、内核或设备硬件栈。

构建及必要检查通过：诊断 helper AArch64 ELF 架构/依赖检查、原始 EROFS readback 字节一致、EROFS fsck、init marker 与 file_context readback、netd callback 负向断言、system AVB hashtree、vbmeta_system descriptor 更新和 LP 输入/布局核对。刷写脚本语法检查和 Dry-Run 通过。

C28 未经实机验证的部分仍包括：init marker 的设备端写入、服务实际启动、shell-domain logcat 读取/持久化，以及 sys.powerctl/shutdown marker 能否赶在快速 Recovery 前写入。

## 实际刷写记录

刷写前只读预检唯一 Fastboot 设备 [设备序列号已脱敏]：

- product=thyme
- current-slot=a
- unlocked=yes
- is-userspace=no
- A unbootable=no / successful=no / retry=6

刷写脚本先核对最终镜像与 manifest，然后顺序写入以下两项：

- super：7,703,600,088 bytes；SHA-256 6B292A91F71C0800255D694BE04C816715DEBC44ADEA8A8CE7B018CB695F24CF。fastboot 将 sparse super 分 10 块发送；各块发送及写入均返回 OKAY，随后 Finished。
- vbmeta_system_a：131,072 bytes；SHA-256 BE82309DE7892151F3111E551E02BD90FB2F256C30A2803C1D77DAB692F00359。发送与写入均返回 OKAY。

刷写后重新读取设备：唯一设备仍为 [设备序列号已脱敏]，product=thyme、current-slot=a、unlocked=yes、is-userspace=no；A unbootable=no / successful=no / retry=6。设备保持 Bootloader Fastboot。没有执行 reboot、userdata/metadata 擦除、set_active、其他分区写入、BCB/misc 操作或 Bootloader 回锁。

## 下一步

C28 仍等待单独的现场启动确认。启动后观察器须先显示 ARMED，再执行唯一一次正式启动。若进入 Recovery，先由用户返回 Fastboot，然后按既有授权完整备份 THYME_DIAG 和 C28 metadata，再分析。

C28 要验证的是：netd/Zygote 状态链、system_server 是否出现、是否捕获 sys.powerctl/reboot,recovery，以及两条候选 --bad_nv action 是否实际触发。只有相应 marker 或日志出现，才能把候选 Recovery 路径升级为本轮实测原因。