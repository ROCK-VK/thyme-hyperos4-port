# Candidate 26 Zygote 首因诊断构建

C26 保留 C25 的持久状态采样，并加入连续限额 logcat 与 Zygote 生命周期采集。当前没有证据支持替换 K40 的 Zygote/ART 文件：本次定点比较中的启动 rc、app_process、ART/runtime APEX 和 classpath 均与供体逐字节一致。因此 C26 不改系统启动行为，只提升获取退出首因的能力。

新增采集包括：所有 logd buffer 的 1 MiB × 4 文件滚动、Bionic property-wait 状态变化、zygote 进程 cmdline/status、首次至多 8 次重启时的 crash/system/main logcat tail。新增文件继续使用 C25 的 shell domain 和 metadata 诊断目录访问策略，没有扩展 CIL 权限。

刷写范围：`super`、`vbmeta_system_a`。C25 的 boot、vendor_boot、dtbo、vbmeta_a 与数据状态保持。构建清单记录六项镜像大小/SHA-256；本报告不包含 ROM 或分区镜像。
