# THYME-OS4 C39-DIAG 构建门禁与刷写就绪报告

**版本**：Candidate 39-DIAG  
**阶段**：ART Runtime::Abort Level-2 Caller 与 Abort Message 原位捕获  
**日期**：2026-10-03  
**状态**：构建与静态验证 100% 全量通过，刷写流水线就绪，设备处于安全待命状态  

---

## 一、诊断目标与背景

在 C38-DIAG 里程碑中，通过原位提取 `[x29_abort + 8]` 并执行全系统二进制暴力反汇编扫描，**100% 权威确证了 Real Zygote SIGABRT 的直接终止调用路径为**：

$$\text{Real Zygote} \longrightarrow \text{art::Runtime::Abort(char const*)} \overset{0x607d3c}{\longrightarrow} \text{libc.so abort()} \longrightarrow \text{SIGABRT}$$

然而，`art::Runtime::Abort` 是 ART 虚拟机的统一终止出口，真正的触发源位于更上游的 **Level-2 Caller**，且其接收的 **`const char* msg` 错误字符串** 尚未被捕获。

**C39-DIAG 的唯一核心目标**：
1. **原位捕获 Level-2 Caller**：确定是谁调用了 `art::Runtime::Abort(char const*)`（模块、函数、callsite 偏移）；
2. **原位提取 Abort Message**：在零崩溃的前提下，完整提取 `Runtime::Abort` 收到的 `const char* msg` 具体字符串内容。

---

## 二、Runtime::Abort 内部栈帧机理与数学模型

对 `/apex/com.android.art/lib64/libart.so`（`com.android.art.capex`）的真实二进制进行了完整反汇编，确证了如下底层事实：

```assembly
0000000000607a88 <art::Runtime::Abort(char const*)>:
  607a88: paciasp                               ; PAC 签名保护
  607a8c: sub sp, sp, #0xc0                     ; 分配 0xc0 (192 字节) 栈帧
  607a90: stp x29, x30, [sp, #96]               ; 保存 Level-2 Caller 的 x29, x30
  607aa8: add x29, sp, #0x60                    ; 设置 x29_runtime = sp + 0x60
  607aac: mov x19, x0                           ; 保存 x0 (msg 指针)
  607ab0: stp xzr, x0, [x29, #-24]              ; [x29 - 16] = x0 (const char* msg)!
  607af4: ldur x19, [x29, #-16]                 ; 重新加载 msg
  607af8: mov x0, x19
  607afc: bl  Thread::AbortInThis(msg)          ; 写入 android_set_abort_message
  ...
  607d3c: bl  abort@plt                         ; 调用 libc abort() (C38 触发点)
  607d40: mrs x8, tpidr_el0                     ; 返回地址 (0x...d40)
```

### 严格栈帧数学关系：

1. **`libc abort()` 帧**：
   - 分配 `0xb0` 栈帧；
   - 现场 `x29_abort = abort_sp + 0x80`；
   - 其保存的父级 `x29` 即为 `[x29_abort] = x29_runtime`。
2. **数学不变式双重断言**：
   $$\text{x29\_runtime} - \text{x29\_abort} = 0x90 \quad (144\text{ 字节})$$
   若差值不等于 `0x90`，立即安全判定为栈帧不匹配，严禁越界解引用。
3. **Level-2 Caller LR**：
   $$\text{Level-2 Caller LR} = [\text{x29\_runtime} + 8]$$
   $$\text{Level-2 Callsite} = \text{canonical}(\text{LR}) - 4$$
4. **Abort Message 指针**：
   $$\text{msg\_ptr} = [\text{x29\_runtime} - 16]$$

---

## 三、物理级零崩溃安全字符串捕获机制

在 Linux ARM64 信号处理函数中解引用用户空间指针存在致命风险：若指针指向未映射页面，直接读取会触发二次 `SIGSEGV`，导致进程被内核强制 `SIGKILL`，导致诊断信息完全丢失。

C39 创新引入了**双重安全防御机制**：

1. **指针合法性快速过滤**：
   - `cbz x6, .Lmsg_null`：检测 NULL 指针；
   - `lsr x2, x6, #48; cbnz x2, .Lmsg_invalid`：检测高 16 位非法指针；
   - `cmp x6, 0x10000; b.lo .Lmsg_invalid`：检测低于 64KB 的 Near-NULL 指针。
2. **`sys_mincore`（系统调用 232）零崩溃物理页预检**：
   - 探测系统调用：`mincore(msg_ptr & ~0xfff, 4096, vec)`；
   - 若页面未映射在任何 VMA 中，内核直接返回错误码 `-ENOMEM`，**不会发生 CPU Page Fault，绝对不触发 SIGSEGV**；
   - 仅在系统调用返回 0（确证页面合法映射）时才允许进入读取流程。
3. **严格页内有界读取与 ASCII 净化**：
   - 最大读取长度限制为：$\min(127, 4096 - (\text{msg\_ptr} \ \& \ 0\text{xfff}))$；
   - **绝对不跨越 4KB 物理页边界**，彻底杜绝在跨页处踩到非法内存；
   - 逐字节扫描，遇到 `\0` 立即终止，并强制在末尾填充 `\0`；
   - 遇到不可打印字符（ASCII $< 32$ 或 $> 126$）自动净化为 `'?'`。

---

## 四、独立 Canary 对照基准

为确保 C39 捕获算法在真实设备上的真值校验，构建了独立 Canary：

- **源文件**：[`tools/candidate32_zygote_canary/c32_zygote_canary.c`](file:///[LOCAL_PROJECT_ROOT]/tools/candidate32_zygote_canary/c32_zygote_canary.c)
- **实现结构**：
  ```c
  __attribute__((noinline))
  void test_c39_level2_caller(art_abort_fn_t fn) {
      fn("C39_CANARY_TEST");
  }
  ```
- **NDK clang 编译产物反汇编**：
  ```assembly
  0000000000004a60 <test_c39_level2_caller>:
      4a60: sub sp, sp, #0x20
      4a64: stp x29, x30, [sp, #16]
      4a68: add x29, sp, #0x10
      4a78: adr x0, ... ; "C39_CANARY_TEST"
      4a7c: blr x8      ; 调用 Runtime::Abort! (callsite 偏移 0xa7c)
      4a80: ldp x29, x30, [sp, #16] ; 返回地址 (LR 偏移 0xa80)
  ```
- **预期基准输出**：
  `C39_RUNTIME_ABORT pid=... pc=0x...d3c lr_pac=0x...d40 caller_lr=0x...a80 callsite=0x...a7c msg_ptr=... msg=C39_CANARY_TEST`

---

## 五、C39 linker64 补丁与 15 项静态门禁验证

使用 GNU `aarch64-linux-gnu-as` 与 `ld` 完成了汇编与符号重定位，运行 [`tools/build_and_verify_c39_linker.py`](file:///[LOCAL_PROJECT_ROOT]/tools/build_and_verify_c39_linker.py)，**15 项静态验证门禁 100% 全部通过**：

| 门禁编号 | 检验项目 | 验证结果 | 详细指标 |
| :--- | :--- | :---: | :--- |
| **Gate 1** | 文件尺寸等同性 | **PASS** | 严格一致：2,473,488 字节 |
| **Gate 2** | ELF 头部校验 | **PASS** | `readelf -h` 100% 字节一致 |
| **Gate 3** | 程序头表 (Segments) | **PASS** | 12 个段配置完全一致 |
| **Gate 4** | 节区头表 (Sections) | **PASS** | 30 个节区属性完全一致 |
| **Gate 5** | 动态表 (.dynamic) | **PASS** | 动态链接条目完全一致 |
| **Gate 6** | 符号表 (.dynsym/.symtab) | **PASS** | 符号数量与偏移完全一致 |
| **Gate 7** | 重定位表 (Relocations) | **PASS** | 0 重定位破坏 |
| **Gate 8** | .rodata 段零差异审计 | **PASS** | **.rodata 差异严格为 0 字节**（所有格式串置于代码洞） |
| **Gate 9** | 跳板指令边界审计 | **PASS** | `0x1106f4` 严格修改 4 字节跳板（`b 0x09c9c0`） |
| **Gate 10** | 桩代码边界审计 | **PASS** | 严格受控于 `[0x09c9c0, 0x09cf04)`（910 字节，容量 1348 字节） |
| **Gate 11** | AAPCS64 栈规范审计 | **PASS** | SP 16 字节对齐，专用 256 字节帧，所有跨调用寄存器安全保存 |
| **Gate 12** | 异步信号安全性审计 | **PASS** | 0 堆分配、0 锁、0 stdio，仅使用 async_safe_log 与内核 syscall |
| **Gate 13** | 跳板反汇编断言 | **PASS** | `1106f4: b 9c9c0` 反汇编确证 |
| **Gate 14** | 桩代码返回断言 | **PASS** | 桩代码末尾 `b 1106f8` 确证平滑接回 debuggerd |
| **Gate 15** | 死代码外部隔离审计 | **PASS** | 无任何外部分支跳入被覆盖区域 |

---

## 六、离线 12 边界用例仿真验证

运行 [`tools/test_c39_simulation.py`](file:///[LOCAL_PROJECT_ROOT]/tools/test_c39_simulation.py)，**12 项边界仿真用例 100% 全部通过**：

1. `Real Zygote 典型调用` $\rightarrow$ C37/C38/C39 三重日志全量输出，成功解析 callsite 与 msg 字符串；
2. `Canary 独立基准调用` $\rightarrow$ 成功输出 C39 日志并准确提取 `msg=C39_CANARY_TEST`；
3. `SIGSEGV 信号 (sig=11)` $\rightarrow$ 安全跳过，0 日志输出；
4. `Context 为 NULL` $\rightarrow$ 安全跳过，0 日志输出；
5. `非 abort PC (pc != 0xe10)` $\rightarrow$ 输出 C37，安全跳过 C38 与 C39；
6. `Netd 独立调用 (callsite 0x66c != 0xd3c)` $\rightarrow$ 输出 C37/C38，安全过滤跳过 C39；
7. `栈帧不匹配 (x29_runtime - x29 != 0x90)` $\rightarrow$ 安全输出 `<FRAME_MISMATCH>`，0 越界解引用；
8. `msg_ptr 为 NULL` $\rightarrow$ 安全输出 `<NULL>`；
9. `msg_ptr 为非法指针 (< 0x10000 或高位不合法)` $\rightarrow$ 安全输出 `<INVALID_PTR>`；
10. `msg_ptr 为未映射内存页` $\rightarrow$ 安全输出 `<UNMAPPED>`；
11. `msg_ptr 位于页面末尾` $\rightarrow$ 严格截断在 4KB 页面边界内，安全 null 截断；
12. `msg_ptr 包含不可打印字符` $\rightarrow$ 成功净化为 `'?'`。

---

## 七、Candidate 39 镜像构建与签名清单

镜像流水线（[`tools/build_candidate39_diag.py`](file:///[LOCAL_PROJECT_ROOT]/tools/build_candidate39_diag.py)）执行完毕：

```json
{
  "candidate": "Candidate 39-DIAG Real Zygote ART Runtime::Abort Level-2 Caller and Message in-situ capture",
  "base": "Candidate 32-DIAG zygote-domain crash-dump isolation canary",
  "linker64_sha256": "aab9dbfcde057e7c2d934d0f9be1a31629ce17e6c26f008264893d9cd97adedd",
  "canary_sha256": "707bfcaf5ee3a84783f4175b1d3f99adbe26100bb78042ec2b5e6afdfc768403",
  "source_delta": {
    "removed": [],
    "added": [],
    "modified": [
      "system/apex/com.android.runtime.apex",
      "system/bin/c32_zygote_canary"
    ]
  },
  "images": {
    "super.img": {
      "bytes": 7703469016,
      "sha256": "8FFC165B2F816D80723BA9100439AD6360CD98CA3DCE365AB3DC972D9E86ADFA"
    },
    "vbmeta_system.img": {
      "bytes": 131072,
      "sha256": "6401B984C294D6A776578DC48B864BE2A76A8D08B5F663045BB37F88E0E439D7"
    }
  },
  "flash_scope_prepared": ["super", "vbmeta_system_a"]
}
```

- **APEX 签名验证**：`apksigner verify --verbose` 确证 `APK Signature Scheme v3: true`；
- **刷写脚本 DRY-RUN 验证**：`tools/flash_candidate39_diag.ps1` 校验全绿通过。

---

## 八、当前设备物理状态与下一步执行指引

- **当前设备状态**：Xiaomi 10S (`[REDACTED_DEVICE_ID]`) 当前处于 Standalone Diag 挂载态（盘符 G:，`THYME_DIAG`），安全待命；
- **下一步执行步骤**：
  1. 请用户长按设备物理键 **【电源键 + 音量下键】**，使设备进入 **Bootloader Fastboot** 模式（出现 Fastboot 橙色/白色兔子或文字图标）；
  2. 设备进入 Fastboot 后，运行刷写脚本将 `super.img` 与 `vbmeta_system.img` 刷入设备 A 槽（刷写后设备安全停留在 Fastboot，不擅自重启）；
  3. 向用户汇报刷写完成与槽位健康状态，**等待用户发出“开始启动 C39”指令**后再启动首启观察与日志打捞。
