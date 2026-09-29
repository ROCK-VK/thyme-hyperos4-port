# Candidate 28 Recovery/Zygote 可靠启动留证构建报告

## C27 诊断文件为空的结论

C26 的 `c26_zygote_diag --logcat` 在 `shell` SELinux 域直接 exec `/system/bin/logcat -b all -v threadtime,monotonic -f <file> -r 1024 -n 3`，并在同一 metadata 路径产生约 8.56 MB 日志。C27 仍使用 `shell` 用户/组和 `u:r:shell:s0`，也能创建相同 metadata 目录下的文件；其平台策略没有变化，因此现有材料不支持将零字节归因于 shell/logd/metadata 权限缺失。

C27 将 logcat 放进 helper 的子进程管道，并由父进程转写单一文件。源代码中 status 文件在 START 前已经创建；START 要等 statvfs、容量计划和字符串构造后才写。watcher 的 events/tails 文件也在 START 写入前创建，并先打开多个文件、读取属性。C27 最终只有零字节文件，无法知道是早期退出、写入/fsync 出错还是突然重启。故‘为什么零字节’只能定位到源码留证窗口不足，不能从这次设备证据确定实际发生了哪种运行时情况。

C28 在 status open 后立即用栈缓冲写入 `C28_LOGCAT_START` 并 fsync，之后才执行 statvfs、建立 pipes 或 fork；父进程先持久化 child PID，再放行 child；exec 失败通过专用 errno pipe 立即记录 `C28_LOGCAT_EXEC_FAILED`。logcat 采用 C26 已工作的 `-b all`，取消 `-r/-n`，维持单文件、8 分钟和最多 24 MiB，并每 1 秒或 128 KiB 对捕获文件 fdatasync。

## C27 Recovery 路径

对最终 C27 的 system、system_ext、product、vendor、odm、mi_ext init RC 进行有界扫描。显式 `rebootrecovery` 只发现 system init 的两条 `--bad_nv` action：`persist.vendor.radio.write.cache=1 && persist.vendor.ssr.restart_level=ALL_ENABLE`，以及 `persist.radio.write.cache=1`。其他 `reboot_on_failure` 项请求普通 reboot 或 bootloader；它们不能直接证明进入 PixelOS Recovery。C27 未保存上述属性值，也未保存 `sys.powerctl`，所以 Recovery 根因仍未确认。C28 在两条原始命令前分别写独立 marker，并增加 `sys.powerctl` 和 `on shutdown` marker；不会改变条件或重启命令。

C28 init RC 另对 post-fs-data、netd 与两个 Zygote 状态、bootanim/surfaceflinger、诊断服务、`sys.boot_completed=1` 写入彼此独立的文件。C27 删除的 netd→Zygote `onrestart` 回调继续保持移除；netd 的兼容性检查/失败行为没有改变。没有改动 ART、Zygote、GPU、HWC、Framework、SELinux CIL、fstab、加密、内核或硬件适配。

## K40 定点对照

已检查的 K40 成功包缓存中只有此前图形相关的部分 system 文件，没有 `system/etc/init/hw/init.rc`。本次没有为了读取一份 RC 展开整套成功包，因此不声称 K40 移植保留或删除了 `--bad_nv` 条件。C28 的变更是观测现有供体触发条件，不复制 K40 固件或设备专属文件。

## 构建与验证

C28 基于 C27 的 system tree 硬链接克隆；静态树差异 allowlist：`system/etc/init/hw/init.rc, system/etc/selinux/plat_file_contexts`，移除 C27 helper/RC 并加入 C28 helper/RC。C27 netd callback 状态、其余非系统 LP 输入及 boot/vendor_boot/dtbo/vbmeta 继承。最终 EROFS fsck、marker/策略路径 readback、helper 原始 ELF 字节一致性、system AVB hashtree、vbmeta_system descriptor 更新和 LP 布局验证见 BUILD_MANIFEST。

仅允许的刷写范围：`super`、`vbmeta_system_a`。构建器不访问设备。本报告不代表 C28 已经刷写或真机验证。

## 镜像 SHA-256

| 镜像 | 字节 | SHA-256 |
|---|---:|---|
| `boot.img` | 201326592 | `E5A016056D5C93C7A886980A7C062617EC44DC06A48417D7DD0F4476708A6368` |
| `vendor_boot.img` | 100663296 | `02333B82BA936F1BAAB1ECAB744632C70F8FC16688A206C7041EF319F112A137` |
| `dtbo.img` | 33554432 | `50E1AC0EDCBD333778217AA6FE8D972F6FF85ADD0DAE8A015A6642C2172DD886` |
| `vbmeta.img` | 131072 | `66A53C2EC38247193CC86B7F5DE887556864413D1142C3C1994645DE1E3BAB10` |
| `vbmeta_system.img` | 131072 | `BE82309DE7892151F3111E551E02BD90FB2F256C30A2803C1D77DAB692F00359` |
| `super.img` | 7703600088 | `6B292A91F71C0800255D694BE04C816715DEBC44ADEA8A8CE7B018CB695F24CF` |
