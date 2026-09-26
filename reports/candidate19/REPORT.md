# THYME-OS4 Candidate 19 RGBX EGLConfig 实验准备

## 目的

C18 的 pmsg 中 SurfaceFlinger 记录了 61 次 `no suitable EGLConfig found`，每次请求参数均为 `format: 1`（RGBA_8888）。C19 将 Android 17 的默认合成像素格式改为 `2`（RGBX_8888），用于验证目标图形栈是否能为该格式选择 EGLConfig。此为定点兼容性实验，不是已证实的根因修复。

## 改动范围

- 基线：Candidate 18 native Adreno。
- 唯一源码配置改动：`system/build.prop` 增加 `ro.surface_flinger.default_composition_pixel_format=2`。
- 保留 C18 的 `persist.graphics.egl=adreno`、BPF 绕过、Keymaster/Gatekeeper 与 graphics allocator ION 权限、thyme 内核及硬件栈、SELinux 和存储配置。
- 未改 boot、vendor_boot、dtbo、vbmeta、system_ext 策略；未替换 EGL/Vulkan/GPU 库；未擦除 userdata/metadata。

## 构建与主机检查

- 构建器：`tools/build_candidate19_rgbx_egl.py --resume`，退出码 0。
- 输出：`work/stage_i_thyme_os4_candidate_19_rgbx_egl_run1/images/`。
- 构建器检查：最终 system EROFS 可读及 fsck 通过；属性从最终 EROFS 回读为 RGBX_8888；`vbmeta_system` 的 system hashtree 描述符匹配新 system，product/system_ext 描述符与 C18 一致；LP dump 的 A 槽逻辑分区和几何符合 C18 布局。
- 六镜像清单：`images/BUILD_MANIFEST.json`。本次写入镜像：
  - `super.img`：7,684,274,964 bytes；SHA-256 `436B4322842C649C674C9B76AE057894EE0B2AC74EB74A0098FD278CC3E634DD`。
  - `vbmeta_system.img`：131,072 bytes；SHA-256 `1E75E1733BBDFE4CF43D898120F202A5761168CD021B0A160784667EFFB5E652`。
- 刷写脚本 Dry-Run 及执行前哈希复核通过；目标仅为 `super` 和 `vbmeta_system_a`。

## 实机刷写

2026-09-27（UTC+8）设备预检为唯一目标 `product=thyme`、A 槽、Bootloader 已解锁、非 userspace Fastboot；A 槽状态为 `unbootable=no / successful=no / retry=6`。Fastboot 依次写入 `super` 与 `vbmeta_system_a`，两项均返回成功；super 的 10 个 sparse chunk 全部完成。没有擦除数据、修改其他分区、切换槽位或执行重启/回锁。

刷后只读复核仍为 Bootloader Fastboot，A 槽与解锁状态未变，A 槽 boot-control 状态仍为 `no/no/retry=6`。Candidate 19 尚未启动，因而没有任何真机图形效果结论。

## 下一步验证

用户在场确认后，先以 `C19-rgbx-format` 标签启动只读观察器并等待 `[ARMED]`，然后才能进行一次 Fastboot reboot。重点看 SurfaceFlinger 的请求是否变为 `format: 2`、EGLConfig abort 是否消失，以及是否出现 bootanimation。若失败，优先保存本轮主机观察及 Standalone 全量诊断卷；不可把 standalone 自身 dmesg 当成 Android 日志。
