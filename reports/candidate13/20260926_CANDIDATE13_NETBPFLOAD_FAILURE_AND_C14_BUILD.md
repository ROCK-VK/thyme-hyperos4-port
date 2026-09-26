# THYME-OS4 Candidate 13 netbpfload 故障与 Candidate 14 准备

日期：2026-09-26

## 新取得的启动证据

本轮 Standalone 通过 RAM 临时启动，从设备的 THYME_DIAG 导出完整诊断目录。新建目录为 work/reports/20260925_CANDIDATE13_LOG_SALVAGE/run_20260926_122358/，没有覆盖更早的 pstore 证据。

- console-ramoops-0：218,184 字节，SHA-256 F504B4D0ED74842DEF0D2726C0286892A9D0D37A7EA42D1E07A73F1D59BD3E70。它包含一轮本次 C13 正常 Android 启动及约 25.924 秒处的暖重启。
- pmsg-ramoops-0：42,225 字节，SHA-256 006B672F9F9457ACAC1A7BA7ADC23B530F49871ADBC49BDD686DB4E547CBCE26。可见 vold/fscrypt 创建及安装 DE/CE 密钥的活动；原始 pmsg 可能包含密钥引用，保留在本地，不公开。
- oops.raw：16 MiB，与旧持久日志原始副本相同，不能归属本轮 C13；未把它作为本轮故障原因。
- dmesg_diag_boot.txt、diag_status.log 属于 Standalone 自身，不是 C13 内核日志。

console-ramoops-0 的关键相对时间线：

| 时间 | 证据 |
|---|---|
| 1.898 s | 正常 Android first-stage init 启动 |
| 1.983 s | 动态编译 SELinux 策略 |
| 2.978 s | Android second-stage init 启动 |
| 3.121–3.157 s | APEX bootstrap 扫描并激活 4 个 bootstrap APEX |
| 约 10.56 s | vold 将 /data 挂载为 F2FS |
| 约 10.7 s | vold 记录 Keymaster earlyBootEnded；pmsg 随后显示 fscrypt system、DE/CE 密钥创建/安装活动 |
| 约 15.96 s | NetBpfLoad 报告 Android 25Q2 要求内核 5.4 |
| 25.911 s | init 请求以 bpfloader-failed 重启 |
| 25.924 s | 内核记录正在强制 warm reset |

主机观察器显示 ADB 始终没有上线，故没有可用的实时 logcat。用户报告小米 Logo 常亮、黑屏后再亮并循环，随后手动进入 Fastboot。pstore 给出了与该屏幕现象相符的确定暖重启请求：netbpfload 失败后通过 init 发起 bpfloader-failed 重启。日志未显示本轮进入 Recovery。

### 结论边界

- 已证实：C13 进入 enforcing second stage、APEX bootstrap、vold /data F2FS 挂载及 fscrypt 初始化；随后发生明确的 bpfloader-failed 暖重启。
- 未证实：Keymaster/Gatekeeper HAL 是否持续健康、C13 两条 ion_device allow 是否消除了相关 AVC、用户凭据解锁是否完成、桌面是否可达。pmsg 中的密钥生成活动不能单独证明完整用户解密或日常可用。
- 本轮没有发现需要再次清除 userdata/metadata 的证据。

## Candidate 14 最小诊断修复

当前 C13 内核为 4.19.325；本轮真实 Android Connectivity NetBpfLoad 报错说明所搭配的 Android 25Q2 loader 要求内核至少 5.4。init 随后明确用 bpfloader-failed 请求重启。

K40 对照中相关 BPF init 触发配置与 C13 基本相同，没有发现可直接复制的 loader 绕过。此次不改变内核、SELinux Enforcing、APEX、fstab、userdata 加密或供体 HAL。

C14 以 C13 为基线，只修改两个 init 文件：

1. system/etc/init/netbpfload.rc 不再执行 bpfloader 或 netd1shot，设置 bpf.progs_loaded=1 并启动 netd，使 init 越过该 loader 的重启门控。
2. system_ext/etc/init/hyper_bpfloader.rc 移除 load-bpf-programs 触发的 hyper_bpfloader 启动。

诊断代价是本次启动不会加载这些供体 BPF 程序；网络相关功能可能缺失或不完整。此版本目的在于跨过已被日志证实的重启点，捕获下一启动阶段的实际结果，不代表 BPF 兼容性已修复。

C13 的 system_ext_sepolicy.cil 两条 ion_device allow、C13 的数据挂载配置及加密路径保持不变。C14 不清除 userdata/metadata。

## 构建与静态检查

本次从 C13 系统树在独立工作目录重建了 system、system_ext、vbmeta_system 与 sparse super；C13 的 boot.img、vendor_boot.img、dtbo.img、vbmeta.img 原样复制。原 C13 构建资产没有覆盖。

- fsck.erofs 检查两份新 EROFS 成功。
- 从最终 EROFS 回读确认两个 BPF init 触发段已按预期变化，C13 两条 ION SELinux 规则仍在。
- 新 vbmeta_system.img 含 product、system、system_ext hashtree 描述符；system 与 system_ext 描述符针对本次新 EROFS。
- super.img 具有 Android sparse v1 头；lpdump 检查动态分区元数据成功，包含本次 system/system_ext 及沿用的 product/vendor/odm/mi_ext 布局。
- 构建静态检查通过。没有执行刷写、启动、数据擦除或 PixelOS 恢复。

## 下一步设备操作准备

Candidate 14 六项镜像清单位于 work/stage_d_thyme_os4_candidate_14_bpf_bootstrap_bypass_run5/images/BUILD_MANIFEST.json。C14 写入脚本 tools/flash_candidate14_bpf_bootstrap_bypass.ps1 默认 Dry-Run，仅显式传入 -Execute 才会进行 Fastboot 写入。脚本只允许顺序写入以下两个目标，并检查设备序列、product=thyme、A 槽、Bootloader 解锁和 bootloader Fastboot 状态：

| 分区 | 文件大小 | SHA-256 |
|---|---:|---|
| vbmeta_system_a | 131,072 字节 | 5347D67BEADC9A0F8DCE49B3C76DA3F34E3E60805F3974ED895990724740D744 |
| super | 7,684,274,964 字节 | 112A0EB7FE6D13CD70848453528466219ADE18E3749D15F934854033E20B8093 |

脚本不包含 userdata/metadata 擦除、其他分区写入、解锁/回锁或重启。刷写仍需用户单独授权；刷完保持 Fastboot，首次启动还需另行明确授权。

本轮 Standalone 导出结束后，最新主机枚举未发现 ADB、Fastboot 或 THYME_DIAG 卷，因此当前设备物理模式尚未重新确认。PixelOS A0′ 没有在本轮恢复，也没有正常启动验证；不可称其当前在线或健康。
