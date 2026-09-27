# Candidate 22 build result

- Candidate: Candidate 22 K40 Android 17 Vulkan UMD ABI compatibility stack
- Base: Candidate 21 K40 Skia Vulkan RenderEngine profile
- Build script performed host-only work. A separate restricted Fastboot script later wrote only `super` and `vbmeta_a`; see `work/reports/20260927_CANDIDATE22_K40_VULKAN_UMD/REPORT.md`.
- Flash scope prepared: `super`, `vbmeta_a`.
- C21 EGL/GLES and hardware-specific boot assets retained.
- C22 replaces the Vulkan ICD/support set with isolated K40 Android 17 UMD libraries.
- Vendor ext4 check: e2fsck read-only passed.
- Vendor metadata: root:root, mode 0644, same_process_hal_file xattr verified.
- Vendor AVB: regenerated with same partition size/salt and no FEC.
- Post-build `avbtool verify_image` validated the vendor AVB footer and SHA-256 hashtree.
- Root vbmeta: only vendor hashtree descriptor changed; all other descriptors and header flags/index preserved.
- LP: same geometry and A-slot logical partition layout; lpdump passed.
- Device remains in Bootloader Fastboot after the authorized two-partition write; C22 has not been started.

| Image | Bytes | SHA-256 |
|---|---:|---|
| `boot.img` | 201326592 | `E5A016056D5C93C7A886980A7C062617EC44DC06A48417D7DD0F4476708A6368` |
| `vendor_boot.img` | 100663296 | `02333B82BA936F1BAAB1ECAB744632C70F8FC16688A206C7041EF319F112A137` |
| `dtbo.img` | 33554432 | `50E1AC0EDCBD333778217AA6FE8D972F6FF85ADD0DAE8A015A6642C2172DD886` |
| `vbmeta.img` | 131072 | `66A53C2EC38247193CC86B7F5DE887556864413D1142C3C1994645DE1E3BAB10` |
| `vbmeta_system.img` | 131072 | `E3A2807CE59CFAF93BEF7E08EE45A1D055DE1264FFEA8F6E8EED06893892AC74` |
| `super.img` | 7701892056 | `6145D602D17321EFF1AD55A7AC10B9314AF9E7C23C0BD60D681115CD54B1330D` |
