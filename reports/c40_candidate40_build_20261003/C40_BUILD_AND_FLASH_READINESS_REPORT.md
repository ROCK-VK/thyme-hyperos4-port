# THYME-OS4 Candidate 40 单变量功能修复构建与刷写就绪报告

**构建时间**：2026-10-03 19:40 HKT  
**设备**：Xiaomi 10S (`thyme`, Snapdragon 870 / SM8250-AC)  
**当前状态**：构建与限制性刷写 100% 成功，物理设备安全驻留 Bootloader Fastboot 待命首启指令  

---

## 一、Candidate 40 核心修复逻辑与单变量审计

基于 C39-DIAG 实机原位捕获的铁证：
$$\text{Zygote} \to \text{MediaProfiles::getInstance()} \to \text{createInstanceFromXmlFile} \to \text{fopen(xml, "r") = NULL} \to \text{CHECK} \to \text{SIGABRT}$$

Xiaomi 定制 `libmedia.so` 读取 `ro.media.xml_variant.codecs` 构造配置文件路径：
```text
"/vendor/etc/media_profiles" + ro.media.xml_variant.codecs + ".xml"
```
由于原本此属性为空，其回退请求 `/vendor/etc/media_profiles.xml`（文件不存在），直接触发硬断言崩溃。

### 1. 严格单变量实施
- **修改文件**：仅且仅修改 `system/build.prop`；
- **追加单行**：`ro.media.xml_variant.codecs=_V1_0`；
- **命中目标**：精准匹配 vendor 分区完好存在的 `/vendor/etc/media_profiles_V1_0.xml`（56,774 字节）；
- **树差异审计**：`diff --no-dereference -r -q C39_TREE C40_TREE` 严格仅输出 1 行，差异文件总数严格为 1。

### 2. 纪律红线与零冗余触碰
- **不新增/复制任何 XML**：坚持纯属性单变量，不伪造兼容文件；
- **零触碰 vendor 分区**：原始 vendor 结构与文件树保持绝对纯净；
- **零触碰 `libmedia.so`**：不 patch 闭源二进制，利用原生设计的 variant 机制；
- **零触碰 SELinux 与图形栈**；
- **保留 C39 原位探针**：保留 C39 `linker64` 诊断探针，以便在越过 `MediaProfiles` 之后若有后续现场能实时打捞。

---

## 二、构建产物与校验摘要

| 镜像文件 | 大小 (Bytes) | SHA-256 校验码 | 变更属性 |
| :--- | :---: | :---: | :---: |
| `system_c40.img` | 1,092,616,192 | `1D6F45FF1FB0645BA95E4A133CF44196D98531F4DEBB0699D6D881641C3BBFC5` | 新建 (注入单行属性) |
| `vbmeta_system.img` | 131,072 | `3D93756D579A32EAEC1E771924710B448DB70EA1D4D5C872A221E40ED885724D` | 重新生成 (系统根哈希更新) |
| `super.img` | 7,703,469,016 | `DEDBC9EE6BC76389C4D57336D0157C4A7CFE34DC2882BF12D082E72D3F1C6F2F` | 重新打包 (含 system_c40) |

### 动态逻辑分区输入哈希校验（100% 一致）
- `vendor_c22.img`: `FCEAFEE5B5909D7BE9BBEC48D9E8720F37798DDEEBDBF193424FB3A095CBA675` (PASS)
- `system_ext_a.img`: `6B63E58346DA5B2FEBA7F51980CCEBF886D5991DD07F91541FE4D9F1485CDAD5` (PASS)
- `mi_ext.img`: `43ED8FC0D1848F5D53BFB7206AC91FE5E5ED4E3F71E958D49F2EEA4C9C8B4BCE` (PASS)
- `odm.img`: `075E4A17DC4CA716399166388B1C175060D5CBB31139B2ACBD9E5B2DEE352E22` (PASS)
- `product.img`: `87955DBE97AC28B01A214273BD03F36B5886310DC3B2E4128B9F4661E1C3345E` (PASS)

---

## 三、受控限制性刷写与物理设备状态

通过 [`tools/flash_candidate40.ps1`](file:///[LOCAL_PROJECT_ROOT]/tools/flash_candidate40.ps1) 执行限制性刷写：
- 严格仅写入目标：`super` 与 `vbmeta_system_a`；
- 绝不执行：`reboot`、`set_active`、`erase/format`、`userdata` 触碰。

### 刷写前后设备状态对照

| 参数项 | 刷写前 (Pre-Flash) | 刷写后 (Post-Flash) | 状态评估 |
| :--- | :---: | :---: | :---: |
| **设备序列号** | `[REDACTED_DEVICE_ID]` | `[REDACTED_DEVICE_ID]` | 唯一目标 |
| **Product** | `thyme` | `thyme` | 严格匹配 |
| **活动槽位** | `a` | `a` | 保持不变 |
| **Bootloader 状态** | `unlocked=yes` | `unlocked=yes` | 正常解锁 |
| **运行模式** | `is-userspace: no` | `is-userspace: no` | Bootloader Fastboot |
| **A 槽健康度** | `unbootable=no, retry=3` | `unbootable=no, retry=3` | **健康完好** |
| **B 槽健康度** | `unbootable=no, retry=7` | `unbootable=no, retry=7` | 正常备用 |

---

## 四、安全停滞与待命动作

> [!IMPORTANT]
> **设备物理安全守则执行中**：
> 物理设备当前已安全保留在 Bootloader Fastboot 模式下，**未进行任何自动重启或引导尝试**。

### 下一步指令准备
请用户在确认设备与实验环境后，明确发出指令：
> **“开始启动 C40”**

收到指令后，我们将执行受控首启流程，并随时做好 Standalone DDR RAM 打捞准备，观测 Zygote 是否顺利通过 `MediaProfiles` 初始化阶段并进入下一阶段。
