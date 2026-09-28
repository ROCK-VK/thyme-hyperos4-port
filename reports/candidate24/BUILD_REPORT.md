# Candidate 24 Framework/UI/display diagnostic build

- Candidate: Candidate 24 Framework/UI/display readiness diagnostic
- Base: Candidate 23 SurfaceFlinger shader-cache prime bypass
- System-only diagnostic additions; C23 system properties and all other logical partition sources retained.
- The diagnostic service logs state to logd/pmsg every 10 seconds and bounded framework/display dumps roughly once per minute for 15 minutes after post-fs-data.
- No runtime claim is made until the next C24 boot evidence is collected.
- Prepared flash scope: `super`, `vbmeta_system_a`; builder never communicates with a device.

| Image | Bytes | SHA-256 |
|---|---:|---|
| `boot.img` | 201326592 | `E5A016056D5C93C7A886980A7C062617EC44DC06A48417D7DD0F4476708A6368` |
| `vendor_boot.img` | 100663296 | `02333B82BA936F1BAAB1ECAB744632C70F8FC16688A206C7041EF319F112A137` |
| `dtbo.img` | 33554432 | `50E1AC0EDCBD333778217AA6FE8D972F6FF85ADD0DAE8A015A6642C2172DD886` |
| `vbmeta.img` | 131072 | `66A53C2EC38247193CC86B7F5DE887556864413D1142C3C1994645DE1E3BAB10` |
| `vbmeta_system.img` | 131072 | `1A67C4A2E22DA746E184B146D7DD65059D00FB501EE3642DA1BD2AEFCE706D08` |
| `super.img` | 7701896152 | `2B84BD93ADFA85FC851A17937B7F96AB4176F01F3E3D00FFC2DB78766BA2CDD8` |
