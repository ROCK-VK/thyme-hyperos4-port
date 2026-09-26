# 小米10S移植澎湃OS 4：资料调查与环境准备计划

更新时间：2026-09-09。已完成第一轮资料入库、工具配置和离线镜像分析；尚未刷写设备。

## 当前准备进展（用户补充后更新）
- 最新：用户成功启动Ubuntu26.04 LTS/resolute，已验证可用并复用。代理提示不等于断网，apt索引更新成功。项目内`tools/platform-tools`的ADB/Fastboot均为37.0.1；用户确认VS Code已有。当前不再需要下载基础软件，已转入离线镜像分析。
- 用户提供wsl -l -v输出：Ubuntu与docker-desktop均为WSL2、Stopped。已读取`/etc/os-release`并确认Ubuntu26.04；无需再下载Ubuntu，文中24.04安装建议保留为备用信息。
- ROM已到位：17U `payload.bin`为10,407,523,197字节；metadata确认`nezha`、Android 17、OS4.0、`17OS4.0.260905.065436767.QCPECN.S`、SDK37、2026-08-01补丁。10S当前目录实际是用户确认的`OS1.0.4.0.TGACNXM_13.0` Android13官方线刷包，super.img 7,882,016,224字节；作为官方底层/回退参考。
- 内存32GB、E盘约300GB空闲；10S已解锁BL、非主力机，Recovery未知（均为用户报告）。
- 天空参考ROM已放入10S系统/OurSky_Mi10s_OS3.0.318.0.WPBCNXM_A16_b3334；用户称为当前使用系统。
- 目录检查发现super.img.zst（5,463,896,943字节）、boot及vendor_boot等镜像；已用WSL解压super并读取动态分区，已解包boot/vendor_boot ramdisk并保存分析副本。
- 附带教程写init_boot，而目录与卡刷脚本使用boot；实际分区必须另行核验，勿将模板教程当作设备证据。
- 系统PATH仍有ADB 33.0.0、Fastboot 36.0.0；项目内独立Platform-Tools已配置为37.0.1，后续固定使用项目内完整路径。Git 2.54.0版本命令正常。
- 先核验用户正在下载的包，不再以寻找其他供体为当前首要任务。

### Google Drive PixelOS参考包（根据用户截图）
- 参考包已下载到`[LOCAL_PROJECT_ROOT]\pixel参考`。原始ZIP没有保留，但已经解出`PixelOS_thyme-17.0-20260820-1750/payload.bin`（2,887,935,611字节）、OTA元数据和全部独立镜像；`.md5sum`仍在，因此可以校验独立文件与payload，无法验证缺失的原始ZIP。
- `zip`用于查看可启动的Android17 thyme系统结构；单独镜像用于对照boot/vendor_boot/dtbo和动态分区。`super_empty.img`体积很小，保留作为动态分区元数据模板参考。
- 已保存到`[LOCAL_PROJECT_ROOT]\pixel参考`，与17U供体和天空包分目录；独立镜像SHA-256已记录在当前状态日志。payload已提取并已核对system/vendor/product属性。
- 不直接刷这些镜像；先读取头信息、AVB、fstab、分区和启动参数。PixelOS不是HyperOS系统供体。

### 三套资料的分工
- 17U OS4：提供Android17/HyperOS 4的system、product、system_ext及其框架/应用素材。
- 天空10S OS3：提供已在thyme上工作的HyperOS移植结构、firmware、boot/vendor_boot、分区脚本和目标机经验。
- PixelOS thyme Android17：提供Android17目标机启动链、内核/设备树、dtbo/vendor_boot、VINTF/SELinux和动态分区参考。
- 10S官方OS1.0.4.0：提供官方thyme底层和回退材料。

## 一、ROM调查结论

- [小米官方澎湃OS页面](https://hyperos.mi.com/)明确列出17 Ultra / 徕卡版为OS4 Beta首批推送机型，8月14日起推送。
- 本次没有取得可以核验为“17 Ultra最新OS4 Beta / Android 17完整包”的公开直链。不能把“未查到链接”理解为“系统不存在”。
- [小米官方Android 17预览计划](https://www.mi.com/global/support/guidance/android-beta/)页面下方有17 Ultra / Leica Leitzphone下载入口，安装说明为ZIP本地升级。这是Android 17开发者预览入口，不能据此宣称是OS4 Beta，也未下载检查是否全量包。
- [小米开发者Android 17适配文档](https://dev.mi.com/xiaomihyperos/documentation/detail?pId=2297)可作平台参考，应用适配教程不是ROM移植教程。
- 搜索获得的社区版本号仅作线索，尚未核验到官方对应整包，暂不锁定“最新版本”。
- 获取目标包后记录：机型、完整版本号、地区、Android版本、发布日期、原始来源、文件大小、SHA-256、是否全量。检查OTA metadata和镜像build属性，不仅看文件名。

## 二、要卡刷包还是线刷包

| 用途 | 优先准备 | 原因 |
|---|---|---|
| 17 Ultra供体素材 | 完整卡刷ZIP；完整线刷包也可 | 需要的是system/product/system_ext等镜像内容，外层包装不决定可移植性 |
| 10S救援回退 | 10S官方完整线刷包 | 作为10S自身恢复资料，另行核对版本、防回滚与刷写脚本 |
| 10S适配参考 | 用户现有可运行OS3移植包及说明 | 对照10S启动、vendor、权限、相机等实现 |
| Android 17兼容参考 | 用户分享的Pixel移植包及配套底层 | 先确认实际Android版本、支持机型和已知缺陷 |

优先全量包。增量OTA依赖特定旧版本，无法简单当作完整镜像来源；后续可在有匹配旧包时研究重建。
若ZIP含payload.bin，使用payload-dumper-go提取；其他布局按实际结构选择工具。
绝不将17 Ultra整包或其引导/基带固件直接刷到10S。保留并适配10S硬件相关部分；boot、vendor等也不能整套照搬17 Ultra。
参考：[AOSP分区说明](https://source.android.com/docs/core/architecture/partitions)、[A/B更新](https://source.android.com/docs/core/ota/ab)。

## 三、用户资料评估

### APTKernel
- [指定发布](https://github.com/AstideLabs/android_kernel_xiaomi_sm8250/releases/tag/v20260821-[REDACTED_DEVICE_ID])：20260821 / [REDACTED_DEVICE_ID]，明确列出thyme。
- 发布区分MIUI与AOSP，区分ReSukiSU-SuSFS与NoKernelSU。
- [当前README](https://github.com/AstideLabs/android_kernel_xiaomi_sm8250)把thyme对应为小米10S，声明Android 11–17适配方向、EROFS、BPF/clone3/Binder回移。
- 有价值：作为10S Android 17内核候选，以及研究所需内核补丁的来源。
- 边界：当前README可能晚于指定发布；需要核对指定提交与实际资产。作者声明不是本项目验证。
- 初始候选方向为thyme + MIUI + NoKernelSU，最终需确认配套底包和安装脚本。现阶段不刷。
- 内核不能自动解决vendor/HAL、VINTF接口、SELinux、图形、相机和电话兼容；参考[AOSP VINTF](https://source.android.com/docs/core/architecture/vintf)。

### Google Drive
- [用户共享目录](https://drive.google.com/drive/folders/1wV4t2wfr0bH4mQFWO6MzNtIyR5tt8zNQ)。
- 网页直读曾超时；现以用户截图和本地下载目录为准，payload、OTA元数据及独立boot/dtbo/vendor_boot/super_empty均已确认。
- “Pixel17到10S”是用户描述，待确认指Android 17类原生移植以及实际构建版本。
- 若确为10S Android 17可用包，可参考其内核、vendor、启动配置和补丁；不能据此推定澎湃OS4也能运行。
- 作者说明、完整包名、底包要求、刷机方式和已知Bug仍需后续结合实机快照核对；本地payload和启动镜像已经完成初步提取。

## 四、环境：现在需要什么

已粗查一生一芯项目的当前状态：其使用npu_toolchain_dev容器。该容器及npu_toolchain:latest镜像保留；本项目使用独立Ubuntu环境，不将ROM工具装入NPU容器。Docker与Ubuntu WSL可以共存，但共享硬件资源；不为本项目重置Docker、注销其WSL发行版或随意修改全局WSL设置。

原始下载入口（本轮所需基础工具已完成配置，后续仅按缺口补齐）：
- Windows Platform-Tools：https://developer.android.com/tools/releases/platform-tools （选择Windows下载，解压到本项目tools/platform-tools，保留system32内旧工具）。
- Ubuntu 24.04 LTS WSL：https://ubuntu.com/wsl/docs/stable/howto/install-ubuntu-wsl2/ （先确认是否已安装；选择WSL版，不下载桌面ISO）。
- VS Code缺少时：https://code.visualstudio.com/download ；微软WSL扩展按 https://code.visualstudio.com/docs/remote/wsl 安装。
- payload-dumper-go：https://github.com/ssut/payload-dumper-go/releases （后续按运行环境选择Linux x86_64或Windows x86_64）。

建议Windows负责USB调试与后续刷写，现有WSL2 Ubuntu 26.04负责Linux文件处理。工具已验证可运行，无需为了本项目另装Ubuntu 24.04。

| 优先级 | 软件 | 安装位置/用途 | 来源 |
|---|---|---|---|
| 已有 | Android SDK Platform-Tools 37.0.1 | Windows独立目录；adb抓日志、fastboot查询与后续刷写 | [Google](https://developer.android.com/tools/releases/platform-tools) |
| 必备 | 对应小米设备的USB驱动 | Windows；保证ADB和Fastboot两个模式都识别 | 优先设备厂商驱动，待识别结果决定是否需要安装 |
| 已有 | WSL2 + Ubuntu 26.04 LTS | Linux解包、脚本、打包与后续编译 | [Microsoft](https://learn.microsoft.com/en-us/windows/wsl/install) |
| 已有 | VS Code（WSL扩展待核实） | Windows编辑器连接Ubuntu | [Microsoft](https://code.visualstudio.com/docs/remote/wsl) |
| 已有 | Git | Ubuntu内管理脚本与补丁；Windows已有Git可保留 | [Git官网](https://git-scm.com/downloads/) |
| 已有 | 7-Zip | Windows查看/解压外层ZIP、TGZ | [7-Zip官网](https://7-zip.org/) |
| 部分已有 | Python 3、venv（pip按需要补） | Ubuntu运行处理脚本；与现有Anaconda隔离 | Ubuntu软件源 |
| 已有 | payload-dumper-go 2.0.2 | 从OTA payload提取分区镜像 | [作者仓库](https://github.com/ssut/payload-dumper-go) |
| 已有 | erofs-utils、e2fsprogs、attr | Linux文件系统检查与处理 | Ubuntu软件源 |
| 已有/部分 | lpunpack/lpmake、simg2img、AOSP `unpack_bootimg.py`；avbtool/mkbootimg待需要时补齐 | super、sparse、AVB和启动镜像分析 | AOSP/静态Android-tools |
| 后续 | JDK、Apktool、JADX | 分析和修改APK/JAR资源与代码 | [Apktool](https://github.com/iBotPeaches/Apktool)、[JADX](https://github.com/skylot/jadx) |
| 后续 | 内核指定Clang及构建依赖 | 需要改内核时才配置，按固定提交的构建说明 | APTKernel仓库 |
| 回退准备 | MiFlash | 可选恢复工具；须核对来源、10S包和选项 | 暂未核验具体安装包，不建议随意找合集 |

手机目前不需要为了准备工作额外安装Root管理器、刷机工具箱或MT管理器。先确认现有Recovery是否适配当前10S分区与加密。
Android Studio、完整AOSP源码、Docker、虚拟机、付费ROM厨房都不是第一阶段必需品。

硬件预算是工程建议：16GB内存可起步做二进制解包，32GB更宽裕；建议空闲SSD空间150–250GB并随镜像数量调整。全量AOSP编译另算，不在初期范围。
E盘此前查询约333GiB可用，用户最新报告约300GB、内存32GB，足够先做素材分析；CPU尚未核实。
Linux工作文件放WSL的Linux文件系统中，原始压缩包可放E盘；保留权限、符号链接、扩展属性和SELinux标签。参考[微软文件系统建议](https://learn.microsoft.com/en-us/windows/wsl/filesystems)。

## 五、按顺序推进的计划单

1. 环境与设备盘点：Windows版本、内存、WSL2状态；手机完整ROM版本、BL状态、Recovery版本、是否备用机。
2. 配置基础工具：已确认adb/fastboot版本与路径；WSL2发行版可启动；Ubuntu内Python/Git/解包工具可用。
3. 备份与恢复准备：备份用户数据；收集10S回退包和现有ROM；记录分区布局。校准/基带相关备份按实际分区和权限设计，私人备份不上传。
4. 素材入库：供体OS4全量包、10S官方包、现有OS3移植包、Pixel参考包及内核；所有文件记录来源与SHA-256。
5. 离线分析：已读取build属性、OTA元数据、boot头、文件系统类型、super布局、VINTF/SELinux；差异表见`work/reports/初步分区与属性核对.md`和`work/reports/启动链与ramdisk对比.md`。
6. 建立可重复处理脚本：先在副本上完成解包/重打包，检查权限、标签、镜像大小与分区限制。此步骤不等于可开机验证。
7. 最小启动实验：有恢复路径后才制作10S专用试验包；先争取启动与ADB日志，再逐项定位故障。
8. 功能验证：显示触控、Wi-Fi、电话数据、音频、相机、指纹、蓝牙、NFC、加密、充电和休眠；逐项记录，不以亮屏等同成功。
9. 发布整理：固定源码/补丁/素材版本、构建哈希、已知问题和刷机说明，核对设备运行版本与产物一致。

第一阶段验收：Windows能识别手机并抓日志，Fastboot模式能只读识别；WSL2运行；能提取一个全量包并读取镜像信息；10S回退资料齐备。
现阶段不承诺能完整移植或所有17 Ultra功能可用。最终可行性取决于实际镜像与硬件兼容分析。

## 六、当前阶段、分工与成功距离（2026-09-09）

### 已完成的阶段

- 环境与工具：完成。Windows项目版Platform-Tools、WSL、payload、EROFS、super、boot解包工具均可用。
- 资料入库：完成。17U OS4、官方10S、天空OS3、PixelOS thyme Android17均已提取并完成第一轮属性、分区、启动链、VINTF和SELinux对比。
- 实机基线：完成只读部分。已确认手机运行天空OS3.0.318.0、Android16、EROFS、A槽和Sky专用内核；KSU模块已由用户关闭。

### 还没有完成的关键阶段

1. **可移植性矩阵**：逐项列出17U system/product/system_ext中依赖`nezha/sm8850/canoe`的服务、库、权限和资源，并保留`thyme/kona`硬件层。
2. **第一版离线组合**：生成不刷手机的10S专用动态分区组合，优先保留10S firmware、dtbo、vendor/odm和AVB布局；17U只引入可验证的OS层，PixelOS只作为Android17启动链参考。
3. **卡刷包与校验**：制作可回退的测试包，完成分区大小、EROFS、AVB、VINTF、SELinux和脚本检查；该阶段仍不代表能启动。
4. **第一次实机启动**：用户备份后进入Recovery/Fastboot并执行刷写，Codex根据adb/logcat/bootreason迭代修复。
5. **功能收敛**：逐项验证显示、触控、Wi-Fi、移动网络、通话、音频、相机、指纹、蓝牙、NFC、充电、休眠、加密和稳定性。

### Codex与用户的边界

- Codex可以完成镜像提取、文件差异、属性和分区分析、启动链/AVB/VINTF/SELinux静态检查、脚本与卡刷包生成、日志解析和每轮修复。
- 用户必须参与备份、进入Recovery/Fastboot、确认实体设备、执行或确认刷写、处理无法自动恢复的硬砖，并提供实机功能测试结果。
- 当前不需要下载Android Studio、完整AOSP源码或重装WSL；只有确定要改内核或大规模重编译时才补齐对应工具链。

### 距离成功的真实判断

- 以“第一次能开机并稳定进入桌面”为目标，目前完成的是准备和侦察，约占总工程量的15%–25%；还没有可刷的Android17测试包，也没有启动成功证据。
- 以“日常可用的HyperOS 4 Android17移植”为目标，当前只能判断为**可行性有希望、风险很高、尚未进入实机迭代**。最大风险是17U供体为`sm8850/canoe`，10S为`sm8250/kona`，两者的vendor/HAL、VINTF和SELinux版本不同。
- PixelOS已经证明thyme存在Android17启动参考，天空OS3已经提供可工作的10S HyperOS底层，这两点提高了成功概率；但不能推导出17U HyperOS 4一定能在10S启动。
