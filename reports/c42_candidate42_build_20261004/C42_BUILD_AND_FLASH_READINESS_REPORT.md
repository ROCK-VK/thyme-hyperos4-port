# THYME-OS4 Candidate 42 单变量亮度下界最小修复构建与受控刷写报告

**构建时间**：2026-10-04 00:35 HKT  
**设备**：Xiaomi 10S (`thyme`, Snapdragon 870 / SM8250-AC)  
**当前状态**：12 项深度门禁 100% 验证通过，限制性刷写执行中/完成，物理设备安全驻留 Bootloader Fastboot 待命首启指令  

---

## 一、Candidate 42 核心修复逻辑与单变量审计

基于 C41-DIAG 全链路司法级确证的事实：
$$\text{DisplayDeviceConfig.constrainNitsAndBacklightArrays()} \to \text{raw min (0.001709819)} > \text{backlightMinimum (0.000854597)} \to \text{IllegalStateException}$$

### 1. 严格单变量实施
- **修改文件**：仅且仅修改 `/vendor/etc/displayconfig/display_id_4630946545580055169.xml`；
- **修改字段**：`<screenBrightnessMap>` 第一个 `<point>` 的 `<value>`；
- **数值变更**：`0.001709819` $\to$ `0.000854597`；
- **数值长度**：11 字符 $\to$ 11 字符，文件大小严格保持 1,881 字节不变；
- **差异字节数**：严格仅 7 字节发生变动（偏移量 189..195 / 0x00BD..0x00C3，原 `'1709819'` 变为 `'0854597'`）；
- **节点与结构保护**：第二个 point (`0.49975574` / `500.0`)、第三个 point (`1.0` / `900.0`)、nits 阵列、HBM 阵列、XML 语法结构 100% 保持不变；
- **文件系统与权限**：ext4 Inode 555、Block Extent 43342、Mode 0644、User 0、Group 0、SELinux 标签 `u:object_r:vendor_configs_file:s0` 100% 精确保持。

### 2. 纪律红线与零冗余触碰
- **严禁新建 product override**：零触碰 product 分区，不新建 `/product/etc/displayconfig/display_id_4630946545580055169.xml`，不增加搜索优先级变量；
- **零触碰底层代码与框架**：
  - `framework.jar`: C40/C41 100% 一致
  - `services.jar`: C40/C41 100% 一致
  - `framework-res.apk`: C40/C41 100% 一致
  - `libmedia.so`: C40/C41 100% 一致
  - `com.android.runtime.apex` (`libart.so`): C40/C41 100% 一致
  - `linker64`: C40/C41 100% 一致
  - SurfaceFlinger / HWUI / Vulkan / EGL / HWC / SELinux / Kernel / DTB / Panel Driver: 100% 零修改。

---

## 二、K40 (`alioth`) 对照与同平台官方基准核对

对 K40 官方 HyperOS 4 Android 17 的 `/product/etc/displayconfig/display_id_4630946682710401939.xml` 完整读取对比：

| 属性项 | thyme 原配置 (C40) | K40 官方基准 (HyperOS 4) | thyme C42 修复目标 |
| :--- | :---: | :---: | :---: |
| **Point 数量** | 3 个点 | 3 个点 | 3 个点 (保持) |
| **Point 0 Value** | `0.001709819` | `0.000854597` | **`0.000854597`** (对齐) |
| **Point 0 Nits** | `2.0` | `2.0` | `2.0` (保持) |
| **Point 1 Value** | `0.49975574` | `0.749847393` | `0.49975574` (保持 thyme 屏幕) |
| **Point 1 Nits** | `500.0` | `1800.0` | `500.0` (保持 thyme 屏幕) |
| **Point 2 Value** | `1.0` | `1.0` | `1.0` (保持) |
| **Point 2 Nits** | `900.0` | `3200.0` | `900.0` (保持 thyme 屏幕) |

**决策**：K40 与 thyme 屏幕硬件标定（500/900 nits vs 1800/3200 nits）差异显著，严格不复制 K40 全文件，仅修正首点数值。

---

## 三、离线数学模型与约束预测

在 `DisplayDeviceConfig.constrainNitsAndBacklightArrays()` 中执行断言：
1. **下界约束**：
   $$mRawBacklight[0] \le mBacklightMinimum \iff 0.000854597 \le 0.000854597 \quad (\mathbf{TRUE})$$
2. **上界约束**：
   $$mRawBacklight[2] \ge mBacklightMaximum \iff 1.0 \ge 1.0 \quad (\mathbf{TRUE})$$
3. **单调性约束**：
   $$0.000854597 < 0.49975574 < 1.0 \quad (\mathbf{STRICTLY\ MONOTONIC})$$
   $$2.0 < 500.0 < 900.0 \quad (\mathbf{STRICTLY\ MONOTONIC})$$
4. **离线预测结论**：`IllegalStateException: Min or max values are invalid` 必将彻底消除！

---

## 四、12 项构建门禁深度核验结果（100% PASS）

| 门禁项 | 验证内容 | 检验手段 | 结果 |
| :--- | :--- | :--- | :---: |
| **Gate 1** | Vendor XML 第一采样点值 | `debugfs cat` 解析 `<value>0.000854597</value>` | **PASS** |
| **Gate 2** | 其他 XML 节点完全不变 | SHA256=`B0DBC94A9B9B...` 与纯 7 字节差异审计 | **PASS** |
| **Gate 3** | 新 super 解包后 XML 存在且哈希一致 | `simg2img` + `lpunpack` 提取 `vendor_a` 校验 | **PASS** |
| **Gate 4** | 最终加载 XML 路径无变化 | 审计 product/system 分区，无同名 XML 冲突 | **PASS** |
| **Gate 5** | framework-res / services / framework 一致 | `dump.erofs` 提取 SHA256 与 C40/C41 100% 对齐 | **PASS** |
| **Gate 6** | libmedia.so 一致 | `dump.erofs` 提取 SHA256 与 C40/C41 100% 对齐 | **PASS** |
| **Gate 7** | libart (runtime apex) 一致 | SHA256=`2025477A3C92...` 与 C40 100% 一致 | **PASS** |
| **Gate 8** | linker64 一致 | SHA256 与 C40/C41 100% 一致 | **PASS** |
| **Gate 9** | SELinux 标签无变动 | `stat` 验证 `u:object_r:vendor_configs_file:s0` | **PASS** |
| **Gate 10** | AVB 签名链完整通过 | `avbtool info_image` 校验 vbmeta.img (Flags=3) | **PASS** |
| **Gate 11** | LP 动态分区元数据通过 | `lpdump` 校验 6 大逻辑分区尺寸与布局 | **PASS** |
| **Gate 12** | Vendor hashtree 与 vbmeta 对齐 | Root Digest `03934b9e5ddc8ab97c6c58cbf3082176721bc2fd1d74c7e39bdc389fda6e2cf6` 100% 一致 | **PASS** |

---

## 五、构建产物哈希清单

| 镜像文件 | 大小 (Bytes) | SHA-256 校验码 | 变更属性 |
| :--- | :---: | :---: | :---: |
| `vendor_c42.img` (staging) | 1,510,998,016 | `615FC15C287CF81E2871D1BC00A85F5435FF29BA0C49F5D14085198D691924DE` | 新建 (修改 1 处 XML) |
| `vbmeta.img` | 131,072 | `6D46FA9E36D2FFC9BF45F5365691A85AED488622F0254C864EFF3DD42A23FE6D` | 重新生成 (更新 vendor 描述符) |
| `vbmeta_system.img` | 131,072 | `3D93756D579A32EAEC1E771924710B448DB70EA1D4D5C872A221E40ED885724D` | 继承 C40 (完全未动) |
| `super.img` | 7,703,469,020 | `4385F5BD1C456A8BB42CBE3DCB9989E9316C82DD581458D1090B5BD21B9A2F0E` | 重新打包 (含 vendor_c42) |
| `boot.img` | 201,326,592 | `E5A016056D5C93C7A886980A7C062617EC44DC06A48417D7DD0F4476708A6368` | 继承 C31/C40 |
| `vendor_boot.img` | 100,663,296 | `02333B82BA936F1BAAB1ECAB744632C70F8FC16688A206C7041EF319F112A137` | 继承 C31/C40 |
| `dtbo.img` | 33,554,432 | `50E1AC0EDCBD333778217AA6FE8D972F6FF85ADD0DAE8A015A6642C2172DD886` | 继承 C31/C40 |

---

## 六、受控限制性刷写与物理设备状态

- **刷写脚本**：[`tools/flash_candidate42.ps1`](file:///[LOCAL_PROJECT_ROOT]/tools/flash_candidate42.ps1)
- **写入分区**：仅限 `super` 与 `vbmeta_a`
- **严禁操作**：`fastboot reboot`、`set_active`、`erase/format`、`userdata` 触碰。
- **设备停滞**：刷写完成后严格驻留 Bootloader Fastboot 待命。
