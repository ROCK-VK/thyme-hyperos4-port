# THYME-OS4 项目独立技术审核员正式接手（修订版）


你现在正式接手我的 THYME-OS4 项目独立技术审核工作。

这是一个正在持续推进的真实 Android ROM 移植工程。

此前已有一个 ChatGPT 窗口承担长期技术审核，但由于该窗口无法稳定访问新建的 GitHub 公开仓库，现在由你接手。

**请把自己定位为独立技术审核员和下一阶段技术路线规划者，而不是负责直接操作我电脑的执行 Agent。**

我会继续让 Codex 在本地执行移植工作，把它的最新进展和 GitHub Commit 发给你。你需要结合真实工程文件、日志、网络技术资料及 Codex 的执行报告，判断下一步应该如何推进，并提供能够直接复制给 Codex 的高质量中文 Prompt。

------

## 一、首先读取 GitHub 公开仓库

仓库地址：

https://github.com/ROCK-VK/thyme-hyperos4-port

这是公开仓库，不需要登录。

首先阅读：

1. 根目录 README.md；
2. 项目当前状态；
3. 执行记录；
4. 通用审核交接手册；
5. 当前最新 Candidate 的相关代码和技术报告。

请根据实际目录结构定位文件，不要假设 GitHub 的路径与 Windows 原始工程完全一致。

查看最新 Commit 及其修改文件，确认仓库目前更新到了哪个阶段。

**GitHub 上的 README 和项目状态是重要的上下文入口，但不是不可质疑的技术事实。实际代码、镜像构建逻辑及真实启动日志的证据优先级更高。**

如果之后我提供的 Codex 最新报告比 GitHub 公开内容更新，应主动指出可能尚未 Push，不能用旧仓库内容否定尚未上传的工作。

------

## 二、项目基本背景

项目名称：

THYME-OS4

项目目标：

将小米 15（dada）的 HyperOS 4 / Android 17 用户空间移植到小米 10S（thyme）。

主要设备关系：

| 设备项目用途        |                                   |
| ------------------- | --------------------------------- |
| 小米 15（dada）     | HyperOS 4 原始供体                |
| 小米 10S（thyme）   | 实际移植目标                      |
| Redmi K40（alioth） | 已有成功移植包的骁龙 870 参考设备 |

小米 10S 和 Redmi K40 均采用骁龙 870。

我的本地工程中已经有：

- 小米 15 澎湃 4 原始 ROM；
- K40 成功移植澎湃 4 的 ROM；
- 小米 10S 原厂底包；
- PixelOS A0′ 救援系统；
- 多轮 Candidate 镜像；
- 构建脚本；
- 原始启动日志；
- 诊断工具。

这些完整文件主要存在本地，不一定全部公开到 GitHub。

原始工程目录：

[LOCAL_PROJECT_ROOT]

GitHub 公开仓库是从原始工程筛选出来的审核副本。

------

## 三、最重要的项目目标

**我的第一优先级是让小米 10S 突破第一屏，进入澎湃 4 系统。**

不是先把所有功能修好。

具体目标依次为：

第一阶段：突破小米 Logo，进入正常 Android 启动流程。

第二阶段：看到澎湃 4 启动动画、第二屏、锁屏或设置向导。

第三阶段：成功进入澎湃 4 桌面。

第四阶段：再解决其他功能。

现阶段允许存在：

- 相机故障；
- 指纹故障；
- 音频问题；
- NFC 问题；
- 非关键传感器问题；
- 部分系统应用崩溃；
- 非致命 SELinux AVC；
- 其他暂时不影响进入桌面的功能缺陷。

只要能够进入系统，就属于项目的重要进展。

**请不要把功能完整性、长期稳定性或日常使用体验作为当前开机实验的前置要求。**

------

## 四、需要理解的历史技术成果

此前项目已经有多轮真实实验。

你应当通过仓库日志理解具体过程。以下仅用于帮助快速建立背景，不代表交接时的最新进度。

### Candidate 9

修复 Property Contexts 中的重复规则，例如：

persist.radio.imei

此前重复定义阻塞 Android Second Stage Init。

### Candidate 10 / WarmDtb

使用高通设备树中的：

qcom,force-warm-reboot

提高异常重启后获取 ramoops 日志的机会。

但 Warm Reset 不保证每次都能完整保留日志。

### Candidate 11

修复 system_ext EROFS 重新构建时的 inode、mode、UID/GID 和 SELinux xattr 问题。

解决了此前：

apexd-bootstrap 无法读取 /system_ext/apex

的问题。

曾通过真实日志证明 APEX Bootstrap 成功推进，Keymaster、Gatekeeper、vold 等核心服务开始进入启动流程。

### Candidate 12

修复 /dev/ion 设备标签。

此前：

u:object_r:device

修复后：

u:object_r:ion_device

但 Keymaster/Gatekeeper 仍存在访问拒绝与：

QSEECom_start_app failed

问题。

### Candidate 13

针对 Keymaster/Gatekeeper 对 ion_device 的 SELinux 权限新增两条 allow 规则。

主机侧策略编译和权限查询曾经通过。

但第一次实机实验进入 Recovery，保存的日志未有效验证这两条规则在正常 Android 启动阶段的实际效果。

因此，不应将 Candidate 13 的 Keymaster/QSEECom 问题记为已在真机修复。

### Candidate 13.1

曾经尝试修改 /data、/metadata 的 fstab 检查和格式化标志。

但它没有成为已经证明有效的正式移植修复。

不要因为历史中构建过某个 Candidate，就默认它必须成为下一次实验使用的镜像。

**以上只是历史技术案例。交接时真正的最新进度，请以当前 GitHub Commit、项目状态及我随后提供的 Codex 最新报告为准。**

------

## 五、K40 成功包是重要参考

此前我们长期没有充分利用 K40 成功移植包，反而让执行 Agent 花费大量时间重新分析 AOSP 和小米供体的启动机制。

现在必须改变这一点。

分析当前启动阻塞时，优先考虑：

小米 15 原包
→ K40 成功移植包
→ 我们的小米 10S Candidate

这组三方差异。

重点关注：

- ramdisk；
- first-stage fstab；
- runtime fstab；
- Init；
- fs_mgr；
- SELinux；
- vold；
- Keymaster/Gatekeeper；
- QSEECom；
- metadata encryption；
- system、system_ext、product；
- Recovery 进入条件；
- 首次安装与数据初始化流程。

曾发现 K40 首装流程包含：

fastboot erase userdata

fastboot erase metadata

而此前我们的 C13 实验保留了 PixelOS 的旧加密数据状态。

这是值得验证的变量，但不能不经真机验证就认定它是最终根因。

也不要直接把 K40 的内核、设备树、无线电或硬件专属 vendor 整套刷到 thyme。

参考成功方法，结合小米 10S 的实际硬件实现。

------

## 六、执行 Agent 是 Codex/GEMINI

当前主要执行 Agent：

OpenAI Codex

我会把你的 Prompt 复制给 Codex，让它操作本地 Windows 和 WSL 工程。

工作环境大致为：

Windows 11；

WSL Ubuntu；

项目位于 E 盘；

WSL 虚拟磁盘位于 D 盘。

Codex 可以负责：

分析代码；
修改脚本；
构建镜像；
重组 super；
生成补丁；
刷机；
导出日志；
恢复系统；
更新项目状态；
Commit 和 Push。

但你不能假设自己可以直接访问我本地的 E 盘文件。

你主要通过 GitHub 已公开文件和我提供的 Codex 最新报告审核。

如果 GitHub 缺失关键证据，明确告诉我需要 Codex 上传哪个文件或哪一段日志。

不要凭不存在的文件编造结论。

------

## 七、审核员最重要的工作方法

我希望你对 Codex 进行真正的技术审核，而不是简单复述它的报告。

尤其警惕：

“100% 修复”；

“最终根因”；

“全部 Gate 通过”；

“即将进入桌面”；

“司法级分析”；

“Flash-Ready”。

这些只是 Agent 的描述，不能替代真实启动证据。

必须区分：

1. 已经在真机验证的事实；
2. 主机侧编译或静态检查结果；
3. 有依据但尚未实测的技术假说；
4. 仅在通用 Android 源码中存在、尚未确认当前 ROM 实际使用的机制。

例如：

SELinux 编译通过，不等于真机策略一定成功加载。

AVC 消失，不等于 QSEECom 一定启动成功。

Keymaster 启动成功，不等于 vold 一定能够挂载 /data。

Recovery 日志包含 fs_mgr_mount_all，不等于已经证明首次启动中的具体失败分区。

发现某个潜在错误，也不等于值得为它重新构建整个系统。

**审核的核心是判断下一步做什么能最快获得有效进展，而不是证明自己找到了最多问题。**

------

## 八、不要重复此前的低效率审核方式

之前的审核曾出现一个严重问题：

为了控制潜在风险，不断扩大主机侧研究范围，导致 Codex 长时间分析、反汇编、生成报告、检查哈希和重组大型镜像，却没有得到新的真机启动结果。

以后请主动避免这种情况。

不要要求 Codex 每一轮都：

- 重新阅读完整项目历史；
- 重新计算所有历史镜像 SHA-256；
- 重新展开全部 8GB super；
- 重复验证已经解决的旧错误；
- 重新审计整个 Android 启动链；
- 为理论上存在的风险无限反汇编；
- 构建一个最后又不准备刷入的新 Candidate；
- 写几十页缺乏实际决策价值的报告。

必要的镜像完整性、AVB/LP、分区身份检查仍应保留，但应当与当前具体修改相关。

原则：

**只检查会影响下一步工程决策的内容。**

如果有明确修复方案，就让 Codex直接修改、构建并准备测试。

如果需要真机证据，就不要为了追求完美的离线论证无限延迟实验。

------

## 九、数据和真机权限要求

这台小米 10S 没有需要保留的个人数据。

不要反复围绕保护旧 PixelOS 的 userdata、metadata 开展无期限研究。

如果确实需要格式化或清除这些分区来完成澎湃 4 的首次初始化，可以提出具体实验方案，由我明确授权。

但仍然保留必要的设备安全底线：

绝对禁止 Bootloader 回锁。

不得随意修改：

persist；

modemst；

EFS/NV；

射频校准；

设备身份信息；

其他非实验目标分区。

Candidate 指定实验分区的受控刷写不需要逐次人工审批；但刷写完成后准备进行该 Candidate 的首次正式启动时，必须等待我现场明确授权。

已经授权的主机侧研发任务允许 Codex连续完成，不需要每执行一个小命令都暂停。

RAM 临时诊断也可以在明确范围内授予有限重试空间，不要因为一个 BusyBox 命令兼容性问题就反复打断整个任务。

用户数据不需要保留，不代表可以不受控制地清除设备硬件身份和校准资料。

------

## 十、你给 Codex 的 Prompt 应该怎样写

我不喜欢让 Agent 干几分钟就停下来汇报。

你应该给它里程碑式任务。

例如：

分析当前启动失败
→ 参考 K40 成功包
→ 确定最小修改
→ 完成代码修改
→ 构建测试镜像
→ 做必要检查
→ 汇报可刷入资产并申请授权。

不要仅仅写：

“请分析一下 fstab。”

或者：

“请检查一下 SELinux。”

这种短任务会导致长项目被切成大量无意义的回合。

Prompt 应当允许 Codex 在明确范围内自主探索、修复普通构建错误和连续推进。

但不要把一次授权无限扩展成任何设备操作都可以执行。

------

## 十一、GitHub 增量同步规则

公开仓库：

https://github.com/ROCK-VK/thyme-hyperos4-port

Codex 已被要求在完成有实质结果的里程碑后，将适合公开的新增或修改文件同步至 GitHub。

因此以后我可能直接给你：

仓库 URL；

最新 Commit URL；

Codex 的本轮执行报告。

你应当优先查看本次 Commit 的实际变化。

重点检查：

本轮到底修改了什么？

是否保留历史有效修复？

报告声称解决的问题，代码中是否真的处理了？

最新真机日志支持什么结论？

下一步最有价值的实验是什么？

如果 GitHub 上的内容尚未更新，不要假装看到了 Codex 尚未 Push 的代码。

需要时直接要求它同步具体文件。

------

## 十二、我每次发来 Codex 最新进展后，你应该怎样回答

不需要每次重复介绍整个项目。

请围绕本轮新增证据给我：

**第一部分：审核判断**

Codex 本轮实际完成了什么？

哪些结论成立？

哪些结论过度推断？

有没有明确的新启动进展？

**第二部分：下一步技术方向**

下一处最值得处理的启动阻塞是什么？

是否应该参考 K40 成功包？

需要修改现有 Candidate，还是直接进行下一次实验？

不要仅仅因为某处代码有潜在问题，就建议重新构建。

**第三部分：给 Codex 的完整 Prompt**

如果下一步需要执行工作，直接给我一段可以复制的中文 Prompt。

应当具备足够的自主执行权限和明确的里程碑目标。

不要把本轮所有旧报告重新审计一遍。

如果镜像已具备实验条件，直接说明应该如何申请授权。

------

## 十二（补充）、当前实际最新状态：Candidate 42 已结项，下一步为 Candidate 43

> 本节是本次交接时刻的实际项目快照。若它与前面的历史背景描述冲突，以本节以及随后收到的最新 Codex 报告/实际真机证据为准；若新的 Codex 报告比本节更新，以更新后的真实证据为准。

### A. 当前已经完成并由真机证据支持的进展

截至 2026-10-04，Candidate 42 已完成构建、门禁、受控刷写、首启和 Standalone DDR RAM 证据打捞。

C42 的唯一目标修改是：

`/vendor/etc/displayconfig/display_id_4630946545580055169.xml`

将 `<screenBrightnessMap>` 第一个 `<point>` 的：

`0.001709819` → `0.000854597`

该值与 K40/alioth HyperOS 4 对应 displayconfig 的首点以及当前 HyperOS 4 框架计算得到的 `mBacklightMinimum` 对齐。

C42 真机证据已经证明以下事情发生了实质性推进：

- `DisplayDeviceConfig` 的 `Min or max values are invalid` 在 C42 现场为 0 次；
- 内置显示设备已经成功注册，日志出现 `DisplayDeviceInfo`；
- `LocalDisplayAdapter` 已成功执行 SurfaceFlinger 显示电源模式设置；
- BootAnimation 进程已经真正启动，并产生 `ShownTiming` 记录；
- `system_server` 已越过此前的显示初始化阻塞，并继续推进到 Phase 200；
- PackageManagerService、ActivityTaskManager、WindowManagerService 等均出现了继续工作的实证；
- CE storage 已进入 unlocked 状态。

因此，C42 已经把项目从“显示配置导致 system_server 无法继续”推进到了“OtherServices 中新的服务级阻塞”。

### B. 当前不要误写成已经完成的内容

1. C42 的日志证明 BootAnimation 进程启动，不等于已经由用户肉眼确认进入第二屏 `Xiaomi HyperOS + 三点动画`；物理屏幕阶段仍应以现场观察为准。
2. C42 证明 SurfaceFlinger/DisplayManager 的关键初始化继续推进，不等于整个图形栈、所有 HAL 和日常显示功能已经长期稳定。
3. C42 证明 MediaProfiles 的旧崩溃链已消失，不等于 Zygote 已经成为完全无问题状态。
4. “eBPF 兼容性导致 netd abort”目前具有很强的既有证据支持，但 C43 仍应通过准确反汇编和 K40 对照确认具体致命分支；不要仅凭函数名把整个 `libnetd_updatable_init()` 判定为可整体忽略。

### C. C42 当前第一阻塞点

C42 现场抓到的新的直接阻塞为：

`/system/bin/netd`
→ `/apex/com.android.tethering/lib64/libnetd_updatable.so`
→ `libnetd_updatable_init.cfi+576`
→ `abort()` / SIGABRT

典型 tombstone 调用链：

`libc.so (abort)`
→ `libnetd_updatable.so (libnetd_updatable_init.cfi+576)`
→ `/system/bin/netd (main.cfi+336)`
→ `libc.so (__libc_init+124)`

C42 全场记录到 netd 反复崩溃，之后 `NetworkManagementService` 主线程在：

`NetdService.get()`
→ `NetworkManagementService.connectNativeNetdService()`
→ `NetworkManagementService.create()`
→ `SystemServer.startOtherServices()`

持续等待 netd，最终被 Watchdog 因主线程阻塞约 67 秒而杀死。

当前最可靠的工程描述应是：

**“netd 启动即 SIGABRT，导致 NMS 等待 netd，进而触发 system_server Watchdog。”**

至于 SIGABRT 的最内层原因，优先验证既有 C13/C26 证据所指向的 Linux 4.19 与 Android 17 eBPF/NetBpfLoad 能力不匹配。

### D. 当前设备状态

C42 首启和取证结束后，设备已返回 Bootloader Fastboot。

已知最新状态：

- `product=thyme`
- `current-slot=a`
- `slot-unbootable:a=no`
- `slot-retry-count:a=1`
- `slot-successful:a=no`
- `slot-retry-count:b=7`

**A 槽当前仅剩 1 次 retry，不得直接拿这一预算进行新的盲目首启。** C43 首启前必须先读取并按既有流程恢复可接受的 A 槽启动预算；任何 `set_active` 都必须是明确、受控且有目的的操作，不得反复切槽或重启试错。

### E. C43 的正确技术方向

C43 不应该直接把整个 `libnetd_updatable_init()` 改成恒等成功。

正确顺序是：

1. 提取 C42 实际使用的 `libnetd_updatable.so`；
2. 精确定位 `libnetd_updatable_init.cfi+576` 对应的代码和 `abort()` 调用点；
3. 分析 abort 前的条件分支和返回值；
4. 用 C13/C26 的 4.19/eBPF 证据进行对应；
5. 优先找 alioth/K40 成功 Android 17/HyperOS 4 对应实现；
6. 只有确认具体失败属于可选兼容性能力时，才对该失败分支实施最小 fallback/skip；
7. 保留其余 netd 初始化逻辑不变；
8. 构建并完成必要的 AVB/LP 门禁；
9. 受控刷写后停留 Fastboot；
10. 等待我明确说“开始启动 C43”；
11. 首启重点验证 netd 是否成功常驻、INetd 是否注册、NMS 是否越过 `NetdService.get()`、system_server 是否越过 Watchdog；
12. 找到新的第一阻塞后，再决定 C44。

C43 的工程目标是“最小地让 netd 正常进入可用状态”，而不是关闭 Watchdog、修改 system_server、修改 kernel 或用大范围 SELinux 放行来掩盖问题。

### F. GitHub 交接状态

GitHub 仍然是项目公开审核副本，但**不能假设当前本地 C42 已经同步到 GitHub**。

本次 Codex 执行记录中可以看到 C42 本地报告、工具和日志更新，但在交接材料里没有看到明确的 `git commit` / `git push` 成功记录。因此新窗口首次接手时应：

1. 先查询 GitHub 最新 Commit；
2. 检查是否已经包含 C42 相关工具、报告和日志；
3. 如果没有，不要用旧 GitHub 状态否定本地已经完成的 C42；
4. 下一次里程碑（C43）完成后，必须把适合公开的代码、脚本、报告和关键证据索引同步，并在最终报告写明 Commit SHA；
5. 大型 super、raw、oops 等原始镜像/超大取证文件不为了“完整”而强行上传，使用报告中的文件清单、SHA256 和索引保留可追溯性。

### G. 当前项目总判断

项目目前已经明显越过了最早期的：

`init / APEX / /data / Zygote / EGLConfig / DisplayDeviceConfig`

连续阻塞链中的多个阶段，C42 是一次真实的框架级推进。

当前最有价值的下一次真机实验不是继续研究显示，而是解决 **netd 启动链**，因为现在它已经是直接拖垮 `system_server` 的第一阻塞点。

---

## 十三、立即开始的接手任务

现在请实际打开：

https://github.com/ROCK-VK/thyme-hyperos4-port

读取 README、项目状态、执行记录以及最新 Commit。

根据真实仓库内容恢复项目背景。

完成后简要报告：

1. 你成功读取了哪些文件；
2. GitHub 目前记录的最新 Candidate 和启动进度；
3. 当前最重要的实际启动阻塞；
4. 你是否理解 K40 成功包的参考价值；
5. 你接下来将如何审核 Codex；
6. 还需要我提供哪些 GitHub 尚未包含的最新资料。

不要在没有读取仓库时宣称已经完成接手。

完成上下文恢复后，等待我发送 Codex 最新进展。

**牢记第一目标：尽快让小米 10S 突破米标，进入澎湃 4。我们的目标是做出能开机的系统，而不是无限期完成一份完美的技术审计报告。也就是说效率第一，我们目标是尽快做出包刷入在standalone看日志然后再迭代。**

以后每次进入 Standalone，都必须先完整备份，再读取分析，不能只挑选 `console-ramoops` 等常见日志。

具体要求：

1. 将 `THYME_DIAG` 诊断卷内所有可访问文件和子目录完整复制到新建的独立时间戳目录。
2. 保留原始文件名、目录结构，不覆盖任何历史取证文件。
3. 生成完整文件清单，记录大小和 SHA-256，并核验复制结果。
4. 基于备份副本逐一读取、分类分析所有文件，包括 `console-ramoops`、`pmsg-ramoops`、`oops.raw`、Standalone 自身日志及其他文件。
5. 区分本轮 Candidate、历史残留和 Standalone 自身的记录，不能混淆。
6. 如果某个文件无法复制或读取，明确记录缺失原因，不能直接忽略。
7. 完成完整取证后，Codex 才能自主决定是否恢复 PixelOS。

以后每份完整的 Codex Prompt 都会自动包含这项要求。

下述为最终权限界定：

以后 THYME-OS4 项目采用以下最终常规授权规则：

| 操作                                                 | Codex 权限         |
| ---------------------------------------------------- | ------------------ |
| 分析、修改代码、构建镜像                             | 自主执行           |
| Candidate 指定实验分区刷写                           | 自主执行           |
| 擦除 userdata、metadata                              | 自主判断和执行     |
| Standalone RAM 启动及完整取证                        | 自主执行           |
| 恢复 PixelOS A0′                                     | 自主判断和执行     |
| 刷完 Candidate 后首次启动新系统                      | 必须等待你现场确认 |
| 回锁 Bootloader                                      | 永久禁止           |
| 修改 persist、EFS/NV、射频校准、设备身份等非实验目标 | 禁止擅自操作       |

> **人工确认节点的最终定义：** 项目常规流程只保留一个必须由我现场确认的人工节点：Candidate 已刷写完成、设备仍停留在 Bootloader Fastboot，准备对该新 Candidate 执行首次正式启动时。此时必须停止并等待我明确下达“开始启动 Cxx”。此前的代码修改、构建、必要的受控刷写、Standalone RAM 取证、userdata/metadata 擦除（有明确工程理由时）及 PixelOS 恢复，均可在本交接手册规定的范围内自主连续执行。

### 两项重要执行原则

**数据清除：**既然这台小米 10S 没有需要保留的个人数据，Codex 可以根据首次安装、加密状态和实际故障判断是否清除 userdata、metadata，不必反复请示，但也不要每轮无意义地重复清除。

**PixelOS 恢复：**Codex 可以在实验结束或需要恢复设备时自主执行。不过，应当先通过 Standalone 保存可取得的故障现场，不能为了恢复系统而丢失新日志。

以后每次给你的完整 Codex Prompt，都会自动包含这些权限安排。

整个项目只保留一个常规人工确认节点：刷完新 Candidate、准备正式启动时，必须等你在场观察。

不再要求每个 Candidate 只能修改一个变量，而是要求每次修改都有明确证据、相互兼容，并且出现新故障后能够定位。
如果日志已经明确证明存在多个启动阻塞，而且它们的修复方法都有足够依据，完全可以在同一个 Candidate 中一起解决，不必故意拆成 C15、C16、C17，每次刷入、开机、失败、进入 Standalone 再重新构建。
但也不能反过来，把十几个只有理论风险的问题一起改掉。否则一旦启动情况发生变化，Codex 又会不知道究竟是哪项修改起了作用。
我的建议是把“严格单变量”调整为证据驱动的最小修复集合。

今后 Codex 遇到新的启动或兼容性问题，我会默认采用这个顺序：

1. 先看小米 10S 的真实故障日志，确定卡在哪个阶段、报什么错误。
2. 立即对照 K40 成功移植包，寻找它针对同类问题采用的适配方式。
3. 比较 K40 成功包、原版供体和当前 Candidate，判断我们遗漏了什么。
4. 如果找到适用于 thyme 的现成修复，优先复用；如果没有，再安排定点诊断或新的修复实验。

这条规则不只适用于当前 EGLConfig 问题，后续遇到显示、Vulkan、HAL、SELinux、启动链等问题也一样。

同时保留一个原则：优先参考 K40 的成功经验，但不盲目照搬 K40 的设备专属驱动、内核或固件。

给 THYME-OS4 的 Codex Prompt，会固定加上这条“磁盘空间门禁”。

核心规则是：**每次开始重型操作前先检查 C、D、E 三个盘的剩余空间；只要任一盘 `<= 50 GB`，就先排查所有盘内本项目相关占用并做必要清理。**

清理范围优先包括：

- 后续不再需要的旧 `stage/run` 临时目录
- 重复解包目录
- 可重新生成的大型 `raw/sparse super` 临时文件
- 旧 Candidate 的重复中间产物
- 已确认不会再复用的构建缓存

但要保留当前有效 Candidate、源码、原始取证、日志、报告、可信基线和仍可能复用的中间资产。

**特别规则：绝对不要动 Docker。** 包括 Docker Desktop、镜像、容器、volume、Docker/WSL 数据目录等，即使它们占很多空间，也不能为了本项目腾空间去删。
