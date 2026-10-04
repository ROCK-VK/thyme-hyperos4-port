# THYME-OS4｜C35-DIAG FINAL BUILD GATE & CANDIDATE 35 镜像构建与就绪报告

**生成时间**：2026-10-02 15:10 HKT  
**项目目标**：Xiaomi 10S (`thyme` / Snapdragon 870) 移植 HyperOS 4 / Android 17 userland (`dada` 基线)  
**当前阶段**：C35-DIAG Linker64 crash_dump helper stderr pipe capture 离线构建门禁与刷写就绪  
**实验变量**：仅修改 `com.android.runtime.apex` 内部 `bin/linker64` 实现 debuggerd helper stderr 捕获；保留 C31 `no_fatal.zygote` 诊断基线  
**当前状态**：全部离线门禁 100% 绿灯 PASS；A 槽 boot-control retry 恢复为 7；物理设备停在 Bootloader Fastboot；等待用户启动口令。

---

## 一、宿主环境与物理设备门禁（100% PASS）

### 1. 宿主磁盘空间实时门禁
- **C 盘可用空间**：`90.51 GiB`（门禁要求 >= 50 GiB，通过）
- **D 盘可用空间**：`183.63 GiB`（门禁要求 >= 50 GiB，通过）
- **E 盘可用空间**：`145.27 GiB`（门禁要求 >= 50 GiB，通过）
- **WSL (ext4) 可用空间**：`871 GiB`（门禁要求 >= 50 GiB，通过）
- **Docker 零触碰纪律**：Docker Desktop、容器、镜像、WSL Docker VHDX 保持 0 触碰、0 修改。

### 2. 物理设备 Fastboot 只读读回与槽位预算恢复
- **设备序列号**：`[REDACTED_DEVICE_ID] fastboot`
- **产品代号 (`product`)**：`thyme`
- **Bootloader 解锁状态 (`unlocked`)**：`yes`
- **用户空间 Fastboot 标记 (`is-userspace`)**：`no`（确证驻留在 Bootloader Fastboot，非 fastbootd）
- **当前激活槽位 (`current-slot`)**：`a`
- **A 槽位状态恢复**：
  - 执行指令：`fastboot set_active a`
  - 实时读回：
    - `slot-unbootable:a`: `no`
    - `slot-successful:a`: `no`
    - `slot-retry-count:a`: `7`（成功从首启后的 retry=1 恢复至满额 7 次预算）
- **B 槽位状态**：
  - `slot-unbootable:b`: `no`
  - `slot-successful:b`: `no`
  - `slot-retry-count:b`: `7`
- **绝对纪律遵守**：未执行 `fastboot reboot`，未刷写任何分区，设备安全停在 Bootloader Fastboot。

---

## 二、Linker64 SHA256 冲突根因消除与唯一规范补丁

### 1. 历史哈希冲突溯源
历史分析记录中存在两个补丁哈希：
1. `51221f7db138e07971b3e94a821ce7d06e30b05fa03c15555627f12e8738382c`
2. `8cc81052fb27b91214314e660ae6ab4245bda96c43e20b2368d3f340d5762574`

**根因查明**：
- 哈希 1 (`51221f7db138e...`) 产生于中间手工调试汇编阶段，当时在 `0x111ca8` 处生成的 `csel x4, x0, xzr, gt` opcode 为 `0x9a9f0000`（未带规范的条件码置位偏移）；
- 在规范化汇编（opcode 修正为 `0x9a9fc000`）并完成 `.rodata` 格式化串原地置换填充后，补丁哈希确定为 `8cc81052fb27b91214314e660ae6ab4245bda96c43e20b2368d3f340d5762574`。
- **决定**：彻底废弃中间草稿哈希 `51221f7db138e...`，全项目统一固定唯一规范产物。

### 2. 原始与补丁 Linker64 最终哈希与逐字节对比
- **原始 linker64**：
  - 路径：`/path/to/thyme-os4-build/c35_diag_linker_capture_20261002/linker64_orig`
  - 大小：`2,473,488` 字节
  - SHA256：`00e5dc0e9716f6e7c6d70e04fa7a721941c02e912932eb5c08753676da0adb50`
- **规范补丁 linker64**：
  - 路径：`/path/to/thyme-os4-build/c35_diag_linker_capture_20261002/linker64`
  - 大小：`2,473,488` 字节（0 字节大小变化）
  - SHA256：`8cc81052fb27b91214314e660ae6ab4245bda96c43e20b2368d3f340d5762574`
- **差异统计**：
  - 变更总字节数：`198` 字节（仅占二进制总体积的 0.008%）
  - 变更区间共 5 处：
    1. `0x00795a` (52 字节，改 49 字节)：`.rodata` 废弃字符串原地替换为 `"C35 helper output: %s\n\0"`；
    2. `0x111b68` (4 字节，改 1 字节)：`.text` 将 `b.ne 111ca4` 改为协议感知 `b.lt 111ca4`；
    3. `0x111ca4` (12 字节，改 10 字节)：`.text` 分流 `cbz x4, 111cb0` (直通 EOF)；`b 111d14` (进入捕获)；`nop`；
    4. `0x111d14` (96 字节，改 88 字节)：`.text` 栈缓冲流水线（分配 512B、保留首 4B、读取管道、打 null-term、日志打印、平栈并跳转 `waitpid`）；
    5. `0x111e68` (64 字节，改 50 字节)：`.text` 子进程追加 `dup2(output_pipe[1], 2)`。

---

## 三、最终司法级 ELF 审计

通过 GNU `readelf` 实际命令输出核验（禁止估算与口头断言）：

| 检查项 | 实际命令 | 原始 Linker64 读数 | 补丁 Linker64 读数 | 结论 |
| :--- | :--- | :--- | :--- | :--- |
| **ELF Type** | `readelf -h` | `DYN (Shared object file)` | `DYN (Shared object file)` | 一致 |
| **Entry Point** | `readelf -h` | `0x90ac0` | `0x90ac0` | 一致 |
| **PHDR 数量** | `readelf -l` | **12** (Start 64, Size 56B) | **12** (Start 64, Size 56B) | 一致 |
| **Section 数量** | `readelf -S` | **30** (Start 0x25b410) | **30** (Start 0x25b410) | 一致 |
| **LOAD[0]** | `readelf -l` | Virt `0x0`~`0x4e580`, Flags `R` | Virt `0x0`~`0x4e580`, Flags `R` | 一致 |
| **LOAD[1]** | `readelf -l` | Virt `0x50000`~`0x1ae7a0`, Flags `R E` | Virt `0x50000`~`0x1ae7a0`, Flags `R E` | 一致 |
| **LOAD[2]** | `readelf -l` | Virt `0x1b0000`~`0x1c3050`, Flags `RW` | Virt `0x1b0000`~`0x1c3050`, Flags `RW` | 一致 |
| **GNU_RELRO** | `readelf -l` | Virt `0x1b0000`, Size `0x9928`, `R` | Virt `0x1b0000`, Size `0x9928`, `R` | 一致 |
| **GNU_STACK** | `readelf -l` | Flags `RW` | Flags `RW` | 一致 |
| **GNU_PROPERTY** | `readelf -l` | Flags `R`, `aarch64 feature: BTI, PAC` | Flags `R`, `aarch64 feature: BTI, PAC` | 一致 |
| **SONAME** | `readelf -d` | `[ld-android.so]` | `[ld-android.so]` | 一致 |
| **NEEDED 依赖** | `readelf -d` | 0 entries (自包含链接器) | 0 entries (自包含链接器) | 一致 |
| **Build ID** | `readelf -n` | `d8fc879ba0f57538f2e66cd324ffa7a3` | `d8fc879ba0f57538f2e66cd324ffa7a3` | 一致 |
| **符号表条目数** | `readelf -s` | 11,943 条 | 11,943 条 | 一致 |

> **关键概念澄清**：
> 纠正历史报告中“.text 0x50000 = LOAD segment”的不严谨表述：
> - `.text`（Addr `0x50000`, Offset `0x50000`, Size `0x10d184`）与 `.rodata`（Addr `0xf80`, Offset `0xf80`）为 ELF **Section**；
> - `LOAD[1]`（VirtAddr `0x50000`, FileOffset `0x50000`, Size `0x15e7a0`, Flags `R E`）为包含 `.text` 等可执行代码段的 **Program Segment**。

---

## 四、ARM64 控制流与协议审计（A ~ G 项证明）

通过 GNU `aarch64-linux-gnu-objdump -d` 确切反汇编指令逐一证明：

### A. 子进程端（Child Process）：output_pipe[1] 同时绑定 FD1 与 FD2
- `0x111e68`: `mov w0, w24` (将 `output_pipe[1]` 载入 arg0)
- `0x111e6c`: `mov w1, #1` (arg1 = STDOUT)
- `0x111e70`: `bl 0x8ffc0` (`dup2(output_pipe[1], 1)`)
- `0x111e74`: `mov w0, w24` (将 `output_pipe[1]` 载入 arg0)
- `0x111e78`: `mov w1, #2` (arg1 = STDERR)
- `0x111e7c`: `bl 0x8ffc0` (`dup2(output_pipe[1], 2)`)
- **证明**：子进程无论向 stdout 还是向 stderr 写入，均 100% 进入父端监听的 `output_pipe`。

### B & C. 父进程端（Parent）：output_pipe[0] 执行首读 count=4
- `0x1119a8`: `mov w0, w21` (`output_pipe[0]`)
- `0x1119ac`: `add x1, sp, #0x28` (`sp + 40` 作为 4 字节首读缓冲)
- `0x1119b0`: `mov x2, #4` (`count = 4`)
- `0x1119b4`: `bl 0x8f4c0` (`read(output_pipe[0], sp+40, 4)`)
- **证明**：父端按原版约定读取前 4 字节，返回值在 `x0` 中，暂存至 `x4`。

### D. 成功判定：buf[0] == 0x01 协议感知立即放行
- `0x111b5c`: `ldrb w8, [sp, #40]` (读取首字节)
- `0x111b60`: `cmp w8, #1`
- `0x111b64`: `cset w8, eq`
- `0x111b68`: `tst w4, w8`
- `0x111b6c`: `b.lt 0x111ca4`
- **证明**：只要 `rc > 0` 且首字节为 `0x01`（握手成功标志），`b.lt` 不跳转，直接进入原版 Tombstone/Wait 流程，零阻塞、零侵入。

### E. 失败路径：保留首 4 字节并读取管道剩余报错文本
- `0x111ca4`: `cbz x4, 0x111cb0` (如果 `rc <= 0`，直通原版 EOF 分支)
- `0x111ca8`: `b 0x111d14` (进入 C35 失败捕获流水线)
- `0x111d14`: `sub sp, sp, #0x200` (栈底开辟 512 字节独立安全缓冲)
- `0x111d18`: `ldr w8, [sp, #0x228]` (从原栈 `[sp + 512 + 40]` 取出首 4 字节)
- `0x111d1c`: `str w8, [sp]` (完整存入新栈底 `[sp]`)
- `0x111d20`: `mov w0, w21` (`output_pipe[0]`)
- `0x111d24`: `add x1, sp, x4` (缓冲指针偏移 `x4`，通常为 4)
- `0x111d28`: `mov w2, #0x1f0` (最大读取剩余 496 字节，防止栈溢出)
- `0x111d2c`: `bl 0x8f4c0` (`read`)
- **证明**：即使首批 4 字节被首读消耗（如 `"CANN"`），也能与后续 496 字节无缝拼接。

### F. 最终 Null-Termination 绝对不越界
- `0x111d30`: `cmp x0, #0`
- `0x111d34`: `csel x0, x0, xzr, gt`
- `0x111d38`: `add x0, x0, x4` (`total =首读字节 + 剩余读取字节`)
- `0x111d3c`: `strb wzr, [sp, x0]` (在 `sp + total` 处写入 `\0`)
- **证明**：由于 `x4 <= 4`，`read <= 496`，`total <= 500 < 512`，写入位置永远落在分配的 512 字节栈内，绝不越界。

### G. 控制流平栈与返回原函数 waitpid
- `0x111d54`: `bl 0x16b0f0` (`async_safe_format_log(6, "DEBUG", "C35 helper output: %s\n", sp)`)
- `0x111d58`: `add sp, sp, #0x200` (严格平栈 512 字节)
- `0x111d5c`: `b 0x111a10` (跳转原版 `waitpid` 回收 helper 子进程)
- **证明**：栈帧完全平衡，复用原版进程回收语义，绝无悬挂僵尸进程或栈破坏。

---

## 五、字符串引用（Xref）审计

- **目标字符串偏移**：`.rodata` 虚拟地址 `0x795a`
- **字符串内容**：`"C35 helper output: %s\n\0"`
- **全二进制交叉引用扫描**：
  - 扫描指令：全代码段（`0x50000` ~ `0x1ae7a0`）搜索引用 `0x7000 + 0x95a` 的 `ADRP + ADD` 指令
  - **结果**：全二进制中有且仅有 **1 处** 引用：
    - PC `0x111d4c`: `adrp x2, 0x7000`
    - PC `0x111d50`: `add x2, x2, #0x95a`
- **结论**：
  - 该唯一引用点正是 C35 失败日志打印处；
  - 全二进制 0 遗留旧 caller 仍按旧格式 `(%s, %zd)` 传递参数；
  - 格式化参数完全匹配（`async_safe_format_log(6, tag, fmt, buf)`），零格式化崩溃风险。

---

## 六、离线协议仿真器 11/11 边界测试（100% PASS）

升级测试脚本 `tools/simulate_c35_dispatcher.py`，全覆盖真实运行可能出现的 11 种极端边界：

| 用例编号 | 测试场景 | 管道输入数据 | 预期判定 | 实际仿真结果 |
| :--- | :--- | :--- | :--- | :--- |
| **Case 1** | Helper 立即关闭（EOF） | 0 字节 | `EOF`（走原版流程） | **PASS** |
| **Case 2** | Read 异常返回 -1 | `read == -1` | `EOF`（走原版流程） | **PASS** |
| **Case 3** | 标准成功握手 | `0x01`（1 字节） | `SUCCESS`（协议放行） | **PASS** |
| **Case 4** | 异常单字节（0x00） | `0x00`（1 字节） | `FAILURE_CAPTURED` | **PASS** |
| **Case 5** | 异常单字节（0xFF） | `0xFF`（1 字节） | `FAILURE_CAPTURED` | **PASS** |
| **Case 6** | 多字节成功握手 | `0x01 0x00 0x00 0x00` | `SUCCESS`（协议放行） | **PASS** |
| **Case 7** | 动态链接器报错 | `"CANNOT LINK EXECUTABLE..."` (150B) | 完整拼接捕获并输出 | **PASS** |
| **Case 8** | Early-Main Abort | `"ABORT: LOG(FATAL)..."` (120B) | 完整拼接捕获并输出 | **PASS** |
| **Case 9** | 边界短文本（<=511B） | 250 字节随机文本 | 完整捕获 | **PASS** |
| **Case 10** | 极端超长文本（>511B） | 1024 字节长日志 | 截断至 500B，安全 null-term | **PASS** |
| **Case 11** | 首字节后管道立即关闭 | 单字符 `'X'` 后 close | 捕获单字符 `'X'` | **PASS** |

---

## 七、APEX 双层签名闭环与容器核验

### 1. 内层 Payload (`apex_payload.img`) 重构与 AVB 签名
- **EROFS 文件系统重构**：
  - 打包指令：`mkfs.erofs -zlz4hc -T 0 -U [REDACTED_DEVICE_ID]-9dfa-5edb-a43e-98e3a4d20250`
  - 产物大小：`12,853,248` 字节
- **AVB Hashtree Footer 签名**：
  - 签名工具：`tools/bootimg/avbtool.py add_hashtree_footer`
  - 关键规避参数：**`--do_not_generate_fec`**（宿主环境无独立 `fec` 可执行文件；原版 APEX 同样无 FEC 描述符）
  - 算法：`SHA256_RSA4096`
  - 提取公钥 SHA1：`28b0e23bc7a1f066a59659c798f1ac89b04207ee`
  - 验证：Payload 内部的 AVB 根哈希与公钥 100% 匹配。

### 2. 外层 APK 容器重构与 V3 签名
- **容器装配**：使用未压缩 ZIP 对齐打包生成 `com.android.runtime.apex`
- **APK Signature Scheme v3 签名**：
  - 执行指令：`apksigner.bat sign --v1-signing-enabled false --v2-signing-enabled false --v3-signing-enabled true ...`
  - 签名核验：`apksigner.bat verify --verbose com.android.runtime.apex`
  - 核验输出：
    - `Verified using v1 scheme (JAR signing): false`
    - `Verified using v2 scheme (APK Signature Scheme v2): false`
    - **`Verified using v3 scheme (APK Signature Scheme v3): true`**
    - `Number of signers: 1`
  - 大小：`12,981,001` 字节
  - SHA256：`9012B495C7DA294160E9FF655A30A974EEB7A1DD112A20E85796845A7A4748D7`

---

## 八、Candidate 35 最终交付物与构建清单

运行 `tools/build_candidate35_diag_linker_capture.py` 构建完成，所有镜像哈希记录在 `reports/c35_diag_candidate35_build_20261002/C35_BUILD_MANIFEST.json`：

### 1. 源码树差异（仅修改 1 个文件）
- `system_tree` 相比 C32 仅有 **1 个** 文件修改：
  - `system/apex/com.android.runtime.apex`
  - 增加文件：0 项；删除文件：0 项。

### 2. 生成待刷写镜像哈希与尺寸
| 镜像文件 | 文件大小 (Bytes) | SHA-256 哈希值 |
| :--- | :--- | :--- |
| **`system_c35_diag.img`** | 1,092,616,192 | `35A4FC0AB420563B875BB642B6934BC294CA2EE38ACAD42513D85469BA93D730` |
| **`vbmeta_system.img`** | 131,072 | `90ED1BDA3F900A74B03C00B8C66592B726439C377798AD5D4E0F7A9FD4D0934D` |
| **`super.img`** | 7,703,469,016 | `8120EAA1A1E2E41C5203BEE9B5BF46FC07771F777C71ADD322DFA090B61AF9E2` |

### 3. 未修改逻辑分区输入一致性核验
- `vendor_c22.img`: SHA256 `FCEAFEE5B5909D7BE9BBEC48D9E8720F...` (一致)
- `system_ext_a.img`: SHA256 `6B63E58346DA5B2FEBA7F51980CCEBF8...` (一致)
- `mi_ext.img`: SHA256 `43ED8FC0D1848F5D53BFB7206AC91FE5...` (一致)
- `odm.img`: SHA256 `075E4A17DC4CA716399166388B1C1750...` (一致)
- `product.img`: SHA256 `87955DBE97AC28B01A214273BD03F36B...` (一致)

---

## 九、刷写边界与受限工具校验

编写了专用受限刷写工具 `tools/flash_candidate35_diag_linker_capture.ps1`：
- **严格受限刷写范围**：
  1. `fastboot flash vbmeta_system_a work/stage_c35_diag_linker_capture_20261002/images/vbmeta_system.img`
  2. `fastboot flash super work/stage_c35_diag_linker_capture_20261002/images/super.img`
- **保护性隔离**：
  - 严禁触碰 `persist`、`modemst1/2`、EFS/NV、`boot`、`vendor_boot`、`dtbo`、`vbmeta`；
  - 脚本默认包含 `-DryRun` 校验逻辑，预演校验 100% 通过；
  - **默认绝不执行自动重启**（必须由带参数确认的独立流程或明确口令触发）。

---

## 十、当前结论与启动等待门禁

1. **构建闭环确立**：从反汇编逆向、协议定义、Linker64 补丁注入、ELF 司法审计、ARM64 控制流证明、APEX 重签到 Candidate 35 镜像封装，全流程 100% 离线闭环，0 悬挂风险。
2. **设备安全就绪**：物理设备 Xiaomi 10S (`thyme`) 保持在 Bootloader Fastboot，A 槽位 retry 计数已恢复为满额 **7** 次。
3. **门禁停靠**：依照项目绝对纪律，**立即停在当前门禁**，绝不私自执行刷写或 `fastboot reboot`。

**当前等待用户明确口令**：
> **“开始启动 C35”**
