# Candidate 23 build result

- Candidate: Candidate 23 SurfaceFlinger shader-cache prime bypass
- Base: Candidate 22 K40 Android 17 Vulkan UMD ABI compatibility stack
- Change: `service.sf.prime_shader_cache=0` in system/build.prop; no other config or binaries changed.
- The change skips only optional SurfaceFlinger startup shader-cache priming; underlying output-buffer usage mismatch remains unproven/unfixed.
- C22 K40 Vulkan UMD/vendor set and previous system/SELinux/storage changes retained.
- EROFS fsck, property readback, system AVB descriptor, vbmeta_system descriptor preservation and LP extent checks passed.
- Flash scope prepared: `super`, `vbmeta_system_a`. The builder does not contact a device.

| Image | Bytes | SHA-256 |
|---|---:|---|
| `boot.img` | 201326592 | `E5A016056D5C93C7A886980A7C062617EC44DC06A48417D7DD0F4476708A6368` |
| `vendor_boot.img` | 100663296 | `02333B82BA936F1BAAB1ECAB744632C70F8FC16688A206C7041EF319F112A137` |
| `dtbo.img` | 33554432 | `50E1AC0EDCBD333778217AA6FE8D972F6FF85ADD0DAE8A015A6642C2172DD886` |
| `vbmeta.img` | 131072 | `66A53C2EC38247193CC86B7F5DE887556864413D1142C3C1994645DE1E3BAB10` |
| `vbmeta_system.img` | 131072 | `B0FFDFD7FD492F17ABD6FDC0F3577C6F9C1976C8087B6A21E77191FA1A624F46` |
| `super.img` | 7701892056 | `F0E252E232D12AEB8E84D9A56B77B39744D6972FD8E695618A10E89168209A15` |
