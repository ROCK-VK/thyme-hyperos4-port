# 安卓移植入门指南

这是一份写给“有刷机经验、会 STM32、接触过 K230 和摄像头，但还不熟 Android 系统内部结构”的入门说明。

本文不假设你会 Android 源码，也不要求你马上学会编译整个 Android。先建立一张正确的地图，比记住几十个刷机术语更重要。

本文会结合当前项目举例：

- 目标设备：小米 10S，代号 thyme，搭载骁龙 870（SM8250-AC）；Android 设备树和兼容树中常使用平台代号 kona / sm8250。
- 目标系统：17 Ultra 的 HyperOS 4 / Android 17。
- 天空包：已经在 10S 上工作的 HyperOS 参考。
- Pixel thyme 包：同为 thyme、更加接近 Android 17 的启动链和底层参考。
- 官方 10S 包：分区、固件和回退基线。

截至 2026-09-13，当前项目已经完成 v04/B0 混合树的大量主机端离线审计，并进行了多轮受控实机对照测试。原始 B0 和后续 Android 17 hybrid 候选都没有成功进入 Android 17；但原生天空 Android 16 基线曾经成功启动到 `boot_completed=1`，说明手机硬件、天空原生启动链和天空系统本身可以工作。电脑端 PASS 不等于手机一定能启动，当前仍没有可称为“稳定成品”的 Android 17 刷写包。

---

## 1. 先建立一个总的认识

Android 手机不是“一个系统文件加一个内核”，而是一整套分层的软件和硬件组合：

~~~text
应用和桌面
    ↓
Android Framework / system_server
    ↓
HAL 硬件抽象层
    ↓
Linux 内核驱动
    ↓
手机硬件
~~~

手机开机时还要经过另一条启动链：

~~~text
Boot ROM
    ↓
Bootloader / Fastboot
    ↓
AVB 验证
    ↓
boot / vendor_boot / dtbo
    ↓
first-stage init，读取 fstab 并挂载分区
    ↓
Android init 和各种服务
    ↓
system_server
    ↓
桌面和应用
~~~

所以“移植一个 ROM”实际是在同时处理几件事：

1. 让系统文件适合目标设备。
2. 让启动链能够找到并挂载正确的分区。
3. 让 Android Framework 找到目标设备的硬件服务。
4. 让权限、接口、动态库和硬件驱动彼此匹配。
5. 出问题时还能回退和救援。

这比单片机烧录一个固件复杂很多。

---

## 2. 这算不算嵌入式？

算，而且是非常典型的嵌入式系统，只是它比 STM32 裸机复杂很多。

### 和 STM32 的对应关系

| STM32 | Android 手机 |
|---|---|
| 芯片启动代码 | Boot ROM、Bootloader |
| Flash 中的固件 | boot、system、vendor 等分区 |
| 中断和外设寄存器 | Linux 内核驱动 |
| STM32 HAL 库 | Android HAL，但不是同一个库 |
| main 函数 | init、system_server 等系统进程 |
| RTOS 任务 | Linux/Android 进程和线程 |
| 编译后烧录 bin/hex | 生成镜像并刷入分区 |
| 串口日志 | adb、logcat、kernel log、pstore |

### 和你实际使用的亚博 K230 的对应关系

你现在使用的是亚博 K230 开发板配套的 IDE，通过类似 OpenMV IDE 的界面直接烧录和运行 Python。这个使用方式更接近“在厂家提供的固件和 Python 运行时上写应用”，实际链路可以理解为：

~~~text
Python 脚本
    ↓
CanMV / MicroPython 运行时
    ↓
K230 板级固件和已经封装好的驱动
    ↓
摄像头、GPIO、显示屏、AI 加速器等硬件
~~~

IDE 和板上的预置固件已经替你处理了很多事情：

- 芯片启动；
- Python 解释器或运行时；
- 摄像头和显示驱动；
- 内存初始化；
- 外设接口；
- 程序下载和运行。

所以，按照你目前的实际经历，你并没有直接接触 Linux 内核、rootfs、Linux init、分区表和动态链接器。K230 芯片或某些固件内部可能包含更复杂的操作系统或运行时组件，但那不是你现在需要掌握的前置经验，也不能简单等同于“会 Linux”。

Android 会把这些原本被 K230 IDE 隐藏的层全部暴露出来，并继续增加：

- Framework；
- Binder 跨进程通信；
- HAL 服务；
- AIDL/HIDL 接口；
- SELinux；
- AVB 启动验证；
- 动态分区；
- A/B 无缝更新；
- 大量预编译的厂商组件。

因此，你的 STM32 和 K230 经验仍然有帮助：你已经熟悉嵌入式硬件、固件、摄像头和“代码控制硬件”的基本思想。但 Android 移植还需要另外学习 Linux 系统、分区镜像、启动链、进程、动态库、权限策略和系统服务；不能假设使用过 K230 IDE 就已经具备 Linux Android 基础。

---

## 3. Fastboot、Recovery 和两种刷机方式

### Fastboot 是什么

Fastboot 不是一种 ROM 格式，而是一种 Bootloader 通信协议和工具。

手机进入 Bootloader 模式后，电脑上的 fastboot 可以读取信息、擦除分区或写入镜像，例如：

- boot；
- vendor_boot；
- dtbo；
- vbmeta；
- super；
- modem；
- 其他固件分区。

Fastboot 适合直接操作分区和启动镜像，常用于：

- 线刷；
- 刷单个镜像；
- 解锁和查询设备状态；
- 救援；
- 测试 boot 或 vendor_boot。

部分新设备还有 fastbootd。它是在 Android 用户空间中运行的 Fastboot，主要负责动态分区相关操作。它和 Bootloader fastboot 不是完全同一个环境。

### Recovery 是什么

Recovery 是一个独立的小型系统环境。TWRP 就是常见的第三方 Recovery。

Recovery 通常可以：

- 挂载分区；
- 解密 userdata；
- 执行卡刷 ZIP；
- 使用 adb；
- 备份和恢复；
- 格式化 data；
- 查看日志。

### 线刷和卡刷

“线刷”和“卡刷”描述的是刷机入口，不是 Android 的内部结构。

| 方式 | 入口 | 常见内容 |
|---|---|---|
| 线刷 | Bootloader/Fastboot 或厂商工具 | 镜像文件、刷机脚本、分区写入命令 |
| 卡刷 | Recovery | ZIP、updater-script、update-binary 或类似安装逻辑 |

同一个系统内容可以被做成不同形式：

- 镜像包；
- Fastboot 包；
- Recovery ZIP；
- OTA 包；
- payload.bin；
- 动态分区 super.img。

“卡刷包”不等于“系统本身”，“线刷包”也不等于“完整底层”。它们只是不同的包装和写入方式。

---

## 4. 常见分区和镜像

### boot.img

通常包含：

- Linux 内核；
- 设备树或相关启动信息；
- ramdisk；
- Android 启动早期所需内容。

刷机圈常把 boot.img 直接叫“内核包”，但严格来说它不只是内核。

### vendor_boot.img

它通常包含厂商侧的启动 ramdisk，里面可能有：

- first-stage init；
- fstab；
- 厂商启动脚本；
- 设备节点规则；
- Android 启动所需的厂商配置。

在新 Android 设备上，很多原来放在 boot 里的厂商启动内容被拆到了 vendor_boot。

当前项目中，Pixel 的 vendor_boot 不能直接使用，因为它原本只按 ext4 挂载，而我们组合中的部分分区是 EROFS，还需要增加 10S 的 mi_ext 挂载逻辑。因此 v04 对它进行了适配和重新打包。

### init_boot.img

部分新设备使用 init_boot 存放通用 ramdisk。不同 Android 启动版本的分区布局不同。

当前小米 10S 是 v3 启动布局，没有 init_boot。17 Ultra 的 v4 启动布局不能直接照搬到 10S。

### dtbo.img

DTBO 是 Device Tree Blob Overlay，设备树覆盖层。

设备树描述硬件连接关系，例如：

- 屏幕；
- 触控；
- 摄像头；
- GPIO；
- 供电；
- I²C/SPI；
- 传感器；
- regulator。

可以把它理解成“告诉内核这台机器有哪些硬件、硬件接在哪里、参数是什么”。

它和 STM32 的芯片启动配置、板级初始化有一点相似，但形式和使用方式不同。

### system

主要是 Android 的通用系统和 Framework 内容。HyperOS 还会把很多系统功能拆到 system_ext 和 product 中。

可以把它理解为“系统上层”和“大部分 Android 软件平台”。

### system_ext

系统扩展分区，通常放厂商对 Android Framework 的扩展、系统服务、额外权限和相关组件。

### product

通常放产品层资源、应用、配置、界面资源和产品特性。

### vendor

这是 Android 移植中非常重要的分区，通常包含：

- 厂商 HAL；
- 厂商服务；
- 硬件相关动态库；
- 音频、相机、显示、传感器、充电等实现；
- vendor 侧的 SELinux 策略；
- VINTF manifest；
- 厂商 init 脚本。

它通常不是“系统界面”，而是“让系统能够使用这台具体手机硬件”的一大部分。

### odm

ODM 通常放更靠近具体机型的定制内容。不同厂商对 vendor 和 odm 的划分不完全相同。

在小米设备上，odm 也可能包含机型、区域或硬件变体相关内容。

### mi_ext

这是小米的扩展分区，用来承载额外属性、配置、扩展目录以及 HyperOS 需要的路径。

它不是内核，也不是 vendor 的完全替代品。当前项目里天空包的 mi_ext 很小，但启动 fstab 和系统路径仍可能依赖它，因此不能因为文件少就随便删除。

### super.img

super 是动态分区容器。它本身通常不是一个普通的系统目录，而是里面包含多个逻辑分区：

~~~text
super
 ├─ system
 ├─ system_ext
 ├─ product
 ├─ vendor
 ├─ odm
 └─ mi_ext
~~~

这些逻辑分区由动态分区元数据管理。lpdump 可以查看布局，lpunpack 可以拆出逻辑分区，lpmake 可以重新打包。

所以刷 super 时，实际可能一次性覆盖多个系统分区。

### super 和“启动链”到底是什么关系？

这是本项目里最容易混淆的一组概念。

可以先用一个不严格但好记的比喻：

```text
super = 房子里面的系统空间和家具
启动链 = 钥匙、门锁、电路总闸，以及开门后最早的一段引导程序
```

`super` 主要装 Android 用户空间。它里面可以有 `system`、`system_ext`、`product`、`vendor`、`odm`、`mi_ext` 等逻辑分区。刷入一个新的 `super.img`，往往会同时替换多个系统分区，但它不会自动替换 `boot.img`、`vendor_boot.img`、`dtbo.img` 或 `vbmeta.img`。

“启动链”指手机从按下电源键到 Android 用户空间开始运行之前的那一串组件，当前项目重点是：

```text
Boot ROM / 高通早期 Bootloader
        ↓
vbmeta / AVB 启动验证
        ↓
boot.img       → 内核和通用启动内容
vendor_boot.img→ 厂商 ramdisk、init、fstab、启动脚本
dtbo.img       → 设备树硬件覆盖
        ↓
first-stage init 挂载 super 中的逻辑分区
        ↓
system / vendor / product / system_ext 等 Android 用户空间
```

因此，下面两种组合不是一回事：

```text
天空启动链 + 天空 super
天空启动链 + Android 17 super
```

第一种是同一套系统的匹配组合，第二种是“混合系统”，可能因为 Android 版本、fstab、AVB、HAL、SELinux、`mi_ext` 或动态分区布局不匹配而在很早阶段失败。

这正是我们之前测试的核心：只替换 `super`，或者只替换启动链，观察到底是哪一组组合能够越过早期启动阶段。Round-6 中“天空启动链 + 天空 super”能启动，而 Round-8 中“天空启动链 + Android 17 hybrid super”回 Fastboot，说明问题集中在混合组合的兼容性范围内，但还没有定位到某一个具体文件。

### vbmeta 和 AVB

AVB 是 Android Verified Boot，Android 验证启动。

vbmeta 中会记录或验证其他镜像的哈希、签名和依赖关系，例如：

- boot；
- system；
- vendor；
- dtbo；
- super。

如果镜像内容改过而 vbmeta 仍然要求旧哈希，设备可能无法启动。

关闭验证标志只能改变验证行为，不能自动修复系统内容、fstab、HAL 或 SELinux。

### firmware

Firmware 是更靠近硬件的固件，例如：

- modem；
- Bluetooth；
- Wi-Fi；
- DSP；
- GNSS；
- 触控或其他协处理器固件。

17 Ultra 的固件不能因为 Android 版本相同就刷到 10S。

---

## 5. 内核、驱动、HAL 和 Framework 的区别

这四个词经常被混在一起。

### 内核

Linux kernel 负责：

- 进程和线程；
- 内存管理；
- 文件系统；
- 网络；
- Binder 基础；
- 设备驱动；
- 电源管理；
- 设备节点。

### 驱动

驱动是内核中控制具体硬件的部分，例如：

- 屏幕驱动；
- 触控驱动；
- 摄像头传感器驱动；
- 音频 codec 驱动；
- I²C/SPI 外设驱动；
- 充电芯片驱动。

### HAL

HAL 是 Android Framework 使用硬件能力的接口层。

例如：

~~~text
相机 App
  ↓
Camera Framework
  ↓
Camera HAL
  ↓
Linux 摄像头驱动
  ↓
摄像头传感器
~~~

Android HAL 和 STM32 HAL 的思想类似，都是把硬件细节封装起来，但不是同一个库，也不是同一种代码架构。

### Framework

Framework 是 Android 上层系统服务和 API 的集合。应用调用的相机、音频、定位、显示、电源等功能，通常先进入 Framework，再由 Framework 调用 HAL。

因此：

- 内核能启动，不代表 Android 能使用相机；
- vendor 存在，不代表 HAL 接口一定匹配；
- HAL 能注册，不代表 SELinux 一定允许它运行；
- 系统界面能显示，不代表电话、相机、指纹和充电都正常。

---

## 6. Binder、AIDL 和 HIDL

Android 中很多系统服务不是直接函数调用，而是跨进程通信。

Binder 是 Android 的主要 IPC 机制，可以理解为 Android 专用的高性能进程间通信框架。

AIDL 和 HIDL 是描述服务接口的方式。

例如一个充电服务可能提供：

~~~text
接口：IChargingControl
实例：default
版本：2
~~~

系统通过 Binder 找到这个服务，然后调用接口。

我们项目中出现过类似：

- vendor.lineage.health.IChargingControl/default；
- vendor.lineage.health.IFastCharge/default；
- vendor.lineage.livedisplay.IPictureAdjustment/default；
- vendor.lineage.powershare.IPowerShare/default。

这些就是 Android 侧的硬件服务接口，不是 STM32 外设库。

如果 system 期待一个接口，但 vendor 没有对应服务，可能导致系统服务启动失败。

如果 vendor 声明了某个服务，但 system/framework 并不支持，可能产生 VINTF 或启动期问题。

---

## 7. VINTF：系统和硬件之间的“接口合同”

VINTF 可以理解成 Android Framework 和 vendor 之间的一份兼容性合同。

其中常见两类文件：

### Vendor Manifest

它声明：

> 这套 vendor 提供了哪些 HAL、哪些服务、哪些版本和实例。

### Framework Compatibility Matrix

它声明：

> Framework 需要哪些 HAL、哪些版本和实例。

理想状态是：

~~~text
Framework 需要的接口
        =
Vendor 实际提供的接口
~~~

checkvintf 就是用来检查这些接口是否兼容的工具。

当前项目的 v04 检查中发现了 Pixel vendor 里的几项 Lineage 服务声明，而 17U Framework 没有对应声明。这说明它们不能直接照搬，需要进一步判断是保留、补接口，还是只移除启动声明。

VINTF 通过也不等于一定能开机，因为还可能有：

- 动态库缺失；
- SELinux 拒绝；
- init 服务崩溃；
- 内核驱动缺失；
- 文件系统挂载失败；
- 数据解密失败。

---

## 8. SELinux：Android 的强制访问控制

Linux 普通权限主要看：

- 用户；
- 用户组；
- 文件读写执行位。

Android 还使用 SELinux，对进程和资源做更细的强制访问控制。

例如，即使一个进程在 Linux 文件权限上有读权限，SELinux 仍然可能禁止它访问某个设备节点。

SELinux 主要涉及：

- domain：进程所属安全域；
- type：文件、设备节点或服务的安全类型；
- context：对象的安全标签；
- allow 规则：允许谁访问什么；
- service context：Binder 服务对应的安全标签。

典型现象是：

- 系统能启动；
- 服务也存在；
- 但某项硬件功能不能工作；
- logcat 或 dmesg 中出现 avc: denied。

这时不能只改 Unix 文件权限，必须分析 SELinux 策略和标签。

SELinux 类似于“系统级、强制执行的权限策略”，但不是 STM32 的普通寄存器访问控制。

---

## 9. init、fstab 和启动过程

### init

Android init 是系统启动的核心进程之一，负责：

- 读取属性；
- 执行 init.rc；
- 启动服务；
- 创建目录和设备节点；
- 设置权限；
- 挂载文件系统。

vendor 中常见很多 init 脚本，负责启动相机、音频、充电、显示等服务。

### fstab

fstab 告诉 first-stage init：

- 哪些分区要挂载；
- 挂载到什么路径；
- 使用 ext4 还是 EROFS；
- 是否需要 AVB；
- 是否是动态分区；
- 是否需要 first-stage mount；
- 出错时是否允许继续。

当前项目曾经发现：

- super 中 system、system_ext、product、mi_ext 是 EROFS；
- vendor、odm 是 ext4；
- Pixel 原始 fstab 只写了 ext4，且没有 mi_ext。

如果直接使用 Pixel 原始 vendor_boot，启动早期就可能无法正确挂载分区。因此 v04 需要以 Pixel Android 17 vendor_boot 为主体，补上 10S 的 EROFS 和 mi_ext 挂载逻辑。

这就是为什么“同样是 thyme”也不能直接把别人的 vendor_boot 原样刷进去。

---

## 10. ext4、EROFS、sparse 和 raw

### ext4

传统 Linux 可读写文件系统，Android 中非常常见。

### EROFS

Enhanced Read-Only File System，只读文件系统。

它适合系统分区，压缩和读取效率较好，但制作镜像、修改文件和挂载方式与 ext4 不同。

天空 OS3 使用了 EROFS 形式的系统分区。换包时，不能只看目录内容，还必须确认 fstab 和内核是否支持 EROFS。

### sparse image

Sparse 是一种稀疏镜像格式，用来减少镜像文件体积。

它不是新的文件系统。一个 sparse ext4 镜像转换成 raw 后，仍然是 ext4。

### raw image

Raw 是实际完整的块设备镜像形式，很多 Linux 工具更容易直接处理。

### 开包和打包

ROM 处理通常是这样的链条：

~~~text
ZIP / payload.bin
    ↓
提取 boot、vendor、system、super
    ↓
拆分 super 中的逻辑分区
    ↓
挂载或解包 ext4 / EROFS
    ↓
修改文件和配置
    ↓
重新生成文件系统镜像
    ↓
重新打包 super
    ↓
重新处理 AVB 和启动镜像
    ↓
制作 Fastboot 包或 Recovery ZIP
~~~

“开包”只是把东西拆出来，不等于已经完成移植。

---

## 11. 什么是底包、供体、上层和底层

这些词是刷机圈常用说法，不是 Android 官方标准术语。

### 供体

提供某些系统内容的来源 ROM。

当前项目中：

- 17U 是 HyperOS 4 上层系统供体；
- Pixel thyme 是 Android 17 底层和启动链参考供体；
- 天空 OS3 是 10S 工作状态和 HyperOS 结构参考；
- 官方 10S 是原厂硬件和回退供体。

### 底包

通常指能够让目标手机正常启动、识别硬件的基础包，可能包含：

- vendor；
- odm；
- boot；
- vendor_boot；
- dtbo；
- firmware；
- 分区和刷机脚本。

底包不是固定等于某一个分区。

### 底层

比“底包”更宽泛，通常指：

- 内核；
- 设备树；
- boot/vendor_boot；
- vendor/odm；
- HAL；
- firmware；
- fstab；
- VINTF；
- SELinux；
- AVB 和分区布局。

### 上层

通常指：

- system；
- system_ext；
- product；
- Framework；
- 应用；
- 系统资源。

当前项目采用的是分层混合移植：

~~~text
17U：
  提供 HyperOS 4 / Android 17 上层

Pixel thyme：
  提供更接近 Android 17 的 thyme vendor/odm 和启动链参考

天空 OS3 / 官方 10S：
  提供目标机的 EROFS、mi_ext、fstab、固件和回退依据
~~~

这不是把三个包整体拼在一起，而是按分区和功能逐项选择来源。

---

## 12. 当前项目的实际移植方案（v04/B0）

### 12.1 一句话概括

我们的方案是：

> 用 17U HyperOS 4 的 Android 17 上层，用 Pixel thyme Android 17 的目标机 vendor/odm 和启动链作 A17 底层参考，再借用天空 OS3 的 10S EROFS/mi_ext/fstab 经验，按 10S 官方分区和回退事实重新组合、适配、检查。

这属于“分层混合移植”或“跨 ROM 分层嫁接”，不是把任何一个参考包完整刷到 10S，也不是自己从零编写内核和 HAL。

### 12.2 当前 v04/B0 候选的来源

| 层或内容 | 当前来源 | 当前作用 |
|---|---|---|
| system | 17U HyperOS 4 Android 17 | 提供主要 Android 17/HyperOS 4 系统；设备矩阵已换成 thyme/sm8250-common 的 A17 参考 |
| system_ext | 17U | 提供 HyperOS 扩展 Framework、系统服务和 Xiaomi 组件 |
| product | 17U | 提供 HyperOS 4 产品资源、应用和产品层配置，保留后续需要审计的 HyperOS 私有功能 |
| vendor | PixelOS thyme Android 17 | 当前 A17 硬件服务、HAL、VINTF 和 Android 17 SELinux provider |
| odm | PixelOS thyme Android 17 | 当前 thyme 机型/变体相关 ODM 内容 |
| mi_ext | 天空 OS3 10S 参考 | 保留 10S 的小米扩展路径和属性来源 |
| boot | PixelOS thyme Android 17 | 作为 10S Android 17 启动候选，当前文件未改 |
| dtbo | PixelOS thyme Android 17 | 作为 thyme/kona 设备树候选，当前文件未改 |
| vendor_boot | PixelOS 为主体、我们重打包 | 保留 Pixel A17 ramdisk，只修改 fstab 以适配 10S 的 EROFS、mi_ext 和实际分区 |
| vbmeta/vbmeta_system | Sky flags=2 诊断探针 | 只用于离线/解锁实验思路，不是生产 AVB，也不是最终放行依据 |
| firmware | 10S/天空/官方包作为参考和回退来源 | 不使用 17U 的 modem、XBL/ABL 或 17U 专用固件 |

17 Ultra 和小米 10S 不是同一硬件平台：

- 17U vendor 对应 sm8850/canoe；
- 10S 对应 SM8250-AC/骁龙 870，Android 树中常写作 kona/sm8250；
- 17U 使用 v4 启动布局，并有 init_boot；
- 10S、天空和 Pixel thyme 使用 v3 启动布局，没有 init_boot。

因此 17U 只提供上层系统，不直接提供 10S 的 vendor、odm、boot、vendor_boot、init_boot、dtbo、modem 或专用固件。

### 12.3 我们实际修改和重新制作了什么

#### A. 对 17U HyperOS 上层做的适配

当前 system、system_ext、product 的主体文件仍来自 17U，但候选不是原始 17U 镜像，主要做过以下适配：

1. 将 system 中面向 17U nezha 的设备兼容矩阵替换为 Pixel Android 17 的 sm8250-common/thyme 参考矩阵，用于把 Framework 的硬件接口要求改成 10S 方向。
2. 将 product 的设备特性文件调整为 thyme 方向，并修改部分产品身份/指纹字符串。
3. 移除早期审计确认属于 17U 虚拟化或 sm8850 路径的部分服务入口和专用目录，例如 qvirt 服务入口、sm8850 专用 mirim policy 路径。
4. 对删除内容同步调整 product 的 fs_config 和 file_contexts。
5. 没有按文件名批量删除所有 Qualcomm、Xiaomi、卫星、Miracast、touchfeature 或 HyperOS 私有功能；这些内容仍保留，等待 VINTF、动态库、SELinux 和实机日志逐项证明是否需要处理。
6. qvirt 等内容的部分共享库和 Framework 字面量仍保留，避免在没有依赖证据时先造成 linker 或 system_server 断裂。

所以当前上层不是“把 17U 改名成 10S”，而是“尽量保留 HyperOS 4 功能，同时替换目标矩阵并清理已经能证明不属于 10S 的硬件入口”。

#### B. 对 Pixel Android 17 启动链做的适配

Pixel 的 boot.img 和 dtbo.img 当前作为目标机 A17 候选保持原样使用。

Pixel vendor_boot.img 则被作为主体重新打包。我们只修改了：

- system、system_ext、product 的 EROFS 挂载候选；
- vendor、odm 的 ext4 挂载保持；
- mi_ext 的 EROFS/ext4 候选和 /mnt/vendor/mi_ext 到 /mi_ext 的 nofail bind；
- 与 10S 分区名、slotselect、logical、first_stage_mount 相关的挂载契约。

同时保留了 Pixel Android 17 的 metadata、userdata 加密、readahead、AVB 参数和其他 ramdisk 内容。重打包后的 v04 vendor_boot 与 Pixel 原始 ramdisk 对照时，计划外内容没有变化，主要差异就是 fstab。

这份 vendor_boot_v04.img 是我们重新生成的适配产物，不是 Pixel 原文件直接复制。

#### C. B0 最小诊断变体

正式 v04 provider 中有三组 Pixel/Lineage 服务声明导致 host checkvintf 退出 65。经过消费者、ELF、init 和 SELinux 静态审计后，制作了 B0 诊断变体，只删除六个精确路径：

- 三份 Lineage VINTF manifest fragment；
- 三份对应 init rc。

B0 没有删除对应的服务 ELF、接口库或 SELinux 策略。这样做的目的，是先验证“删除声明和启动入口是否足以消除 VINTF 阻断”，而不是宣布这些服务已经安全删除。

B0 的完整 host checkvintf 真实退出码为 0，但它仍然只是诊断和离线候选，不是刷写包。

#### D. 我们自己重新制作的镜像和验证产物

这些不是任何参考包中现成存在的内容，而是本项目重新生成的适配产物：

- B0 的四个 EROFS 镜像：system、system_ext、product、mi_ext；
- B0 的两个 ext4 镜像：vendor、odm；
- 按 10S virtual A/B 和 super 几何重新生成的 super；
- 以 Pixel vendor_boot 为主体的 vendor_boot_v04；
- B0 混合树、SOURCE_MAP、哈希清单和逐文件 provenance 报告；
- Android 17 file_contexts 的验证副本；
- Android 17 linkerconfig 普通模式的离线生成副本；
- VINTF、ELF、init、消费者、SELinux、分区和启动链审计工具。

这里的“自己制作”主要是适配、组合、重打包和验证，不是从零原创了手机内核、相机 HAL、音频 HAL、基带或 HyperOS Framework。

### 12.4 当前最新验证状态

截至 2026-09-13，准确状态是：

- 完整 B0 混合树的来源、文件、EROFS/ext4、super 几何、VINTF、file_contexts 和普通 linkerconfig 等主机检查大部分通过；
- 原始 B0 六项受限写入成功，但首次启动出现 Logo/黑屏循环，随后回到 Fastboot；
- 后续多轮 Android 17 候选测试仍未取得 Android 17、ADB 授权或 `boot_completed=1`；
- 原生天空 `super` + 原生天空启动链曾经成功进入 Android 16，`sys.boot_completed=1`，天空用户数据在当时仍可见；
- Android 17 hybrid `super` 在保留天空启动链时仍回 Fastboot；即使之后单独格式化 `userdata`，结果也没有改善；
- 因此旧 userdata 不是该早期启动失败的充分原因，不能再把“清数据”当成默认修复；
- 设备动态 linker、Binder、SELinux policy load、HAL、VINTF 运行时、AVB/rollback、fstab/fs_mgr 和 Android 17 首启仍未全部闭合；
- 当前没有稳定的 Android 17 成品，也没有可以把“主机检查通过”直接等同于“手机可用”的刷写包。

因此当前准确说法是：

> B0 和后续 hybrid 候选是用于定位问题的实验输入；原生天空系统基线启动成功，但 Android 17 移植仍未成功。

### 12.5 三个参考包各自的方案

#### Pixel thyme Android 17 的方案

从包结构可以确认，Pixel 包采用的是“同目标机 Android 17 适配”路线：

- system 是 Android 17/AOSP 或 Lineage 风格的系统上层；
- vendor/odm 面向 thyme/kona；
- vendor target-level 为 7；
- SELinux policy 版本为 202604；
- boot/vendor_boot/dtbo 是 thyme 的 v3 启动链；
- vendor 使用 ext4；
- VINTF、HAL 和 sepolicy 按 Android 17 目标机重新组织。

它的优点是 Android 17 和 thyme 底层匹配度高。它的缺点是它不是 HyperOS 4，且带有 Lineage health、livedisplay、powershare 等额外服务，不能原样作为 HyperOS vendor 使用。

#### 天空 OS3.0 的方案

天空包采用的是“目标机 10S 上已经工作的 HyperOS 端口”路线。从镜像结构能确认：

- 保留 thyme/kona 的目标机硬件适配；
- 使用 10S 的 vendor/odm/mi_ext 结构；
- system、system_ext、product、mi_ext 使用 EROFS；
- fstab 同时考虑 ext4 和 EROFS，并处理 mi_ext bind；
- vendor VINTF manifest 和官方 10S vendor 逐字哈希相同；
- SELinux 主策略版本与官方 10S 对齐；
- boot/vendor_boot/dtbo 是 10S v3 启动链。

它是非常有价值的 10S/HyperOS 结构参考，但它的 system/vendor 组合是 Android 16/target-level 5，不能直接当作 Android 17 底层。天空包作者原始使用了哪些上层供体，仅凭当前包结构不能完全确定。

#### 官方 HyperOS 1.0.4.0 的方案

官方包不是“移植方案”，而是小米针对 10S 的原厂基线：

- Android 13；
- 10S 官方 vendor/odm；
- 原厂 v3 boot/vendor_boot/dtbo；
- ext4 动态分区；
- 官方 AVB、firmware、刷机脚本和 anti 约束；
- 官方 super、metadata、A/B 和分区容量事实。

本项目没有把官方 Android 13 system 直接并入 Android 17 候选，也没有把官方固件和 17U 底层混刷。官方包主要用于确认“10S 原厂应该是什么样”、制作回退资料和对照 Fastboot/super 行为。

### 12.6 复用、修改和我们自己制作的内容

| 来源 | 直接复用或采用 | 我们修改/适配的部分 | 当前只作参考或明确不采用 |
|---|---|---|---|
| 17U HyperOS 4 | system、system_ext、product 的大部分 HyperOS 4/Android 17 文件、Framework、应用和 APEX | thyme 设备矩阵、部分 product 身份和设备特性、已确认的 17U 专用服务入口/目录、对应 fs_config/file_contexts；随后重新生成 EROFS 和 super | 17U vendor、odm、boot、vendor_boot、init_boot、dtbo、modem、专用固件 |
| Pixel thyme Android 17 | vendor、odm 的大部分文件；boot、dtbo；Android 17 VINTF/SELinux/linker 配置；vendor_boot 作为重打包主体 | vendor_boot 只改 fstab；B0 诊断树再删除 3 份 Lineage manifest 和 3 份对应 init rc | Pixel 的 HyperOS 上层、原始 Pixel super、与未修改 Pixel system 对应的原始 vbmeta；Pixel vendor 中的 Lineage 服务不能未经审计整组删除 |
| 天空 OS3.0 | mi_ext；10S EROFS、fstab、mi_ext bind、目标机路径和 HyperOS 行为参考；flags=2 vbmeta 仅作诊断探针来源 | 将 Sky 的目标机挂载经验合并到 Pixel A17 vendor_boot；把 Sky 的结构用于检查 10S 目标关系 | 当前 v04 不再把 Sky vendor/odm 作为实际 A17 provider；Sky boot、vendor_boot、dtbo、固件不直接替代当前 Pixel A17 启动候选 |
| 官方 HyperOS 1.0.4.0 | 10S 原厂分区名称、容量、A/B/virtual A/B、super/metadata、Fastboot 和回退事实；官方 vbmeta 公钥/布局作对照 | 没有修改官方包本身；只根据它核对候选几何、设备回退和同机刷写先例 | 官方 Android 13 system/vendor 没有直接并入 A17 候选；官方固件也不与 17U 底层混用 |

我们自己重新制作的部分，主要是“适配产物”和“验证产物”：

- 17U 上层、Pixel A17 provider、Sky mi_ext/挂载经验和 10S 分区事实的组合关系；
- 只改 fstab 的 vendor_boot_v04；
- B0 六路径最小诊断变体；
- 四个 EROFS、两个 ext4 和新的 super；
- SOURCE_MAP、哈希清单、逐文件回读和门禁报告；
- file_contexts 验证副本、linkerconfig 普通生成副本以及审计脚本。

我们没有原创以下核心内容：

- 手机 Linux 内核；
- Camera、Audio、Power、Health 等 HAL 实现；
- modem、Wi-Fi、Bluetooth 固件；
- HyperOS Framework；
- Pixel 或天空包中的原始应用和厂商二进制。

因此“原创移植”在本项目中的准确含义，是我们原创了来源选择、分层组合、启动适配、最小修改边界和验证流程，而不是从零写出一套手机操作系统。

### 12.7 我们和 Pixel、天空的方案是否类似

类似，但不是照抄任何一个方案。

| 对比对象 | 相似之处 | 不同之处 |
|---|---|---|
| Pixel thyme | 都利用同目标机的 Android 17 底层和 v3 启动链 | Pixel 是 AOSP/Lineage 风格系统；我们把 HyperOS 4 的 17U 上层嫁接进去，并重做 vendor_boot fstab |
| 天空 OS3 | 都保留 10S 目标机硬件结构，按分区而不是整包移植 | 天空当前是 HyperOS 3/Android 16；我们当前 vendor/odm 已切换为 Pixel A17，Sky 主要提供 mi_ext、EROFS/fstab 和目标机行为参考 |
| 官方 OS1 | 都必须服从 10S 的真实分区、slot、容量和回退事实 | 官方包是原厂 Android 13，不是 Android 17 供体，也不是当前 vendor provider |

因此我们的方案可以概括为：

~~~text
Sky：
  证明 10S 的 HyperOS/EROFS/mi_ext 应该怎样工作

Pixel：
  证明 10S 的 Android 17 vendor/odm/启动链可以怎样组织

17U：
  提供我们真正想移植的 HyperOS 4 上层

官方 OS1：
  规定 10S 原厂分区、固件、回退和安全边界

我们：
  把四类证据按分区和功能重新组合，再自行适配、封装和验证
~~~

这就是本项目的核心：不是“Sky 包加 Pixel 包再加 17U 包”，而是“分别取它们最适合的一层，并重新建立层与层之间的契约”。

---

## 13. Android 移植的一般工作流程

### 第一步：确定目标机事实

先确认：

- 设备型号和代号；
- SoC；
- 当前 Android 版本；
- 分区布局；
- 启动布局；
- A/B 还是单槽；
- 是否有 super；
- 当前 slot；
- boot/vendor_boot/dtbo 是否存在；
- Recovery 和回退方式。

不能只看系统设置里的名称，因为某些属性可能被 ROM 伪装。

### 第二步：准备回退

至少应准备：

- 官方目标机完整包；
- 当前可启动 ROM；
- boot、vendor_boot、dtbo、vbmeta 备份；
- 关键校准和基带相关备份；
- 明确的 Fastboot 或 Recovery 回退路径。

没有可靠回退，就不适合开始反复试刷。

### 第三步：开包和识别来源

逐个包检查：

- Android 版本；
- SDK；
- 机型属性；
- 文件系统；
- VINTF；
- SELinux 版本；
- 启动镜像版本；
- 分区和固件。

不要看到文件名相同就认为可以互换。

### 第四步：建立来源矩阵

对每个分区或功能写清楚：

| 内容 | 来源 | 原因 |
|---|---|---|
| system | 17U，已换 thyme/sm8250-common A17 设备矩阵 | HyperOS 4/Android 17 系统上层 |
| system_ext/product | 17U，保留并审计 HyperOS 私有功能 | HyperOS Framework 扩展和产品层 |
| vendor/odm | Pixel thyme Android 17 | 当前 A17 硬件服务、HAL、VINTF 和 SELinux provider |
| mi_ext | 天空 OS3 10S | 目标机扩展路径和属性 |
| boot/dtbo | Pixel thyme | 目标机 Android 17 启动候选 |
| vendor_boot | Pixel thyme，重新适配 fstab | 同时满足 A17 ramdisk 和 10S EROFS/mi_ext 挂载 |
| vbmeta | Sky flags=2 诊断探针 | 仅作离线/解锁探针，不是生产 AVB |
| firmware | 10S/天空/官方包作参考 | 不能跨平台使用 17U 固件 |

### 第五步：离线检查

至少检查：

- 镜像是否完整；
- 分区大小；
- EROFS/ext4 是否正确；
- fstab 是否能挂载实际分区；
- VINTF 是否兼容；
- SELinux 是否能编译或加载；
- HAL 动态库和服务是否存在；
- init 脚本是否引用了不存在的路径；
- linker namespace 是否允许跨分区加载；
- AVB 头和哈希是否自洽。

### 第六步：制作候选包

重新生成：

- 文件系统镜像；
- super；
- vendor_boot；
- vbmeta 或测试用验证配置；
- Fastboot 或 Recovery 需要的外层结构。

候选包必须有来源清单和 SHA-256，避免刷错文件。

### 第七步：第一次启动

第一次启动只验证最基本的内容：

- 能否进入启动动画；
- 是否能进入系统；
- 是否能 adb；
- boot_completed 是否出现；
- 显示和触控是否工作；
- 是否出现持续重启；
- 是否能进入 Recovery/Fastboot 回退。

“亮 logo”不等于系统成功，“能进桌面”也不等于相机、电话、指纹、加密都正常。

### 第八步：按层调试

不要一看到功能异常就随便替换文件。先判断问题属于哪一层：

| 现象 | 优先怀疑 |
|---|---|
| 完全不亮、立刻重启 | boot、内核、dtbo、vbmeta、硬件固件 |
| 卡在第一屏 | vendor_boot、fstab、挂载、AVB |
| 卡开机动画 | init、SELinux、动态库、system_server |
| 能进桌面但无声音 | audio HAL、音频驱动、策略配置 |
| 能显示但无触控 | dtbo、触控驱动、Input HAL |
| 相机黑屏 | camera HAL、传感器驱动、SELinux、供应商库 |
| 充电或反向充电异常 | power/health HAL、内核充电驱动、策略 |
| Recovery 无法解密 | metadata、加密参数、Keymaster、fstab |

---

## 14. 和 STM32/K230 经验最容易混淆的地方

### “有驱动”不代表“Android 能用”

STM32 中只要初始化 GPIO、SPI 和传感器，应用就能直接调用。

Android 中可能要同时满足：

1. 内核驱动存在；
2. 设备节点正确；
3. vendor 库存在；
4. HAL 服务能启动；
5. VINTF 接口版本匹配；
6. SELinux 允许访问；
7. Framework 知道如何调用；
8. 相关权限和配置完整。

### “能编译”不代表“能启动”

Android ROM 大多使用预编译二进制。文件能放进镜像，不代表：

- 动态链接器能找到依赖；
- init 能启动它；
- SELinux 允许它；
- Binder 服务能注册；
- Framework 会使用它。

### “同机型”也不代表“同一底层”

两个包都写着 thyme，仍然可能有不同的：

- Android 版本；
- 内核版本；
- VINTF target-level；
- SELinux policy；
- HAL 版本；
- fstab；
- 分区文件系统；
- 加密方式；
- 服务实现。

因此 Pixel 包只能作为参考和候选来源，不能默认整包照搬。

---

## 15. 建议你的学习顺序

你不需要一开始就学完整 Android 源码。建议按下面顺序：

### 第一阶段：Linux 和刷机基础

- Linux 文件权限；
- 进程和线程；
- mount、fstab；
- 动态链接库；
- ELF；
- adb、fastboot；
- logcat、dmesg。

### 第二阶段：Android 启动和分区

- boot、vendor_boot、dtbo；
- super 和动态分区；
- A/B 和 slot；
- AVB/vbmeta；
- EROFS/ext4；
- init.rc。

### 第三阶段：Android 系统接口

- Framework；
- system_server；
- Binder；
- AIDL/HIDL；
- HAL；
- VINTF；
- SELinux。

### 第四阶段：硬件移植

- Linux 设备树；
- 内核驱动；
- vendor blob；
- Camera HAL；
- Audio HAL；
- Power/Health HAL；
- 显示和触控；
- modem、Wi-Fi、Bluetooth。

### 第五阶段：源码级开发

- Android Build System；
- Soong/Blueprint；
- AOSP；
- Kernel build；
- sepolicy 编译；
- vendor 定制；
- AIDL HAL 实现。

---

## 16. 一页记忆版

### Android 移植最核心的关系

~~~text
system / Framework
  想调用某个硬件接口
        ↓
VINTF 约定接口是否存在
        ↓
HAL 服务是否注册
        ↓
SELinux 是否允许访问
        ↓
vendor 动态库是否齐全
        ↓
Linux 内核驱动是否存在
        ↓
硬件是否真的工作
~~~

### 当前项目的一句话

> 17U 提供 HyperOS 4 / Android 17 上层，Pixel thyme 提供 Android 17 目标机底层参考，天空和官方 10S 提供目标硬件的结构、挂载、固件与回退基础；最终通过 VINTF、SELinux、启动链和实机日志把它们适配成一套系统。

### 最重要的三条原则

1. 不要把“能开机”理解成“所有功能兼容”。
2. 不要把“同名分区”理解成“可以直接互换”。
3. 不要在没有回退路径和离线检查的情况下试刷。

---

## 17. 常见术语速查

| 术语 | 含义 |
|---|---|
| ROM | 一整套 Android 系统包，也常泛指刷机包 |
| 供体 | 提供某部分文件或功能的来源系统 |
| 底包 | 目标设备的基础 ROM/硬件适配包 |
| 上层 | system、system_ext、product、Framework、应用 |
| 底层 | 内核、boot、vendor、HAL、固件、启动和权限体系 |
| 开包 | 解压和拆分 ROM |
| 打包 | 重新生成镜像、super、刷机包 |
| HAL | Android 硬件抽象层 |
| VINTF | Framework 与 vendor 的接口兼容性合同 |
| SELinux | Android 强制访问控制策略 |
| Binder | Android 进程间通信机制 |
| AIDL/HIDL | Android 服务接口描述方式 |
| AVB | Android Verified Boot |
| vbmeta | AVB 验证元数据 |
| super | 动态分区容器 |
| EROFS | Android 常用只读文件系统 |
| dtbo | 设备树覆盖层 |
| firmware | modem、DSP、蓝牙等硬件固件 |
| A/B | 双槽启动和无缝更新机制 |
| slot | 当前启动槽位，如 slot_a、slot_b |
| fastboot | Bootloader 通信和刷写工具 |
| Recovery | 独立的维护和刷机环境 |

---

## 18. 为什么要做这么多轮测试：不是盲目修 Bug

之前的工作有“试错”成分，但不是看到哪里不顺眼就随便改文件、随便刷。因为 Android 开机失败通常发生在很多层的交界处，单看“卡 Logo”无法直接知道是内核、启动链、挂载、AVB、系统分区还是数据加密。

我们采用的是“假设—单变量—实测—对照”的方法：

```text
提出一个可能原因
        ↓
只改变一个变量，其他分区尽量保持不变
        ↓
写入前重新确认设备、槽位、容量和文件 SHA-256
        ↓
只执行一次受控重启
        ↓
观察 Fastboot、Recovery、ADB、boot_completed
        ↓
根据结果降低或保留某个原因的优先级
```

这里的“单变量”很重要。例如：

- 只刷 `super`，可以观察 Android 用户空间变化的影响；
- 只刷 `vendor_boot`，可以观察 fstab/first-stage init 的影响；
- 只执行 `set_active a`，可以观察 A 槽失败标志是否阻止启动；
- 用天空完整系统做基线，可以判断手机硬件和原生启动链是否正常；
- 只格式化 `userdata`，可以判断旧数据是否是失败原因。

### 测试结果应该怎样理解

- Fastboot 返回 `OKAY`：只说明 Bootloader 接受了传输和写入，不说明 Android 能启动。
- 重启后仍在 Fastboot：说明本次启动没有完成，但不能单独说明具体是哪一个文件错了。
- 出现 Recovery 或 ADB `unauthorized`：说明启动比“立即回 Fastboot”更深入了一些，但还不能称为 Android 正常启动。
- ADB 变成 `device`，并且 `sys.boot_completed=1`：才可以确认 Android 已完成基本启动。
- 能进桌面：只证明基本启动成功，相机、电话、音频、指纹、充电和加密仍要另外验证。

### 这些测试实际排除了什么

1. `set_active a` 后，A 槽失败标志被清除，并一度能进入 Recovery/出现 ADB `unauthorized`。这说明槽位状态确实影响启动路径，但它不是完整根因。
2. 只修改 `/metadata` 的 fstab 参数，结果仍然回 Fastboot。因此 metadata fstab 不是唯一或充分原因。
3. 只移除 fstab 中的 AVB token，结果仍然回 Fastboot。因此“这几个 AVB 挂载参数”本身不是充分原因。
4. Android 17 `super` 分别配 Pixel 启动链和天空启动链都失败，说明 Pixel 启动链可能有风险，但不能把全部问题归咎于 Pixel 启动链。
5. 天空原生 `super` 配天空原生启动链能够启动到 `boot_completed=1`，说明手机硬件、天空原生系统和天空原生启动链至少能形成可工作的组合。
6. 保留天空启动链，只把 Android 17 hybrid `super` 换进去仍然失败，说明问题主要集中在 Android 17 用户空间与目标机启动链之间的组合兼容性，不能简单归因于手机坏了。
7. 对同一个 hybrid `super` 格式化 `userdata` 后仍然回 Fastboot，说明旧 userdata 不是这次早期启动失败的充分原因。

所以目前不能说“已经找到一个确定 Bug”。更准确的说法是：我们已经把问题从“什么都可能”缩小到了 Android 17 hybrid 组合中的启动合同，包括 `super` 内容、boot/vendor_boot、AVB、fstab/fs_mgr、VINTF、SELinux、HAL、动态 linker 和 `mi_ext` 等，还需要继续逐项闭合。

这也不是纯粹的“修 Bug”过程。前几轮主要是在定位故障层，后续才会针对证据最强的具体问题制作修复变体。期间曾经因为任务状态显示滞后，重复回放过一次同样的 metadata 候选；那次没有产生新信息，已明确排除，不能算一次新的成功或失败证据。

---

## 19. 本项目已经做过的主要实机测试

下面只记录对判断移植问题有价值的测试；普通文件查看、哈希重算和主机离线审计没有全部列入。完整报告位于项目的 `work/reports/` 目录。

| 时间/轮次 | 实际改变的内容 | 结果 | 它告诉我们的事情 |
|---|---|---|---|
| 2026-09-11 B0 首测 | A 槽写入 `super`、`boot_a`、`vendor_boot_a`、`dtbo_a`、`vbmeta_a`、`vbmeta_system_a` 六项 | 六项全部 `OKAY`；重启后 Logo/黑屏循环，回 Fastboot | B0 传输成功，但 Android 17 首启失败；根因未确定 |
| Round-1 D2 super | 只写 Android 17 D2 `super` | sparse 11/11 成功；重启立即回 Fastboot，A 槽失败标志未变 | 可能存在槽位状态或更早的启动阻断 |
| Round-2 slot active | 不换镜像，只执行 `set_active a` 后重启 | A 槽失败标志被清除；出现 ADB `unauthorized`/PixelOS Recovery，但没有 `boot_completed` | 槽位状态确实有影响，但仍未完整启动 |
| Recovery 观察 | 用户在 Recovery 里选择 `Reboot system now` | Logo/黑屏循环，随后回 Fastboot；A 槽又被标记为失败 | A 槽确实尝试启动过，但早期启动失败 |
| Round-3 metadata fstab | 只替换 `vendor_boot_a` 中 `/metadata` 的挂载参数 | 写入成功；重启约 65 秒后回 Fastboot，无 ADB | metadata fstab 单独修改没有解决问题 |
| Round-3 重复回放 | 因状态显示滞后，重复同一个 metadata 候选 | 仍回 Fastboot | 没有新变量，不能算新的因果证据 |
| Round-4 AVB fstab | 只移除若干 fstab AVB token，其他内容不变 | 重启后仍回 Fastboot | 这些 AVB token 不是充分根因 |
| Round-5 Sky 启动链 | 写入天空原生 `boot/vendor_boot/dtbo/vbmeta/vbmeta_system`，保留 Android 17 D2 `super` | 五项写入成功，但仍回 Fastboot | 换成目标机原生启动链仍不能让 Android 17 super 启动 |
| Round-6 原生天空基线 | 写入天空原生 `super`，并保留天空原生启动链 | 后续 ADB 变为 `device`，`boot_completed=1`，Android 16 天空系统启动，数据当时仍在 | 天空原生系统、硬件和原生启动链可以正常工作 |
| Round-7 | 计划测试 hybrid `super`，但写入前 Fastboot 未稳定枚举 | 设备动作计数为 0 | 这是安全门禁停止，不是启动失败测试 |
| Round-8 hybrid super | 只把 Android 17 hybrid `super` 写回，保留天空启动链 | 9/9 sparse chunks 成功；重启立即回 Fastboot，无 ADB/Recovery | Android 17 hybrid 用户空间仍然不能启动 |
| Round-9 clean-data | 保留同一个 hybrid `super`，只格式化 `userdata` 后重启 | 仍然回 Fastboot | 旧 userdata 不是充分根因；此轮之后 userdata 已被格式化 |

### 这些轮次之间最重要的对照

```text
天空 super + 天空启动链
        → Android 16 启动成功

Android 17 super + 天空启动链
        → 回 Fastboot

Android 17 super + Pixel 启动链
        → 回 Fastboot
```

这组对照说明：

- “手机硬件完全坏了”不是当前最合理解释；
- “只要把 Pixel 启动链换成天空启动链就一定好”也不成立；
- 当前最值得继续分析的是 Android 17 `super` 与 10S 启动环境之间的兼容合同，而不是继续盲目替换整包。

注意：Round-6 的“数据还在”发生在格式化之前；Round-9 是后来专门验证 userdata 影响而执行的格式化测试，不能把两次现场混为一谈。

主要证据文件：

- `work/reports/20260911_B0首启失败_离线根因分析.md`
- `work/reports/20260912_TRY_ROUND_1_D2_SUPER_A.md`
- `work/reports/20260912_TRY_ROUND_2_SLOT_ACTIVE_A.md`
- `work/reports/20260913_TRY_ROUND_3_METADATA_FSTAB_A.md`
- `work/reports/20260913_TRY_ROUND_4_AVB_FSTAB_A.md`
- `work/reports/20260913_TRY_ROUND_5_SKY_HW_CHAIN_A.md`
- `work/reports/20260913_TRY_ROUND_6_NATIVE_SKY_SUPER_A.md`
- `work/reports/20260913_TRY_ROUND_8_SKY_HYBRID_SUPER_A.md`
- `work/reports/20260913_TRY_ROUND_9_SKY_HYBRID_SUPER_A_CLEAN_DATA.md`

---

## 20. 当前阶段的一句话结论

我们不是在证明“某个文件改完就能开机”，而是在用受控对照实验回答三个问题：

1. 手机硬件和救援入口是否正常？——天空原生基线已经证明基本正常。
2. Android 17 用户空间能否和 10S 启动链配合？——目前还不能，多个 hybrid 组合仍回 Fastboot。
3. 具体是哪一份启动合同不兼容？——尚未完全定位，当前重点是 `super` 内容与 boot/vendor_boot、AVB、fstab/fs_mgr、VINTF、SELinux、HAL、linker、`mi_ext` 的组合关系。

因此，“刷写成功”“天空系统成功启动”和“Android 17 移植成功”是三个不同结论，不能混为一谈。
