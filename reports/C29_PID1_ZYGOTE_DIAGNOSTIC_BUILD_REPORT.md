# Candidate 29 PID1/Zygote 有序故障诊断构建报告

## 决策

C28 的根本 fatal signal、init LOG(FATAL) 和 PID 1063 身份仍不可见。五个 `main` SIGABRT 与 primary Zygote 的 critical 配置相符，但没有 PID/服务映射、restart 顺序或可见的 critical-process fatal 记录；`zygote_secondary` 的状态 marker 无时间戳。故离线证据尚不足以关闭 critical 或切断 secondary→primary 回调。C29 是诊断版，不是已证明的系统修复。

## C29 改动

C29 继承 C28，netd→Zygote 两条回调继续保持移除。仅替换系统诊断 RC/helper：在 post-fs-data 启动有序采样与日志器，按 `CLOCK_BOOTTIME`、内核 boot ID、event/service/PID 追加并 fdatasync；每 10 ms 采样 netd、两个 Zygote、`sys.boot_completed`、`sys.powerctl`，并扫描 system_server 首次 PID。init `write` marker 作为第二通道。logcat 沿用 C26 直接 `-f` 路线，单文件、最多 60 秒/8 MiB、无 rotation，并持久记录 helper/child/exec/wait 结果。

未修改 Zygote `critical`、secondary `onrestart`、netd 逻辑、SELinux CIL、GPU/HWC、Framework、内核、fstab 或数据加密。

## 构建和最终镜像

构建器仅在 C/D/E 均不低于 50 GiB 时启动；本次门禁记录 `{'C_free_gib': 75.28, 'D_free_gib': 206.2, 'E_free_gib': 248.82}`。C28 非系统逻辑分区输入与 C29 LP 输入逐项哈希相同。刷写范围仅为 `super`、`vbmeta_system_a`。

| 镜像 | 字节 | SHA-256 |
|---|---:|---|
| `boot.img` | 201326592 | `E5A016056D5C93C7A886980A7C062617EC44DC06A48417D7DD0F4476708A6368` |
| `vendor_boot.img` | 100663296 | `02333B82BA936F1BAAB1ECAB744632C70F8FC16688A206C7041EF319F112A137` |
| `dtbo.img` | 33554432 | `50E1AC0EDCBD333778217AA6FE8D972F6FF85ADD0DAE8A015A6642C2172DD886` |
| `vbmeta.img` | 131072 | `66A53C2EC38247193CC86B7F5DE887556864413D1142C3C1994645DE1E3BAB10` |
| `vbmeta_system.img` | 131072 | `A03AFBEDF1A60DDCBC3D0A1F9A391782876F15323F397F108CB8637CEA142A40` |
| `super.img` | 7703587800 | `A67994F75146E87EB74F772A2BEAF7547BFCC4B31C80C94003239FE6E47BB09D` |

构建器完成 helper AArch64 PIE/依赖检查、system EROFS fsck/readback、helper 字节级 readback、system AVB hashtree/vbmeta_system descriptor 与 LP 布局验证。此为主机验证，不代表 C29 已刷写或已启动。
