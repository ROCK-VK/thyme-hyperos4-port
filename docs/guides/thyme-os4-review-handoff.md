# THYME-OS4 项目独立审核交接手册（通用版）

**用途：长期复用的审核方法、历史案例和安全边界；不是某一天的进度快照。**

> 新审核窗口接手时，用户会另外提供**最新的 Gemini/Antigravity/Codex 执行记录、最新项目状态及必要日志**。必须以那些新材料判定当前 Candidate 编号、真实设备状态、下一阻塞点、已授权操作和待做事项。本文出现的 C8～C13 仅为**历史案例和审核方法示范**，不意味着交接时仍处于那个节点，更不意味着某项尚未完成。不要据本文的旧版本号给出“现在应该做 C13”的结论。
>
> 本文区分“转述的代理报告”“真实日志支持的结论”“审核建议”。审核窗口没有自动获得用户 Windows/WSL 的实时访问权限，不能把 Gemini 的口头 PASS 当作自己独立执行的检查。

## 1. 接手窗口的角色和输出要求

- 用户在 Windows 11 的 Gemini Antigravity / agent / Codex中实际修改、构建、刷写小米 ROM；将该 agent 的执行记录、报告、日志发到 ChatGPT，让 ChatGPT 充当**独立技术审核员/下一阶段 Prompt 设计者**，而不是重复叙述报告。
- 审核每轮必须答：**本轮真实推进了什么；证据是否成立；Gemini 是否有错判或未证实因果；下一条直接阻塞点是什么；是否值得马上构建/刷机；给 agent 一段能连续跑到里程碑、可复制的中文 Prompt**。不要让 agent 做三两步就停，也不要让它一次越权连续刷多版。
- 用户强调**进度和效率**：有清晰日志就定位、做最小修复、针对性离线校验、进入下一轮实测。避免要求全项目重审、历史 SHA256 重算、同一批 kernel/fstab/SELinux 已确认结论不断重复。旧版十二/十四 Gate 式长 Prompt 已被修正为**精简四 Gate**：①最小正确差分；②针对当前错误的有效证据/真实策略验证；③最终镜像与 AVB/分区约束；④设备、取证、救援流程就绪。修改了哪个输入，才重新检查依赖它的结论。
- 推荐口径：“诊断和修复可以大胆推进；真正写入手机之前保持严格；已经验证且未变化的部分不重复劳动。”
- 用户通常希望**先审进度，再给完整中文 `text` 代码块 Prompt**。阶段末必须明确标注“本轮仅主机侧”或“本轮授权一次实机”，避免 Gemini 误把研发授权当刷机授权。

## 2. 项目本体和技术资产

- 项目：**THYME-OS4**，将 Xiaomi 15（项目 donor 代号 `dada`）的澎湃 OS4 / Android 17 用户空间移植至 Xiaomi 10S（代号 `thyme`；项目使用 A5 `4.19.325` 内核、Qualcomm 870/Kona 系平台）。历史资料里偶有 Gemini 将本轮误写成 Android 14，不能依这种笔误重定项目目标；以实际镜像 `build.prop` 为准。
- 项目工作区：Windows `[LOCAL_PROJECT_ROOT]`；WSL Ubuntu 编译区 `[LOCAL_WSL_USER]/`；工具 `tools/`，镜像 `work/stage_c_thyme_os4_candidate_*/images/`，现场报告 `work/reports/`，持久项目日志 `日志/项目当前状态.md` 和 `日志/执行记录.md`。
- 用户手机 Fastboot/ADB 序列号在历史报告为 `[REDACTED_DEVICE_ID]`，实验必须现场再次确认；目标槽位 `_a`，不能用历史报告代替当前 `fastboot getvar current-slot`/ADB 等核验。
- 安全恢复基线 **PixelOS A0′**，先前六分区已多次恢复成功；工具曾使用 `tools/restore_pixelos_a0_prime.ps1`、`tools/restore_and_verify_pixelos.py`。确认**当前有效脚本版本和调用参数**，尤其 agent 最近升级本地 `tools/platform-tools/fastboot.exe` v37.0.1，且曾修改过恢复脚本；不可机械沿用旧命令。
- 六个允许依本轮批准方案操作的分区：`boot_a`、`vendor_boot_a`、`dtbo_a`、`vbmeta_a`、`vbmeta_system_a`、`super`。`super` 内部是逻辑分区，不得误把其组成镜像当成独立允许刷写的任意目标。
- **不能擦除** userdata、metadata、modemst/NV/EFS/persist/IMEI/硬件密钥，不允许无依据跨槽、EDL/9008、全局 permissive、粗暴 SELinux 放权；实验失败优先取证，再恢复安全基线。
- PixelOS 恢复“5项/6项全绿”：ADB 在线，`ro.product.device=thyme`、`ro.boot.slot_suffix=_a`、`sys.boot_completed=1`、`ro.boot.verifiedbootstate=green`、预期 `uname -r`，有时还查 `ro.build.version.release=17`、`ro.build.display.id=CP2A.260605.016`。**`sys.boot_completed=1` 不等于独立证明每字节 userdata 完好**；“未擦除 + 正常启动”是更准确说法。

## 3. 必须守住的刷机/启动/救援权限边界

- 项目曾实行 `DEVICE_WRITE_STOP`：每次诊断后回 PixelOS，之后**没有新的明确授权就不再动手机**；主机侧研发可连续进行。
- **批准刷机与批准启动分开**。典型单次实验：核验基线/镜像/救援包和进程 → 唯一 Fastboot 写入者刷六分区 → 刷完停留 Fastboot → 通知用户手机仍在 Fastboot → 用户明确回复“准备好了，开始启动” → `fastboot reboot` → 人工观察/ADB 或 Standalone 取证 → 完成日志保全后恢复 PixelOS → 健康核验。
- 不应由 Gemini 在看见 Fastboot 时马上让自动恢复程序抢跑。C9/C10 的自动恢复监控曾是风险点：必须在取证阶段暂停它；取证完整后才放行，并且不能因想快速恢复而中断正在写入的 `super`。同一时间一个 Fastboot 写入进程。
- **异常画面：米标常亮、黑屏、自动 Fastboot**只能当现象，不能当某特定 init/HAL 已执行的证据。用户按 `Power+Vol-` 人工进 Fastboot 的时间与自动软件重启必须分别记录。
- 取证：`fastboot boot` 已验证的 Standalone Diag 环境，手机可能作为 `THYME_DIAG` USB 盘挂载 Windows；单独目录保存 `console-ramoops`、`pmsg-ramoops`（如存在）、`diag_status`、`dmesg_diag_boot`、tombstones（如有）、USB/屏幕时间线。独立记录来源/大小/哈希。**Standalone 自己的 dmesg != 先前 ROM 的内核日志**；`oops.raw` 曾包含旧 MIUI 工厂残留，绝对不能混入当前 Candidate 日志。
- Warm Reset 是增加保留 RAM 机会的机制，**并不保证所有用户态消息都在 `console-ramoops`，用户态 logcat 可能在 `pmsg-ramoops`**；不要只凭某一条 PMIC “warm” 行断言整个多次重启序列都保全。最终有效性以本轮确证日志为准。

## 4. 历史审核案例：曾经如何从误判走向真实阻塞点（非实时进度）

### C5/C6/C7/C8：建立可取证链路与锁定 PropertyInit
- C5/C6：静态 Mi logo、手工 Power+Vol- 回 Fastboot；Standalone 曾获取约150KB pstore；不能用屏幕猜直接原因。
- C7：`panic=0` 等诊断参数，米标→黑屏周期，未成功取得可靠新 pstore，旧 `oops.raw` 是历史 MIUI 残留。
- C8 `InitFatalPanic`：`androidboot.init_fatal_panic=true`，成功取得真实 `console-ramoops`，Second Stage init 已出现，报 `Duplicate prefix match detected for 'persist.radio.imei'`。当时 `enforcing=1`；早期的“已全程 SELinux permissive”表述是错的。

### C9：修五处 property_contexts 重复；但早期成功总结必须撤回部分内容
- 在 `system_ext_property_contexts` 中去掉/注释与 vendor 重复的五处定义：`persist.radio.imei`、`persist.radio.meid`、`ro.ril.oem.imei`、`ro.ril.oem.meid`、`ro.ril.miui.imei`；保留合理 owner 规则与其他初始化配置。**把两个标签改成相同字符串并不能消除重复 prefix 的结构冲突**。
- C9 离线属性 Trie 通过，手机启动表现较 C8 改变，但本次 reboot 令真实 RAM 现场未能保全；Gemini 错误地将 `oops.raw` 中 **2024-06-05 MIUI 历史日志**当 C9 本轮日志，宣称 APEX 已挂载18个、servicemanager/hwservicemanager、SurfaceFlinger、Keystore2 及“critical service exited 4 times”均有真实证据。这些具体 C9 运行阶段和重启原因后来**明确撤回**；不要复活这个错误结论。

### 原 C10 被否决；C10-WarmDtb 解决取证可用性
- 原 C10 只把命令行 `reboot=panic_warm` 改成 `reboot=w,panic_w`。Linux 通用解析器接受，但 A5 Qualcomm `drivers/power/reset/msm-poweroff.c` 的 `do_msm_restart()` **忽略** `reboot_mode`，此修改不能控制 PMIC。原 C10 没有刷机价值，已废弃。
- 重新研制 C10-WarmDtb：在 `vendor_boot.img` 内三份有效候选 FDT 的 `restart@c264000` / `compatible="qcom,pshold"` 节点加入 `qcom,force-warm-reboot;`，恢复 C9 其余命令行、重封装 `vendor_boot` 并更新 `vbmeta` 相关描述符。驱动在 probe 读取 `force_warm_reboot`、真实 PMIC 复位决策使用它；不需要重新编译 A5 kernel。
- C10 实测获得约 157,792B / 2,085 行的真实 console-ramoops；本轮系统在 `apexd-bootstrap` 扫描 `/system_ext/apex` 时 `Permission denied`，随后明确 `reboot("bootloader,bootstrap-apexd-failed")` 自动 Fastboot。Standalone 报告 warm boot/驱动 “Forcing a warm reset”。**第一次真正从 ROM 当前日志锁定下一阻塞，不再盲猜 Display HAL**。
- 构建 `system_ext` EROFS 时漏了正确的 Android `--file-contexts`、`--fs-config-file`/元数据承载方式；不能仅凭 Permission denied 就武断宣称每个 inode 全部 unlabeled，还要区分 SELinux xattr 与 UNIX mode/UID/GID。

### C11：修 system_ext 元数据，跨越 APEX Bootstrap
- C11 重建 `system_ext` 时恢复所需 SELinux xattr、UID/GID、mode，保留 C9 五处 property 去重和 C10 WarmDtb。
- Gemini 现场报告：41 个 APEX 扫描、4 个 bootstrap APEX 激活；米标运行约 **795+ 秒（13 分钟）**，无 kernel panic；获得约1.4MB console 和约42KB `pmsg-ramoops`，见真实 keymaster/gatekeeper/vold/keystore2 日志。**13分钟仍未进入桌面，不能称 ROM 开机成功**。
- 两硬件安全服务 Keymaster4.0/Gatekeeper1.0 报 `Abort message: 'QSEECom_start_app failed'`，对 `/dev/ion` 的 AVC tcontext 为 `u:object_r:device:s0`，SELinux Enforcing；Qualcomm 旧 HAL 需要 ION/QSEECom，供体新 userspace 缺 `/dev/ion` 标签规则。

### C12 历史案例：补 `/dev/ion` 标签后仍被拒绝
- C12 在 `system_ext_file_contexts` 中补唯一一条 `/dev/ion    u:object_r:ion_device:s0`；重建 `system_ext`、`super`、`vbmeta_system`，保持其他获证基线。
- C12 本轮真实报告：约**444KB console、25KB pmsg**；AVC 的 tcontext 从 C11 `device:s0` 实际变为 C12 **`ion_device:s0`**，证明标签修复真实生效。但 Keymaster/Gatekeeper 仍 `denied { read }`、`QSEECom_start_app failed` / SIGABRT。**“泛型 device AVC 清零”不等于“ION AVC 清零”。**
- C12 实测示例：

  ```text
  avc: denied { read } ... scontext=u:r:vendor_hal_keymaster_qti:s0 tcontext=u:object_r:ion_device:s0 tclass=chr_file permissive=0
  avc: denied { read } ... scontext=u:r:vendor_hal_gatekeeper_qti:s0 tcontext=u:object_r:ion_device:s0 tclass=chr_file permissive=0
  ```
- `vold` 已走到 `fscrypt_mount_metadata_encrypted`、读取 `/metadata/vold/metadata_encryption/key`、后续等待密钥服务；**这仅证明该密钥文件存在且能被访问，不证明 `/data` 已成功解密挂载；切勿擦 data/metadata 或擅自重建密钥**。
- 该轮 Gemini 曾报告完成 PixelOS A0′ 六分区恢复、`thyme`、`_a`、`sys.boot_completed=1`、`verifiedbootstate=green`、预期内核。**这只是历史恢复案例；接手时不得据此宣称当前手机仍处于 PixelOS 或仍健康。**

## 5. 历史审核案例：C12 后如何设计 C13 映射修复（非接手时任务）

这节只示范**审核人员如何从一轮实机结果设计下一轮目标**。交接时具体修复是否已经完成、是否已经转向新阻塞点，全部以用户随后提供的最新报告为准。

- 某次 C12 实机报告里，`/dev/ion` 的 tcontext 已从 `device:s0` 改为 `ion_device:s0`，但 Keymaster、Gatekeeper 仍 `denied { read }` 并报 `QSEECom_start_app failed`。审核员没有要求重做已生效的 `/dev/ion` 标签修复，而是把下一假说转向旧 vendor 与新 platform 的 Treble SELinux 版本化权限关联。
- Gemini 曾提出：旧 vendor `allow` 引用 `ion_device_30_0`，新平台缺少到具体 `ion_device` 的有效兼容映射。此结论必须用**当轮最终镜像的实际 CIL、mapping、域与属性、实际二进制策略**核实，而不是依赖口头归因。
- 若证据符合，曾优先考虑最小映射例子：

  ```lisp
  (typeattributeset ion_device_30_0 (ion_device))
  ```

  放置位置应是**当轮真实 SELinux 编译/加载路径中归属合理的文件**；还需检查声明重复、secilc、neverallow、precompiled_sepolicy 与 hash 的选择。此处不是适用于任何后续版本的固定补丁，不能不检查就套用。
- Gemini 还曾建议将两条 direct allow 与映射一起加入。审核员指出：**若旧 vendor 已有覆盖该属性的 allow，单补映射可能足够；不要无证据扩大权限**。如补映射后真实策略仍不足，再按新日志最小增加必要授权。
- 预期实机验收是逐层判断：节点标签是否仍正确 → 特定 AVC 是否消失 → HAL 是否越过原失败 → vold/data 是否继续推进 → 下一条真实阻塞是什么。**补上权限不保证 QSEECom、TrustZone、data 解密或桌面一定成功。**

## 6. 新窗口收到最新报告后的通用审核流程（不限 Candidate 编号）

**第一步：重建实时状态，不沿用本手册的历史进度。** 从用户最新报告中确认：当前 Candidate 编号和状态（仅计划、主机侧构建、已刷、已取证、已恢复哪一种）；设备现在在 PixelOS、Fastboot、实验 ROM、Standalone 还是未知；最后一次用户批准的具体操作；后台是否还有 Fastboot/恢复流水线运行。信息不全时要求 agent 查当前事实，不猜。

**第二步：区分来源与证据等级。** 原始 `console-ramoops` / `pmsg-ramoops` / tombstone / logcat / 现场时间线优先；最终镜像及差分、编译日志次之；Gemini 的自然语言总结不能代替实际输出。特别鉴别本轮日志与历史 MIUI `oops.raw`、Standalone 自身 dmesg、其他 Candidate 残留。把“直接观察”“合理机制假说”“实机尚待证实”分开写。

**第三步：找首个直接阻塞点和最小因果链。** 查首次错误的进程、PID、时间、退出原因与后续连锁反应；不要把最后一条重启消息或一个紧邻 AVC 自动当成最初根因。屏幕米标/黑屏仅是现象。若错误已被上轮修复，不要因为新阶段仍失败就反复重做已生效部分。

**第四步：选择下一里程碑的工作量。** 有明确错误 → 连续主机侧修复、针对性校验、必要重建；日志不足 → 有效的最小取证方案；足够的最终产物证据 → 建议一次受控真机试验；若风险或策略编译尚未闭合 → 先修正，别为增加 Candidate 编号而刷机。用户偏好 agent 获得**较大的连续主机侧执行权限**，而不是每几条命令一停。

**第五步：精简四 Gate，依变化决定检查。** ①最小正确差分；②对当前错误的针对性验证（例如实际编译后 SELinux 权限，而非只 grep）；③最终镜像、分区容量、AVB、被刷资产一致性；④Standalone/救援包/独占 Fastboot/设备门禁。已验证且未变化的内核、SAR、fstab、WarmDtb 等可以引用之前证据，不重做所有历史检查。

**第六步：给用户可直接复制的中文 Prompt。** 应写明确阶段目标、充分自主权限、应交付的关键证据与最终报告、禁止操作和**刷机授权边界**。不要把某个历史 Candidate 路线写死到通用 Prompt。需要真机时仅授权用户明确同意的**一个**候选、**一次**实验；刷写后仍须另等用户“准备好了，开始启动”；失败先取证再恢复 PixelOS。不要替用户确认授权。

**审核输出建议结构**：本轮确实推进的事实 → 需修正的误判或风险 → 下一步是否值得上机/继续主机侧 → 可复制的里程碑 Prompt。不要用“100%”“司法级”替代证据，也不要把尚未看到的原始日志宣称已独立复核。

## 7. 项目内重要路径（以文件实际存在为准）

```text
[LOCAL_PROJECT_ROOT]\
  日志\项目当前状态.md
  日志\执行记录.md
  tools\build_candidate9.py
  tools\build_candidate11.py
  tools\build_candidate12.py
  tools\precheck_candidate12.py
  tools\flash_candidate12.ps1
  tools\restore_pixelos_a0_prime.ps1
  tools\restore_and_verify_pixelos.py
  tools\platform-tools\fastboot.exe
  work\reports\20260924_CANDIDATE8_INITFATALPANIC_LOG_SALVAGE\
  work\reports\20260924_CANDIDATE10_WARMDTB_LOG_SALVAGE\
  work\reports\20260924_CANDIDATE11_LOG_SALVAGE\
  work\stage_c_thyme_os4_candidate_12_ion_fix\images\
WSL:
  [LOCAL_WSL_USER]/thyme_pixelos_native_kernel_45b9b95/source/
  [LOCAL_WSL_USER]/c9_build_stage/system_ext_tree/
  [LOCAL_WSL_USER]/c12_build_stage/system_ext_tree/
```

历史记录由 Gemini 生成，本地文件路径和工具参数如已被移动，应让 Gemini 搜索现有项目而非在新的审核窗口假定路径总不变。特别注意**任意新 Candidate** 的产物路径应由它的实际报告和文件验证决定，不能凭历史目录格式推测。

## 8. 给新审核窗口的通用接手指令（不预设任何当前版本）

> 你是 THYME-OS4（Xiaomi 15 澎湃 OS4/Android 17 用户空间 → Xiaomi 10S `thyme`）项目的独立技术审核员。**本手册只提供历史案例、项目技术背景、风险边界和审核方法，不表示当前进度。用户会另发 Gemini Antigravity 的最新完整执行记录、项目状态和必要日志；必须先从最新材料确认当前版本、手机实时状态、授权范围、实测事实和下一直接阻塞点。** 请核对日志 provenance 和最终镜像/策略差分，区分确证、假说和 Gemini 的过度推断；基于变化做少量有效检查，不重做全量历史 Gate。然后给出可复制、能让 Gemini 自主推进到里程碑的中文 Prompt。主机侧可连续研发，未经用户新的明确授权不刷机；刷写完停 Fastboot，等用户明确“准备好了，开始启动”才 reboot；失败先用 Standalone/实时日志取证，再恢复 PixelOS A0′；禁止 wipe userdata/metadata/NV/硬件密钥、无依据跨槽或 EDL。历史 C8～C13 仅供识别曾经踩过的坑；**不得依据它们直接决定交接时要做哪一版、哪一个补丁，或声称设备现在健康。**

## 9. 交接的认识边界

- 我是**审核窗口**，不在用户 PC 上直接跑过编译或真机操作，也不应宣称自己查看过 Gemini 提到的本地 `file:///` 原文件内容，除非用户上传该文件或连接可读项目仓库。
- 本文历史 C10–C12 的关键日志摘录来自用户粘贴的 Gemini 报告；新窗口需要审查任何轮次的完整原始日志时，应使用用户最新上传的报告/日志或可读连接器，不要把历史总结代替本轮数据。
- 历史 C9 的“历史残留误判”是这个项目重要教训：源数据 provenance 高于 Gemini 修辞；新日志一定要验证它来自当前 Candidate。

**交接时推荐用户附带：** 最新 `项目当前状态.md`、最新 `执行记录.md` 的相关范围、最新 Candidate 构建/预检/实机报告、异常原始日志（如有）、当前手机在什么界面及最近授权了什么操作。若用户只发一段新报告，也先基于那段分析，不强迫其每次上传全项目历史。
