# C35-DIAG Linker64 Binary Patch 权威审计报告

生成时间：2026-10-02
目标二进制：`/apex/com.android.runtime/bin/linker64`

---

## 1. 核心指纹与大小比对

| 审计项 | 原始文件 (Original) | 补丁后文件 (Patched C35) | 判定 |
|---|---|---|---|
| 文件大小 | `2,473,488 字节` | `2,473,488 字节` | **100% 一致 (0 字节变化)** |
| SHA-256 | `00e5dc0e9716f6e7c6d70e04fa7a721941c02e912932eb5c08753676da0adb50` | `8cc81052fb27b91214314e660ae6ab4245bda96c43e20b2368d3f340d5762574` | **受控哈希演进** |
| ELF Header | 完全一致 | 完全一致 | **PASS (零突变)** |
| Program Headers | 12 个 LOAD/SEGMENT 布局相同 | 12 个 LOAD/SEGMENT 布局相同 | **PASS (零突变)** |
| Section Headers | 30 个 Section 偏移与大小相同 | 30 个 Section 偏移与大小相同 | **PASS (零突变)** |
| Dynamic Table | DYNAMIC 条目完全相同 | DYNAMIC 条目完全相同 | **PASS (零突变)** |
| 外部动态依赖 | 无新增依赖 (`NEEDED` 清单一致) | 无新增依赖 (`NEEDED` 清单一致) | **PASS (零突变)** |
| 符号表 (`.dynsym`/`.symtab`) | 条目数与偏移一致 | 条目数与偏移一致 | **PASS (零突变)** |

---

## 2. 所有修改字节偏移与差异对照表

共检测到 `17` 个受控修改区间：

### 区间 1：偏移 `0x795a` ~ `0x795d` (长度 3 字节)

- **修改目的**：
  - `.rodata` 格式化字符串原地替换：将废弃的 `unexpected value: %zd` 改为 `C35 helper output: %s\n`，末尾填充 `\0` 保留原长。
- **原始字节 (Hex)**：
  `25733a`
- **新字节 (Hex)**：
  `433335`

### 区间 2：偏移 `0x795e` ~ `0x795f` (长度 1 字节)

- **修改目的**：
- **原始字节 (Hex)**：
  `72`
- **新字节 (Hex)**：
  `68`

### 区间 3：偏移 `0x7960` ~ `0x798d` (长度 45 字节)

- **修改目的**：
- **原始字节 (Hex)**：
  `6164206f662049504320706970652072657475726e656420756e65787065637465642076616c75653a20257a64`
- **新字节 (Hex)**：
  `6c706572206f75747075743a2025730a0000000000000000000000000000000000000000000000000000000000`

### 区间 4：偏移 `0x111b68` ~ `0x111b69` (长度 1 字节)

- **修改目的**：
  - `.text` 父端协议感知握手校验：将 `b.ne 111ca4` 改为 `b.lt 111ca4`，使 `rc >= 1 && buf[0] == 0x01` 成功放行，仅在 `rc < 1` (EOF) 或第一字节非 0x01 时走错误分支。
- **原始字节 (Hex)**：
  `e1`
- **新字节 (Hex)**：
  `eb`

### 区间 5：偏移 `0x111ca4` ~ `0x111ca6` (长度 2 字节)

- **修改目的**：
  - `.text` 父端失败分支入口分流：`cbz x4, 111cb0` (EOF 走原版 EOF 打印)；`b 111d14` (有数据走 stderr 捕获)；`nop`。
- **原始字节 (Hex)**：
  `9f04`
- **新字节 (Hex)**：
  `6400`

### 区间 6：偏移 `0x111ca7` ~ `0x111caa` (长度 3 字节)

- **修改目的**：
- **原始字节 (Hex)**：
  `f16003`
- **新字节 (Hex)**：
  `b41b00`

### 区间 7：偏移 `0x111cab` ~ `0x111cb0` (长度 5 字节)

- **修改目的**：
- **原始字节 (Hex)**：
  `54840400b5`
- **新字节 (Hex)**：
  `141f2003d5`

### 区间 8：偏移 `0x111d14` ~ `0x111d26` (长度 18 字节)

- **修改目的**：
  - `.text` 父端 Stderr 捕获与打印流水线：动态在栈底开辟 512 字节局部缓冲，复制首 4 字节，调用 `read(output_pipe[0], sp+x4, 496)` 读取剩余输出，末尾安全打 null-terminator，调用 `async_safe_format_log` 打印为 `C35 helper output: %s`，平衡栈指针后跳转 `waitpid`。
- **原始字节 (Hex)**：
  `1f050071c0e7ff54680640f9c9f7fff0299d`
- **新字节 (Hex)**：
  `ff0308d1e82b42b9e80300b9e003152ae163`

### 区间 9：偏移 `0x111d27` ~ `0x111d41` (长度 26 字节)

- **修改目的**：
- **原始字节 (Hex)**：
  `91a1f7ffb021c83c91a2f7ff9042dc0b91e5ffff17680640f9c9`
- **新字节 (Hex)**：
  `8b023e80522524fd971f0000f100c09f9a0000048bff6b2038a1`

### 区间 10：偏移 `0x111d43` ~ `0x111d47` (长度 4 字节)

- **修改目的**：
- **原始字节 (Hex)**：
  `[REDACTED_DEVICE_ID]`
- **新字节 (Hex)**：
  `[REDACTED_DEVICE_ID]`

### 区间 11：偏移 `0x111d48` ~ `0x111d49` (长度 1 字节)

- **修改目的**：
- **原始字节 (Hex)**：
  `a1`
- **新字节 (Hex)**：
  `a2`

### 区间 12：偏移 `0x111d4b` ~ `0x111d4f` (长度 4 字节)

- **修改目的**：
- **原始字节 (Hex)**：
  `[REDACTED_DEVICE_ID]`
- **新字节 (Hex)**：
  `[REDACTED_DEVICE_ID]`

### 区间 13：偏移 `0x111d50` ~ `0x111d57` (长度 7 字节)

- **修改目的**：
- **原始字节 (Hex)**：
  `a2f7ffd0426825`
- **新字节 (Hex)**：
  `e0008052e30300`

### 区间 14：偏移 `0x111d58` ~ `0x111d74` (长度 28 字节)

- **修改目的**：
- **原始字节 (Hex)**：
  `080140b9e00080521f8d0071e8f7ffd008090d910301899a27ffff17`
- **新字节 (Hex)**：
  `8d85fd97ff0308912cffff171f2003d51f2003d51f2003d51f2003d5`

### 区间 15：偏移 `0x111e74` ~ `0x111e79` (长度 5 字节)

- **修改目的**：
- **原始字节 (Hex)**：
  `1f04003181`
- **新字节 (Hex)**：
  `e003182a41`

### 区间 16：偏移 `0x111e7a` ~ `0x111e98` (长度 30 字节)

- **修改目的**：
- **原始字节 (Hex)**：
  `0054880240b91f11007120ffff54e0031a2ae1031f2a9b3dff97990240b9`
- **新字节 (Hex)**：
  `8052a03dff97e0031a2ae1031f2a9d3dff97070000141f2003d51f2003d5`

### 区间 17：偏移 `0x111e99` ~ `0x111ea8` (长度 15 字节)

- **修改目的**：
- **原始字节 (Hex)**：
  `040031610000543f13007120ffff54`
- **新字节 (Hex)**：
  `2003d51f2003d51f2003d51f2003d5`

---

## 3. 结构一致性断言

- **ELF Program Header 变动**：`False` (预期 False)
- **Section Layout 变动**：`False` (预期 False)
- **Loadable Segment 变动**：False (LOAD 0x50000 权限为 R E，大小 0x15e7a0，MemSiz 0x15e7a0 零变动)
- **RELRO / GNU_STACK / PIE 变动**：False (GNU_RELRO: 0x1b0000, GNU_STACK: RW, DYN: Position-Independent)
- **新动态依赖**：无
- **代码总长度**：0 增加，所有指令均原地置换或利用 dead-code/NOP 区间填充

---

## 4. 关键反汇编对比 (`debuggerd_dispatch_pseudothread`)

### 4.1 子进程 Child 端 Dup2 扩展对比 (0x111e68 ~ 0x111ea8)

```armasm
; === 补丁后 C35 Child 反汇编 ===
  111e68:	[REDACTED_DEVICE_ID] 	mov	w0, w24         ; w24 = output_pipe[1]
  111e6c:	52800021 	mov	w1, #0x1        ; STDOUT_FILENO (1)
  111e70:	[REDACTED_DEVICE_ID] 	bl	e14fc <__dl_dup2>
  111e74:	[REDACTED_DEVICE_ID] 	mov	w0, w24         ; w24 = output_pipe[1]
  111e78:	52800041 	mov	w1, #0x2        ; STDERR_FILENO (2) [C35 新增!]
  111e7c:	[REDACTED_DEVICE_ID] 	bl	e14fc <__dl_dup2>
  111e80:	[REDACTED_DEVICE_ID] 	mov	w0, w26         ; w26 = crash_dump_pipe[0]
  111e84:	[REDACTED_DEVICE_ID] 	mov	w1, wzr         ; STDIN_FILENO (0)
  111e88:	[REDACTED_DEVICE_ID] 	bl	e14fc <__dl_dup2>
  111e8c:	14000007 	b	111ea8          ; 跳转进入原版管道关闭及 execle 流水线
  111e90:	[REDACTED_DEVICE_ID] 	nop
  111e94:	[REDACTED_DEVICE_ID] 	nop
  111e98:	[REDACTED_DEVICE_ID] 	nop
  111e9c:	[REDACTED_DEVICE_ID] 	nop
  111ea0:	[REDACTED_DEVICE_ID] 	nop
  111ea4:	[REDACTED_DEVICE_ID] 	nop
```

### 4.2 父端 Parent Handshake 协议感知校验 (0x111b64 ~ 0x111b70)

```armasm
; === 补丁后 C35 Parent 校验反汇编 ===
  111b64:	[REDACTED_DEVICE_ID] 	cmp	x0, #0x1
  111b68:	[REDACTED_DEVICE_ID] 	b.lt	111ca4      ; [C35 改造] 若 x0 < 1 (EOF) 跳转 111ca4
  111b6c:	[REDACTED_DEVICE_ID] 	cmp	w8, #0x1
  111b70:	[REDACTED_DEVICE_ID] 	b.ne	111ca4      ; 若 buf[0] != 0x01 跳转 111ca4
  ; 否则若 buf[0] == 0x01，无条件放行进入现有 clone() tombstone 流程！
```

### 4.3 父端 Stderr 捕获与打印流水线 (0x111ca4 / 0x111d14 ~ 0x111d70)

```armasm
; === 补丁后 111ca4 分流 ===
  111ca4:	[REDACTED_DEVICE_ID] 	cbz	x4, 111cb0      ; EOF (x4==0) 直通原版 "failed to exec, or was killed"
  111ca8:	[REDACTED_DEVICE_ID] 	b	111d14          ; x4 > 0 有错误输出，进入捕获流水线
  111cac:	[REDACTED_DEVICE_ID] 	nop

; === 补丁后 111d14 捕获与日志流水线 ===
  111d14:	[REDACTED_DEVICE_ID] 	sub	sp, sp, #0x200  ; 栈底开辟 512 字节独立缓冲，绝不破坏父栈
  111d18:	[REDACTED_DEVICE_ID] 	ldr	w8, [sp, #552]  ; 从父栈 [sp_orig + 40] 复制前次 read 读到的首 4 字节
  111d1c:	[REDACTED_DEVICE_ID] 	str	w8, [sp]
  111d20:	[REDACTED_DEVICE_ID] 	mov	w0, w21         ; fd = output_pipe[0]
  111d24:	[REDACTED_DEVICE_ID] 	add	x1, sp, x4      ; buf = sp + x4
  111d28:	[REDACTED_DEVICE_ID] 	mov	w2, #0x1f0      ; 尝试读取最多 496 字节剩余报错
  111d2c:	[REDACTED_DEVICE_ID] 	bl	5adc0 <__dl_read>
  111d30:	[REDACTED_DEVICE_ID] 	cmp	x0, #0x0
  111d34:	[REDACTED_DEVICE_ID] 	csel	x0, x0, xzr, gt ; x0 = max(0, x0)
  111d38:	[REDACTED_DEVICE_ID] 	add	x0, x0, x4      ; total = x4 + x0
  111d3c:	[REDACTED_DEVICE_ID] 	strb	wzr, [sp, x0]   ; 安全打 null-terminator
  111d40:	[REDACTED_DEVICE_ID] 	adrp	x1, 6000 <__dl_.str.3.llvm.10601115370221303137+0x69>
  111d44:	[REDACTED_DEVICE_ID] 	add	x1, x1, #0xf32  ; tag = "DEBUG"
  111d48:	[REDACTED_DEVICE_ID] 	adrp	x2, 7000 <__dl_.str.llvm.3714003009145656655+0xce>
  111d4c:	91256842 	add	x2, x2, #0x95a  ; fmt = "C35 helper output: %s\n"
  111d50:	[REDACTED_DEVICE_ID] 	mov	w0, #0x7        ; priority = 7 (FATAL)
  111d54:	[REDACTED_DEVICE_ID] 	mov	x3, sp          ; arg = 捕获的完整 stderr 字符串
  111d58:	[REDACTED_DEVICE_ID] 	bl	7338c <__dl_async_safe_format_log>
  111d5c:	[REDACTED_DEVICE_ID] 	add	sp, sp, #0x200  ; 平衡栈指针
  111d60:	[REDACTED_DEVICE_ID] 	b	111a10          ; 跳转 waitpid 回收子进程并退出
  111d64:	[REDACTED_DEVICE_ID] 	nop
  111d68:	[REDACTED_DEVICE_ID] 	nop
  111d6c:	[REDACTED_DEVICE_ID] 	nop
  111d70:	[REDACTED_DEVICE_ID] 	nop
```
