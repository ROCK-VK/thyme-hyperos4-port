# Candidate 44 Flash and Fastboot Hold State Report

**Candidate ID**: THYME-OS4 Candidate 44  
**Date**: 2026-10-04 17:45 HKT  
**Device Target**: Xiaomi 10S (`thyme` / `[REDACTED_DEVICE_ID]`)  
**Flash Status**: **100% SUCCESSFUL (Device Retained in Bootloader Fastboot)**  

---

## 1. What Candidate 44 Changed

1. **Surgically Fixed CAPEX Container Manifest Defect**:
   - Injected actual `apex_payload.img` AVB root digest (`4bdfe2f9158035e7d4dd5efe814f5d1dd9eee1d9052eb7c1f571125e9c67e042`) into outer `apex_manifest.pb.capexMetadata.originalApexDigest`.
   - Reassembled and signed the CAPEX container with project RSA-4096 key (`apksigner` v3).
2. **Inherited 100% C43 Inner APEX & Netd Patch**:
   - Sourced inner `original_apex` SHA256: `c6c010d1d829ac138e0c93889728167202c8f510b3f5948fe900cc2006cfbfd3` (**100% Byte-Identical**).
   - Patched `libnetd_updatable.so` SHA256: `a70a3176b82d792cdea3ed876c90980c1d459fbcdb859d5e21f12c3a5eaf92f5` (**4-byte NOP patch retained**).
   - Inner & Outer version: `370400000` (varint `\x80\xb6\xcf\xb0\x01`).
3. **Inherited C40 & C42 System Fixes**:
   - C40 Media Profiles fix (`ro.media.xml_variant.codecs=_V1_0`).
   - C42 DisplayDeviceConfig minimum brightness fix (`<value>0.000854597</value>`).

---

## 2. Key Digest Verification

- **Outer Manifest originalApexDigest**: `4bdfe2f9158035e7d4dd5efe814f5d1dd9eee1d9052eb7c1f571125e9c67e042`
- **Actual Payload AVB Root Digest**: `4bdfe2f9158035e7d4dd5efe814f5d1dd9eee1d9052eb7c1f571125e9c67e042`
- **Equivalence Status**: **EXACT STRING & BYTE MATCH (PASS)**
- **EROFS Readback Verification**: Extracted from `system_c44.img` and confirmed 100% byte-identical (`FF7104A95CAF...`).

---

## 3. Flash Execution & Target Partitions

| Partition | Image File | Bytes | SHA256 Hash | Flash Result |
| :--- | :--- | :--- | :--- | :--- |
| `super` | `super.img` | 7,703,526,364 | `727579EE75D3274CFB7270B37CCDDCF6E56E10400E1D393049ACCF69ED519746` | **OKAY** (10 sparse chunks, 199.3s) |
| `vbmeta_system_a` | `vbmeta_system.img` | 131,072 | `E710488DF68CD1485FB5F5B7DF64541C7A98B198B5E87B071406E192B7599B72` | **OKAY** (12.4s) |

- **Userdata / Metadata**: **NOT TOUCHED (Zero wipe / format)**
- **Non-experimental partitions**: **NOT TOUCHED**

---

## 4. Device Slot Snapshot After Flash

```text
product: thyme
current-slot: a
unlocked: yes
is-userspace: no
slot-unbootable:a: no
slot-successful:a: no
slot-retry-count:a: 7
slot-unbootable:b: no
slot-successful:b: no
slot-retry-count:b: 7
```

- **A Slot Retry Budget**: **7 (Fully Restored)**
- **Current Device State**: **Strictly Retained in Bootloader Fastboot**
- **Automatic Reboot**: **FORBIDDEN (None issued)**
