# THYME-OS4｜K40 / Milo 作者改动集合与 C30 阻塞点交叉核验

日期：2026-09-30 21:57 HKT
范围：复用已有 C30、Xiaomi 15 donor、K40 system 和 Milo system 缓存；定点核对启动配置、属性、runtime、平台 SELinux 及 C30 原始启动证据。未启动 C30、未刷写、未切槽、未擦除、未恢复 PixelOS、未构建 C31。

## 结论

**本轮没有找到同时满足“有 K40/Milo 交叉支持”且“能解释 C30 已知阻塞”的系统修改，因此 C31 候选集合为 0 项。**

高优先级交集在已检查的 Android 17 system 范围内没有发现共同的 init、Zygote、ART、netd/BPF、linker、VINTF 或平台 SELinux workaround。唯一共同的有效配置差异是：K40 system 未设置、Milo system 将七项 Tango/pretrans 属性注释掉，而 Xiaomi 15 donor 与 C30 保持启用。没有在本轮可读取的 C30 system / system_ext / product / vendor 配置、限定 runtime 二进制和 C30 pmsg 中找到这些属性的消费者；其含义和启动因果未确认，也没有证据将它们映射到 C30 的 PID1 panic、Zygote 重启、netd SIGABRT 或诊断写入失败。因此它是一个**已确认的共同配置状态差异**，不是可采纳的 C31 修复。

C30 原始 console 还显示 Zygote 域在启动约 15.86–16.18 秒读取五种 vendor property context 时出现七条 SELinux read AVC。这是真实的新线索，但日志没有把它们与 Zygote 退出、init fatal 或 32.922 秒 PID1 sysrq panic 建立因果关系。K40 完整 vendor policy 不在现有缓存中，本轮不推断它已解决这些 AVC。

## 改动集合

集合以 Xiaomi 15 donor 为比较基线。不同 build 的哈希差异先按配置/代码语义区分，不把版本变化直接当成移植补丁。

### Init、critical、Zygote、netd

- **K40 − donor：**在已核对的 87 个 init 路径中，除两个经 EROFS 直接确认目标一致的 BoringSSL 符号链接外，实际差异为 system/etc/init/hw/init.rc 与 system/etc/init/hw/init.usb.rc。
- K40 init.rc 新增 /data/system/theme 权限处理、由 persist.sys.adb.start 控制的可选 TCP ADB、受 sys.dex2oat.enable 触发的 baiyang_dex2oatd，以及 boot_completed 后的充电/CPU 频率调节。它没有改变 Zygote critical、fatal target、netd 回调或 BPF 路径。这些内容不解释当前早期 PID1 panic。
- K40 init.usb.rc 在 init 阶段将 sys.usb.configfs 设为 0；该文件后续动作会再由硬件配置覆盖。它可能影响 USB 配置时序，但没有证据说明它修复 C30 的启动 fatal。
- **Milo − donor：**直接从 Milo EROFS 读取 BoringSSL symlink payload 后，未发现实际 init 行为差异。netd.rc、netbpfload.rc、surfaceflinger.rc 和两份 init.zygote 文件与 donor 一致。
- **C30 − donor：**匹配 init 集合中的六项实际差异为 C25/C30 诊断 rc、hw/init.rc 诊断导入/marker、netd.rc、netbpfload.rc 和 surfaceflinger.rc。前两项为 C30 诊断；netbpfload 绕过是既有 BPF 修复；netd 删除两条 Zygote restart 回调是 C30 已有改动；ANGLE trigger 是较早图形实验配置。
- **交集 4：**没有 K40 和 Milo 共同修改、而 C30 缺失的 init / critical / Zygote / netd 行为修改。init.zygote64.rc、init.zygote64_32.rc 及可读的 BoringSSL 目标均相同；被检查的 build.prop / rc 中没有 init.svc_debug.no_fatal.zygote 或额外关闭 Zygote critical 的配置。
- 既有 init manifest 将两个 EROFS symlink 记成 Windows reparse/零字节，不能据此算作移植差异。本轮直接从 donor、K40、Milo EROFS 读取两个链接目标，并与 C30 readlink 结果比对；四方目标相同。详见 BORINGSSL_SYMLINK_READBACK.csv。

### System 属性、Framework 与 Runtime

- Milo 的 system/build.prop 明确将 tango.enabled、tango.debug、tango.pretrans.max_size、tango.pretrans_on_install、tango.pretrans.debug、tango.pretrans.lib、tango.pretrans.apk 注释掉。
- K40 的 system/build.prop 与已缓存 product build.prop 均没有这些活动项。donor 与 C30 system/build.prop 则分别设置 1 / off / 67108864 / true / off / true / true。
- Tango 属性名显示其与 pretrans、install、APK/lib 处理相关，但实际 consumer、默认值及启动时序未在当前缓存中确认。精确字符串搜索未在 C30 的 plat_property_contexts、所检查 init 配置、system/bin、system/lib64、framework、APEX、system_ext、product、vendor 路径及 C30 pmsg 中找到消费者。此结果不排除未缓存的 OEM 组件或动态访问。
- K40 services.jar 含 Baiyang Dexopt 专有实现，并由 K40 init.rc 中显式 property trigger 启动；Milo 没有同一实现。它是 K40 单边、可选的设备/构建功能，不是交集修改。
- Milo 的 services.jar、framework-res.apk、libandroid_runtime.so 与 2026-09-02 donor/C30 有字节差异，但 Milo 是较新的 generic missi Android 17 build。libandroid_runtime.so 仅小 64 字节，SONAME 与 106 项 DT_NEEDED 依赖集合相同；本轮未发现与 Linux 4.19、Zygote fatal 或 PID1 panic 对应的具体行为修复。不能将版本差异作为 C31 移植理由。
- 已比较的 ART/runtime APEX、app_process、boot/system-server classpath、linker config、VINTF manifest/matrix 未出现支持旧 thyme vendor 的 K40+Milo 共同适配。

### SELinux 范围

- 已有四方对照只覆盖 system plat_sepolicy.cil 中与指定启动域相关的规则集合：Milo 与 donor 相同，Milo 没有 C30 未有的启动规则；K40 相对 Milo 多出的规则是 shell 对 system_prop 的读/设置授权，不对应本轮 Zygote vendor property AVC。
- C30 多出的限定规则为诊断域/marker；没有据此新增任何 Zygote 宽泛授权。
- 现有 K40 缓存不含完整 K40 vendor SELinux policy；Milo 本轮也只读取了 system_a。故本报告不声称四方 merged/vendor policy 完全相同，也不排除 K40 vendor policy 存在设备侧规则。

## Candidate 与 blocker 对照

证据等级按本轮用户定义。B 表示两套参考样本共同呈现同一配置状态，不代表该状态已证明能修复启动。

| Candidate / 参考 | 文件 | K40 状态 | Milo 状态 | C30 状态 | 可能作用与 blocker 映射 | 等级与决定 |
|---|---|---|---|---|---|---|
| Tango/pretrans 属性状态 | system/build.prop，七项 tango.* | 未设置（system 与已缓存 product） | 七项均为注释行 | 与 donor 一样启用 | 可能影响 pretrans/install 的 APK/lib 处理；consumer 未定位，不能解释 A PID1 panic、B Zygote restart、C netd SIGABRT 或 D 诊断写失败 | B（仅交叉确认配置状态）；不进入 C31 |
| K40 init 可选配置 | system/etc/init/hw/init.rc | 添加 theme chmod、可选 TCP ADB、Baiyang dex2oat、boot_completed 后调节 | 与 donor 相同 | C30 有自己的诊断及既有修复 | 部分影响后期性能/USB/主题；没有证据映射至 A–D | C；设备专用，不移植 |
| K40 USB 初始化 | system/etc/init/hw/init.usb.rc | init 时设 sys.usb.configfs=0，后续硬件配置覆盖 | 与 donor 相同 | 与 donor 相同 | 可能改变 USB 枚举/ADB 时序，不解释内核 panic，也未证明解决 C30 helper metadata 写入 | C；不作为启动修复 |
| K40 可选 Dexopt | system/framework/services.jar 与 K40 init.rc | 有 Baiyang Dexopt 类和显式启动 trigger | 无相同改动 | 使用 donor services.jar | 可选应用优化功能；不属于当前早期启动链 | C；排除 |
| Milo 新版 Framework/资源 | services.jar、framework-res.apk、libandroid_runtime.so | 核心对应文件多数与 donor 相同；services.jar 是另一构建 | 字节不同但属于更新 build；未找到与当前 blocker 对应的行为差异 | services.jar/framework-res/libandroid_runtime 与 donor 相同 | 可能含未解析版本变化；没有可定位的 A–D 兼容修复 | D；不移植 |
| C30 已验证 BPF 绕过 | system/etc/init/netbpfload.rc | donor stock 路径 | donor stock 路径 | C14 bypass，设置 bpf.progs_loaded 后启动 netd | C14 实机已证明越过早期 BPF loader 门槛；与当前 libnetd_updatable SIGABRT 的根因不同 | A（历史修复）；保留，不回退 |
| C30 netd/Zygote 回调实验 | system/etc/init/netd.rc | donor stock，保留两条回调 | donor stock，保留两条回调 | 删除 netd restart zygote / zygote_secondary | 设计上切断一条潜在重启边，但 C29/C30 没有有序事件证明它是 B 的根因，也不能解释 A | D；不作进一步无证据扩大 |
| C30 Zygote vendor-property AVC | C30 console-ramoops-0 | 现有 K40 plat 规则未见对应授权；vendor policy 未缓存 | Milo plat 规则与 donor 相同；其 vendor policy 未在本轮提取 | 15.864–16.180 秒有七条 zygote:s0 对 vendor_displayfeature_prop、vendor_system_prop、vendor_display_prop、vendor_fingerprint_prop、vendor_default_prop 的 read denial | 是真实访问拒绝，可能影响属性读取；未发现紧邻的 Zygote fatal/退出因果，不能由 AVC 本身推断 PID1 panic 根因 | D（事件直接、因果未知）；列为下一项定点取证，不加宽 allow |

## C30 当前故障闭环程度

- **A｜PID1 fatal/panic：**console-ramoops 明确记录 init PID1 在约 32.922 秒经 write_sysrq_trigger 主动触发 sysrq crash。上游 init fatal 条件仍未知；参考包没有可移植的 critical/no_fatal 修改。
- **B｜Zygote restart：**C30 console 有上述七条早期 property AVC；C29 metadata 只显示 running/restarting 状态，缺少顺序；C30 ordered-events 文件为空。无法证明 AVC、netd restart 与 Zygote 退出的顺序或因果。
- **C｜netd：**C30 pmsg 有多次 netd SIGABRT，回溯进入 libnetd_updatable_init。Milo/K40 的 stock netd/BPF 配置未提供 4.19 workaround；C30 已有 BPF 绕过，但 netd 后续崩溃仍存在。
- **D｜诊断写入：**C30 helper 文件为空或零字节，未得到 canary/events/logcat 状态；K40 的 USB init 修改不构成 metadata 写入证据。Standalone 原始取证可用，但不能还原未持久化的 helper 事件顺序。

## 决策与下一步

1. **不构建 C31。**当前唯一 K40+Milo 共同配置差异没有映射到任何已证实启动 blocker；其他 K40 差异是单边设备功能，Milo Framework 差异主要是 build/version 字节变化。
2. 不修改 Tango 属性，不恢复 stock netd/BPF 文件，不增加 Zygote/vendor property 宽泛 SELinux allow，不关闭 critical。
3. 下一项最高收益工作是离线定点追踪 C30 的 Zygote vendor-property AVC：在取得对应实际 vendor policy/属性上下文时，确认具体属性键及允许读取的域；并继续从已有 console/pmsg 定位 32.922 秒前 init fatal 条件。仍需将访问拒绝与退出因果分开。
4. K40 vendor policy 和 Milo system_ext/vendor policy不在本轮可读缓存内；如果后续证据表明该 policy 差异会决定 Zygote 是否继续启动，再针对必要的单个逻辑分区/文件提取，不展开完整 super。
5. 本轮没有操作设备、启动 C30、修改 Candidate 或构建 C31。Milo 继续不作为可刷写 External Candidate。

## 证据文件

- 四方 init、runtime/VINTF/linker 清单和限定 plat SELinux 差异：work/third_party_milo_c30_fourway_20260930/
- C30 首启报告和 pstore 副本：work/reports/candidate30_first_boot_20260930/
- 本轮系统属性/候选矩阵：AUTHOR_CHANGE_SET_MATRIX.csv
- BoringSSL symlink 的 EROFS 直接读回：BORINGSSL_SYMLINK_READBACK.csv
- 四方文件范围和 hash 是静态主机证据；C30 启动事实只引用本地已保存原始 pstore/pmsg。未对设备执行新实验。

## 本轮临时空间清理

分析完成后删除了三个可重建且不再作为依赖的单文件中间产物：Milo unsparse 临时 super（9,126,805,504 B）、Milo 单独提取的 system_a（978,804,736 B）及 K40 临时 services.jar（40,160,958 B），合计 10,145,771,198 B（约 9.45 GiB）。删除前已确认限定工具/报告中无路径引用、无相关提取进程；Milo 原始 images/super.img、Milo 选定 system 缓存和 K40 system_a 缓存仍保留。本轮未接触 Docker 或设备。
