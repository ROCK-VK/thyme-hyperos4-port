# Candidate 25 persistent first-screen/framework diagnostic build

- Candidate: Candidate 25 persistent first-screen/framework diagnostic
- Base: Candidate 24 Framework/UI/display readiness diagnostic
- C25 replaces C24's unverified logd-only sampler with a bounded native helper and a durable metadata diagnostic file.
- The first file record is START; property/PID samples occur every 15 seconds and bounded framework/display queries about once per minute for 15 minutes.
- Diagnostic writes are confined to `/metadata/thyme_os4_diag`; the helper does not modify userdata, encryption metadata records, BCB or hardware partitions.
- Prepared flash scope: `super`, `vbmeta_system_a`; this builder never communicates with a device.

| Image | Bytes | SHA-256 |
|---|---:|---|
| `boot.img` | 201326592 | `E5A016056D5C93C7A886980A7C062617EC44DC06A48417D7DD0F4476708A6368` |
| `vendor_boot.img` | 100663296 | `02333B82BA936F1BAAB1ECAB744632C70F8FC16688A206C7041EF319F112A137` |
| `dtbo.img` | 33554432 | `50E1AC0EDCBD333778217AA6FE8D972F6FF85ADD0DAE8A015A6642C2172DD886` |
| `vbmeta.img` | 131072 | `66A53C2EC38247193CC86B7F5DE887556864413D1142C3C1994645DE1E3BAB10` |
| `vbmeta_system.img` | 131072 | `63B03D20B8EF718C70EF36F063DA57EDD858CE9D7570E490AFE48681A89104C7` |
| `super.img` | 7702744024 | `87022BC2BE868B1A3CF51F2B3A63C377BBA245BCEEA2BB72610D5A3270BDDF1F` |
