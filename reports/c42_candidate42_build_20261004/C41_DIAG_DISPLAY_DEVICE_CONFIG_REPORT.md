# THYME-OS4 C41-DIAG：DisplayDeviceConfig 实际加载源、亮度映射参数与 K40 成功参考精确定位报告

**阶段**：C41-DIAG（纯离线深度诊断，零代码改动，零刷写操作）  
**时间**：2026-10-03  
**设备状态**：Xiaomi 10S (`[REDACTED_DEVICE_ID]`) 稳定驻留 Bootloader Fastboot（A 槽 `retry=2`, `unbootable=no`；B 槽 `retry=7`）  
**宿主空间门禁**：C=83.35 GiB, D=177.49 GiB, E=93.49 GiB（全部 > 50 GiB，门禁全绿）  

---

## Executive Summary

在 Candidate 40 取得历史性突破（Zygote 成功 fork system_server 并推进至 BootPhase 100）后，`system_server` 的 `android.display` 线程遭遇如下致命异常：
```text
FATAL EXCEPTION IN SYSTEM PROCESS: android.display
java.lang.IllegalStateException: Min or max values are invalid; raw min=0.001709819; raw max=1.0; backlight min=8.54597E-4; backlight max=1.0
    at com.android.server.display.DisplayDeviceConfig.constrainNitsAndBacklightArrays(DisplayDeviceConfig.java:2790)
    at com.android.server.display.DisplayDeviceConfig.loadBrightnessMap(DisplayDeviceConfig.java:2364)
    at com.android.server.display.DisplayDeviceConfig.initFromFile(DisplayDeviceConfig.java:2118)
    at com.android.server.display.DisplayDeviceConfig.getConfigFromSuffix(DisplayDeviceConfig.java:2075)
    at com.android.server.display.DisplayDeviceConfig.loadConfigFromDirectory(DisplayDeviceConfig.java:1130)
```

本审计任务 **C41-DIAG** 针对该异常展开全链路汇编反编译、XML 树检索、`resources.arsc` 资源解析、数学底层回溯及 K40 (`alioth`) 同架构对照，已取得 **100% 司法级确证（PROVEN）**，现将全部 11 项技术指标及分析结论完整结项汇报。

---

## 一、用户要求的 11 项技术指标闭环答复

| 序号 | 审计项 | 权威确证结论 |
| :--- | :--- | :--- |
| **1** | **实际加载文件** | `/vendor/etc/displayconfig/display_id_4630946545580055169.xml` |
| **2** | **Physical Display ID** | `4630946545580055169`（十六进制 `0x40446d58ef1f1a81`，无 stable flag 值为 `[REDACTED_LONG_ID]`） |
| **3** | **Port ID** | `129`（十六进制 `0x81`，来源于 display ID 最低字节） |
| **4** | **rawBacklight 来源** | `/vendor/etc/displayconfig/display_id_4630946545580055169.xml` 中 `<screenBrightnessMap>` 的第 1 点与第 3 点 `<value>` 标签（`0.001709819` 与 `1.0`） |
| **5** | **rawNits 来源** | 同上 XML 中 `<screenBrightnessMap>` 的 `<nits>` 标签（首点 `2.0`，中点 `500.0`，末点 `900.0`） |
| **6** | **backlightMinimum 来源** | `framework-res.apk` 中 `config_screenBrightnessSettingMinimum_hyper` (`0x010e0164` = 8) 经 `BrightnessSynchronizer.brightnessIntToFloat(8)` 运算得出 `0.000854597` |
| **7** | **backlightMaximum 来源** | `framework-res.apk` 中 `config_screenBrightnessSettingMaximum_hyper` (`0x010e0162` = 8192) 经 `BrightnessSynchronizer.brightnessIntToFloat(8192)` 运算得出 `1.0` |
| **8** | **为什么 raw_min > backlight_min** | **跨代 PWM 刻度冲突**：Framework 继承自小米 15 的 13-bit 刻度计算出下界为 `7/8191 = 0.000854597`；而 10S Vendor XML 仍使用小米 10S 原始的 12-bit 刻度计算起点为 `7/4094 = 0.001709819`。因 `0.001709819 > 0.000854597`，AOSP 断言 `mRawBacklight[0] <= mBacklightMinimum` 失败！ |
| **9** | **K40 对应配置** | K40 在 `/product/etc/displayconfig/` 中的 XML 首点明确标定为 `<value>0.000854597</value>`，完全与 HyperOS 4 框架下界一致，因此 100% 成立 |
| **10** | **当前最小修复候选** | **候选方案 A**：在 `product/etc/displayconfig/` 或 `vendor/etc/displayconfig/` 将 10S 对应 XML 的首点适配为 `<value>0.000854597</value>`（或插入 `0.0`），使得 `mRawBacklight[0] <= mBacklightMinimum` 成立 |
| **11** | **是否构建 C42** | **NO**（C41-DIAG 严格保持诊断纪律，严禁提前构建，待用户批准候选方案后再行构建） |

---

## 二、深度逆向与全链路数学证明

### 1. 致命崩溃现场的汇编级代码确证
在 `services.jar` (`classes2.dex`) 反编译代码中，`DisplayDeviceConfig.constrainNitsAndBacklightArrays()` 汇编指令如下：
```smali
27e4b0: iget-object v0, v10, mRawBacklight:[F
27e4b4: const/4 v1, #int 0
27e4b6: aget v0, v0, v1                      # v0 = mRawBacklight[0] (0.001709819)
27e4ba: iget v2, v10, mBacklightMinimum:F    # v2 = mBacklightMinimum (8.54597E-4)
27e4be: cmpl-float v0, v0, v2                # 比较 v0 与 v2
27e4c4: if-gtz v0, 00ac                      # 若 v0 > v2 则跳转到 00ac
...
27e54c: new-instance v0, Ljava/lang/IllegalStateException;
27e550: const-string/jumbo v1, "Min or max values are invalid; raw min="
...
27e594: throw v0
```
AOSP 的核心设计要求：**面板亮度曲线在低端必须能够覆盖到系统设定的最小背光值以下**（即 `mRawBacklight[0] <= mBacklightMinimum`），否则背光 Spline 插值算法在下界会发生越界。由于当前 `0.001709819 > 0.000854597`，抛出不可恢复的 `IllegalStateException`。

---

### 2. `backlight min = 8.54597E-4` 的 100% 精确数学推导
反编译 `DisplayDeviceConfig.loadBrightnessConstraintsFromConfigXml()`（`services.jar`，代码偏移 `0x27edb4`）：
1. 检查浮点资源 `config_screenBrightnessBacklightMinimum` (`0x01050152`)：
   其默认值为 `-2.0f` (`0xc0000000`)，表示未配置。
2. 代码分支进入 fallback 读取小米扩展整型资源：
   - 最小整型背光：`config_screenBrightnessSettingMinimum_hyper` (`0x010e0164` / `17695076`) = `8`
   - 最大整型背光：`config_screenBrightnessSettingMaximum_hyper` (`0x010e0162` / `17695074`) = `8192`
3. 传入 `BrightnessSynchronizer.brightnessIntToFloat(int)`：
   ```smali
   33b7e4: sget v3, BrightnessSynchronizer;.MIUI_BRIGHTNESS_ON:I  # 8192
   33b7ea: const/4 v4, #0.0f
   33b7ec: int-to-float v5, v7                                    # 8.0f
   33b7ee: const/high16 v6, #1.0f
   33b7f2: invoke-static {v4, v6, v6, v3, v5}, MathUtils;.constrainedMap:(FFFFF)F
   ```
4. `MathUtils.constrainedMap(rangeMin, rangeMax, oldMin, oldMax, value)` 计算逻辑：
   $$\text{ratio} = \frac{\text{value} - \text{oldMin}}{\text{oldMax} - \text{oldMin}} = \frac{8.0 - 1.0}{8192.0 - 1.0} = \frac{7.0}{8191.0}$$
   $$\frac{7}{8191} \approx 0.00085459650836283726\dots$$
   在 Java 单精度 IEEE 754 浮点数表示中，该值通过 `Float.toString()` 格式化为：
   $$\mathbf{8.54597E-4}$$

---

### 3. `raw min = 0.001709819` 的 100% 精确数学推导
小米 10S (`thyme`) 原厂硬件驱动使用的是 12-bit PWM 背光（取值范围 1..4095），其有效最小背光硬件点为 8。
在 12-bit 映射系统下：
$$\text{ratio} = \frac{8.0 - 1.0}{4095.0 - 1.0} = \frac{7.0}{4094.0}$$
$$\frac{7}{4094} \approx 0.001709819247679531\dots$$
四舍五入保留 9 位小数，正好就是 `/vendor/etc/displayconfig/display_id_4630946545580055169.xml` 中的标定数值：
$$\mathbf{0.001709819}$$

---

### 4. XML 加载路径与匹配仲裁
`DisplayDeviceConfig.loadConfigFromDirectory()` 的文件搜索链：
1. **Product 分区优先**：`/product/etc/displayconfig/display_id_4630946545580055169.xml`  
   - 在当前 Candidate 40 的 `product` 分区中，仅存在小米 15 自己的 `display_id_4630946639341352083.xml`，未命中。
2. **Vendor 分区兜底**：`/vendor/etc/displayconfig/display_id_4630946545580055169.xml`  
   - 成功命中！
3. 解析出的 `<screenBrightnessMap>` 节点：
   ```xml
   <screenBrightnessMap>
       <point>
           <value>0.001709819</value>
           <nits>2.0</nits>
       </point>
       <point>
           <value>0.49975574</value>
           <nits>500.0</nits>
       </point>
       <point>
           <value>1.0</value>
           <nits>900.0</nits>
       </point>
   </screenBrightnessMap>
   ```

---

## 三、K40 (`alioth`) 对照与同平台官方基准验证

通过挂载提取 K40 官方 HyperOS 4 Android 17 的镜像包，对比发现：
1. **K40 的 DisplayConfig XML 位于 `product` 分区**：
   - `/product/etc/displayconfig/display_id_4630946682710401939.xml`
   - `/product/etc/displayconfig/display_id_4630947212918452371.xml`
2. **直接读取 K40 XML 内部定义**：
   ```xml
   <screenBrightnessMap>
       <point>
           <value>0.000854597</value>
           <nits>2.0</nits>
       </point>
       <point>
           <value>0.749847393</value>
           <nits>1800.0</nits>
       </point>
       <point>
           <value>1.0</value>
           <nits>3200.0</nits>
       </point>
   </screenBrightnessMap>
   ```
   **惊人的一致性**：K40 官方在 HyperOS 4 中，其 XML 的首个采样点已经精确修改为 **`0.000854597`**！
   这与 HyperOS 4 Framework 计算出的 `mBacklightMinimum = 8.54597E-4` **完全相等（100% 对齐）**！
   因此，在 K40 上：
   $$mRawBacklight[0] \le mBacklightMinimum \iff 0.000854597 \le 0.000854597 \quad (\text{TRUE})$$
   K40 因而能够顺利通过 `constrainNitsAndBacklightArrays()` 的严格检查！

---

## 四、Candidate 42 最小单变量修复方案提案

| 方案 | 修改层级 | 具体改动 | 优点 | 缺点 |
| :--- | :--- | :--- | :--- | :--- |
| **方案 A（推荐）**<br>DisplayConfig XML 适配 | `product` 分区<br>`/product/etc/displayconfig/` | 在 `product` 分区新增 `display_id_4630946545580055169.xml`（或直接修改 vendor 中的该文件），将 `<screenBrightnessMap>` 首点调整为与 K40 官方完全一致的：<br>`<point><value>0.000854597</value><nits>2.0</nits></point>` | 1. 100% 符合 K40 官方 HyperOS 4 实现规范；<br>2. 纯 XML 文本改动，零代码风险；<br>3. 物理覆盖满足数学约束，保证 spline 插值平滑；<br>4. 不改动 vendor 原厂驱动层。 | 需要重包对应分区 |
| **方案 B**<br>Product Overlay 覆盖 | `product` 分区<br>`FrameworkResOverlayDevice.apk` | 在 RRO Overlay 中覆盖 `config_screenBrightnessBacklightMinimum` 为 `0.001709819` | 保持 vendor XML 原状 | 需要编译或打包 APK，链路较重，可能影响其他依赖该常量的系统组件 |

---

## 五、C41 阶段结项与纪律声明

1. **当前阶段**：纯诊断结项完成，所有 11 个问题全部闭环答复；
2. **设备安全**：物理机停留在 Fastboot，未发生擅自重启或写操作；
3. **下一步执行**：严格遵守不擅自构建原则，等待用户审核本报告并明确批准 C42 修复方案。
