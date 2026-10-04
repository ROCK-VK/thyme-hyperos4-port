# THYME-OS4 C38-DIAG 构建、验证与受控刷写就绪报告

**报告时间**：2026-10-03 11:45 HKT  
**项目目标**：Xiaomi 10S（`thyme` / Snapdragon 870）移植 Xiaomi 15 HyperOS 4 / Android 17  
**当前里程碑**：**C38-DIAG（Real Zygote `abort()` Caller 原位捕获）**  
**核心目标**：从 `abort()` 活跃栈帧 `[x29 + 8]`（`sp + 0x88`）捕获真实 Native 调用者，彻底获取 Caller 模块归属、函数偏移与 callsite。

---

## 一、当前设备与环境状态

1. **设备物理状态**：
   - 设备：Xiaomi 10S（`thyme` / Snapdragon 870 / serial: `[REDACTED_DEVICE_ID]`）
   - 模式：`Bootloader Fastboot`（实时确认）
   - 槽位状态：
     * `current-slot`: `a`
     * `slot-retry-count:a`: `5`（健康良好）
     * `slot-unbootable:a`: `no`
     * `slot-successful:a`: `no`
     * `slot-retry-count:b`: `7`
     * `slot-unbootable:b`: `no`
   - **严格纪律**：未执行 `fastboot reboot`、`erase`、`set_active` 或切换槽位，设备安全驻留 Fastboot。

2. **宿主存储空间门禁**（全部高于 50 GiB）：
   - C 盘：`86.98 GiB`
   - D 盘：`182.28 GiB`
   - E 盘：`124.97 GiB`
   - WSL 根分区：`867 GiB`
   - Docker 容器与虚拟盘：保持零接触。

---

## 二、C38-DIAG 核心技术实现与静态验证

### 1. 核心数学机理与 PAC 防御
- **栈帧数学**：`libc.so 0x7bd70 <abort>` 开辟 176 字节栈帧（`sub sp, sp, #0xb0`），在 `sp + 128` 处执行 `stp x29, x30, [sp, #128]`，随后 `add x29, sp, #0x80`。因此现场 `x29` 指向 `sp + 128`，进入 `abort()` 时的父级调用者 `LR/x30` 100% 存放在 `[x29 + 8]`（即 `sp + 136`），处于栈帧安全范围内。
- **PAC 防御**：Snapdragon 870（Kryo 585，ARMv8.2-A）无硬件 FEAT_PAuth 特性，`paciasp`（`HINT #25`）等价于 `NOP`。Stub 读取原始 `caller_lr_pac` 后，使用 `ubfx x15, x14, #0, #48` 清除高 16 位得到 canonical `caller_lr`，并计算 `caller_callsite = caller_lr - 4`。
- **双重严格断言**：Stub 仅在 `x29 - sp == 0x80` 且 `(pc & 0xfff) == 0xe10` 时解引用 `[x29 + 8]` 并输出 `C38_ABORT_CALLER`；若不满足（非 Real Zygote abort），直接返回原 handler，绝不产生非法内存访问。

### 2. 纯 Python 精确 ARM64 指令编码与反汇编交叉验证
- 脚本：[`tools/encode_c38_instructions.py`](file:///[LOCAL_PROJECT_ROOT]/tools/encode_c38_instructions.py)
- 代码空间：使用 `0x09c9c0`（`BinaryExpr::printLeft`，1348 字节超大死代码洞穴），占用前 208 字节（52 条指令）。
- 编码方式：通过纯 Python 位运算计算分支偏移（`b 0x09c9c0` = `0x17fe30b3`，`b 0x1106f8` = `0x1401cf1b`，`bl 0x7338c` = `0x97ff5a5d` / `0x97ff5a41`），彻底消除了外部 GNU 汇编器双重重定位累加偏差。
- `aarch64-linux-gnu-objdump` 反汇编比对结果：52 条指令所有分支跳转点、PC-relative `adrp` 及 AAPCS64 传参 100% 严密。

### 3. 15 项静态验证门禁 15/15 PASS
脚本：[`tools/build_and_verify_c38_linker.py`](file:///[LOCAL_PROJECT_ROOT]/tools/build_and_verify_c38_linker.py)
- **Gate 1 [PASS]**: 文件大小严格恒定 `2,473,488` 字节
- **Gate 2 [PASS]**: ELF Header 100% Identical
- **Gate 3 [PASS]**: Program Headers 100% Identical（12 segments）
- **Gate 4 [PASS]**: Section Headers 100% Identical（30 sections）
- **Gate 5 [PASS]**: Dynamic Table（`.dynamic`）100% Identical
- **Gate 6 [PASS]**: Symbol Table（`.dynsym` / `.symtab`）100% Identical
- **Gate 7 [PASS]**: Relocation Tables 100% Identical
- **Gate 8 [PASS]**: `.rodata` 差异严格收敛在 `[0x6000, 0x60d3)`（211 字节原 MTE 废弃空间，`FMT_C37` @ 0x6000, `FMT_C38` @ 0x6060）
- **Gate 9 [PASS]**: `trampoline` 在 `0x1106f4` 严格为 4 字节，金丝雀保护指令未变动
- **Gate 10 [PASS]**: `stub` 在 `0x09c9c0` 占用 208 字节，未越出 `BinaryExpr` 边界
- **Gate 11 [PASS]**: AAPCS64 栈帧与 16 字节对齐保持，`x19-x28` 被调保存寄存器 0 破坏
- **Gate 12 [PASS]**: 异步信号安全性确认（0 堆分配、0 锁、0 格式化库引入）
- **Gate 13 [PASS]**: 跳板反汇编为 `b 9c9c0`
- **Gate 14 [PASS]**: 桩出口反汇编为 `b 1106f8`
- **Gate 15 [PASS]**: 死代码隔离审计（外部无跳入点）
- **产物**：`/path/to/thyme-os4-build/linker64_c38_patched`，SHA256: `55cfddd9fa0d72448ef27908599c61885dedf11c20940a12ce4cb328a5c40939`。

---

## 三、Candidate 38 构建与六重验收入库

脚本：[`tools/build_candidate38_diag.py`](file:///[LOCAL_PROJECT_ROOT]/tools/build_candidate38_diag.py)
1. **APEX 重构与签名**：
   - 替换 `bin/linker64` 为 C38 patched 版本；
   - `mkfs.erofs` + `avbtool add_hashtree_footer` 签名 payload；
   - Windows `apksigner.bat` 完成 APK Signature Scheme v3 签名，`apksigner verify` 返回 `true`；
   - 产物：`com.android.runtime.apex`（12,981,001 字节，SHA256: `F0FCE421C7FB38F0FDBE3EAD794FA7FF469BF7FEA69BC86BDCA03C264216F3BD`）。
2. **系统树差异（Tree Delta）**：
   - 相较于 C32 基线系统树，差异严格仅有 **1 个文件**：`system/apex/com.android.runtime.apex`；
   - `removed: []`, `added: []`, `modified: [system/apex/com.android.runtime.apex]`。
3. **镜像生成与验收入库**：
   - `system_c38_diag.img`：1,092,616,192 字节，SHA256: `592B587B540767E70EB1FA5A79C88F24093F152D6CCABC060B36B9F6B3534116`
   - `vbmeta_system.img`：131,072 字节，SHA256: `BBBF8F3BE3C82791074AA468EAA7B3D16582043AB51BCB08D16306259EE7E180`
   - `super.img`：7,703,469,016 字节，SHA256: `CC25068C99A83953F30F352B5A354227DD1FB76BA5CDB2D2528571D43E9008F2`
4. **构建后验证门禁**（[`tools/verify_candidate38.py`](file:///[LOCAL_PROJECT_ROOT]/tools/verify_candidate38.py)）：
   - AVB 描述符检验通过（system, system_ext, product）；
   - LP 动态分区元数据完整包含 6 个分区；
   - **关键验证**：从 `super.img` 内部完整解出 `system` $\to$ 解出 `com.android.runtime.apex` $\to$ 解出 `bin/linker64`，其 SHA256 确证 100% 恒等于 `55cfddd9fa0d72448ef27908599c61885dedf11c20940a12ce4cb328a5c40939`！

---

## 四、受控实机刷写记录

脚本：[`tools/flash_candidate38_diag.ps1`](file:///[LOCAL_PROJECT_ROOT]/tools/flash_candidate38_diag.ps1)  
日志：`reports\c38_diag_candidate38_build_20261003\C38_DIAG_FLASH_20261003_033500_876.txt`

```text
[CMD] fastboot devices -l -> [REDACTED_DEVICE_ID] fastboot
=== PRE-FLASH DEVICE AND A/B STATE ===
product=thyme, current-slot=a, unlocked=yes, is-userspace=no, slot-retry-count:a=5, slot-retry-count:b=7

Sending sparse 'super' 1/10 ~ 10/10 (7.7 GB) -> OKAY [191.173s]
Sending 'vbmeta_system_a' (128 KB)           -> OKAY [12.372s]

=== POST-FLASH DEVICE AND A/B STATE ===
product=thyme, current-slot=a, unlocked=yes, is-userspace=no, slot-retry-count:a=5, slot-retry-count:b=7
C38-DIAG flash completed. Only super and vbmeta_system_a were written.
Device remains in Bootloader Fastboot. No reboot, set_active, erase, or other partition operation was issued.
```

---

## 五、下一步操作规划（等待用户指令）

当前工作区代码、构建产物与物理设备已完全处于 **100% 同步就绪状态**。

下一步实机验证流程：
1. **用户下达开机指令**（如“开始启动 C38”）；
2. 启动只读监视器并执行受控首启命令：
   ```powershell
   tools\start_candidate38_observed_boot.ps1 -RunDir <obs_dir> -Serial [REDACTED_DEVICE_ID] -Execute -UserWatchingConfirmed
   ```
3. 实机出现第一屏小米 Logo 常亮时，由用户手动长按按键带回 Fastboot；
4. 运行 Standalone RAM 导出 DDR 内存 `pmsg-ramoops-0`；
5. 提取 `C38_ABORT_CALLER` 日志行：
   ```text
   C38_ABORT_CALLER pid=... tid=... pc=0x... sp=0x... fp=0x... pac=0x... lr=0x... callsite=0x...
   ```
6. 执行符号化与模块映射定位，权威锁定 Real Zygote abort 的真实第一现场根因模块。
