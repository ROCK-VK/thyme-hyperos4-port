# Candidate 44 Build and Runtime Equivalence Gate Readiness Report

**Candidate ID**: THYME-OS4 Candidate 44  
**Date**: 2026-10-04 17:15 HKT  
**Base Candidate**: Candidate 43 Netd eBPF Init Abort Surgical Bypass  
**Device Target**: Xiaomi 10S (`thyme` / Snapdragon 870)  
**Host Architecture / Work Environment**: Windows 11 Host + Ubuntu WSL2 Build Pipeline  

---

## 1. Executive Summary & Single-Variable Scope

Candidate 44 strictly and surgically resolves the CAPEX packaging defect identified on Candidate 43's first boot:
- **Root Cause from C43 First Boot**: `apexd` failed to decompress and activate `/system/apex/com.android.tethering.capex` due to:
  `Root digest of ... does not match with expected root digest in /system/apex/com.android.tethering.capex`
  The outer container manifest retained the legacy factory root digest (`[REDACTED_DEVICE_ID]...`), while the internal patched payload had root digest `[REDACTED_DEVICE_ID]...`.
- **Candidate 44 Solution**:
  1. Reuses the **EXACT byte-for-byte C43 `original_apex`** (`c6c010d1d829ac138e0c93889728167202c8f510b3f5948fe900cc2006cfbfd3`), containing the 4-byte NOP patch in `libnetd_updatable.so` (`a70a3176b82d792cdea3ed876c90980c1d459fbcdb859d5e21f12c3a5eaf92f5`). No modification was made to the inner APEX.
  2. Maintained version `370400000` (varint `\x80\xb6\xcf\xb0\x01`) identically between inner and outer manifests.
  3. Extracted actual AVB root digest from `apex_payload.img` via `avbtool print_partition_digests`:
     `4bdfe2f9158035e7d4dd5efe814f5d1dd9eee1d9052eb7c1f571125e9c67e042`.
  4. Injected this exact root digest into `capexMetadata.originalApexDigest` of the outer `apex_manifest.pb` (length 666 bytes).
  5. Reassembled and signed the CAPEX container with `apksigner` (v3 scheme).
  6. Built `system_c44.img`, verified single-variable isolation against C40 baseline (strictly 1 file modified: `system/apex/com.android.tethering.capex`).
  7. Performed dual runtime equivalence gates on both **STAGING CAPEX** and **EROFS READBACK CAPEX** extracted directly from `system_c44.img`.
  8. Regenerated `vbmeta_system.img` with updated system hashtree descriptor and rebuilt `super.img` with `lpmake`.

---

## 2. Forensic Compliance & Standalone Salvage Verification

Per project safety and forensic audit guidelines, C43 Standalone RAM diagnostics were audited:
- Location: `reports/c43_candidate43_build_20261004/standalone/run_20261004_152655/`
- Full file manifest (`FILE_MANIFEST.csv`), SHA256 list (`SHA256SUMS.txt`), and timeline (`host_salvage_timeline.csv`) are 100% complete and validated.
- Preserved artifacts:
  - `console-ramoops-0`: 1,571,670 B (SHA256: `6B6CADA12C63C36B8E42B16FE0EFE22907DEB91729733138FF8BFD55DA74CB8F`)
  - `pmsg-ramoops-0`: 1,462,944 B (SHA256: `34FA6B38AA0DC030B16BF0A6C614B00595688E881968CBD2A436B54EC320787D`)
  - `dmesg_diag_boot.txt`: 155,211 B
  - `oops.raw`: 16,777,216 B

---

## 3. Host Storage Gate

- Drive C Free: 81.63 GiB (> 50 GiB Gate PASS)
- Drive D Free: 172.48 GiB (> 50 GiB Gate PASS)
- Drive E Free: 358.77 GiB (> 50 GiB Gate PASS)
- Docker Desktop / WSL data: 100% untouched.

---

## 4. Candidate 44 Asset Inventory & Hash Manifest

| Asset | Size (bytes) | SHA256 Hash | Notes |
| :--- | :--- | :--- | :--- |
| `original_apex` (Inner) | 36,462,592 | `c6c010d1d829ac138e0c93889728167202c8f510b3f5948fe900cc2006cfbfd3` | 100% Byte-identical to C43 |
| `libnetd_updatable.so` | 103,648 | `a70a3176b82d792cdea3ed876c90980c1d459fbcdb859d5e21f12c3a5eaf92f5` | 4-byte NOP patch retained |
| `apex_payload.img` Root Digest | - | `4bdfe2f9158035e7d4dd5efe814f5d1dd9eee1d9052eb7c1f571125e9c67e042` | Computed via `avbtool` |
| `com.android.tethering.capex` | 17,297,936 | `FF7104A95CAF4C25A20DB20691358C53A2FAF1E27574F6D01BC6BD3FB2A75A31` | Outer manifest digest injected |
| `system_c44.img` | 1,092,616,192 | `6493E92E2F7841725988D292B9CACB8F3B2305096531B21C2F4E198BD8087E37` | Root Digest: `c57ba49264...` |
| `vbmeta_system.img` | 131,072 | `E710488DF68CD1485FB5F5B7DF64541C7A98B198B5E87B071406E192B7599B72` | Algorithm NONE, 128 KiB padded |
| `super.img` | 7,703,526,364 | `727579EE75D3274CFB7270B37CCDDCF6E56E10400E1D393049ACCF69ED519746` | Sparse LP image (6 dynamic parts) |

---

## 5. Runtime Equivalence & Verification Gates

1. **Gate 1: Package Name Alignment**
   - Outer manifest package: `com.android.tethering`
   - Inner manifest package: `com.android.tethering`
   - Result: **PASS**

2. **Gate 2: Version Alignment**
   - Outer manifest version: `370400000` (varint `\x80\xb6\xcf\xb0\x01`)
   - Inner manifest version: `370400000` (varint `\x80\xb6\xcf\xb0\x01`)
   - Result: **PASS**

3. **Gate 3: Public Key Identity**
   - Inner `apex_pubkey` SHA1: `944fdf0f06b2c517710befe752a8931b3d4d3ca8`
   - Outer `apex_pubkey` SHA1: `944fdf0f06b2c517710befe752a8931b3d4d3ca8`
   - Result: **PASS**

4. **Gate 4: Digest Alignment (The Critical Fix)**
   - Outer manifest `capexMetadata.originalApexDigest`: `4bdfe2f9158035e7d4dd5efe814f5d1dd9eee1d9052eb7c1f571125e9c67e042`
   - Actual payload root digest (`avbtool print_partition_digests`): `4bdfe2f9158035e7d4dd5efe814f5d1dd9eee1d9052eb7c1f571125e9c67e042`
   - Exact string & byte equivalence: **PASS**

5. **Gate 5: APK Signature Scheme v3**
   - Verified using v3 scheme: `true`
   - Result: **PASS**

6. **Gate 6: EROFS Readback Verification**
   - File extracted from `system_c44.img` via `dump.erofs --cat`: `extracted_readback.capex`
   - Staging CAPEX SHA256: `FF7104A95CAF4C25A20DB20691358C53A2FAF1E27574F6D01BC6BD3FB2A75A31`
   - Readback CAPEX SHA256: `FF7104A95CAF4C25A20DB20691358C53A2FAF1E27574F6D01BC6BD3FB2A75A31`
   - Readback runtime equivalence check: **100% PASS**

7. **Gate 7: Single-Variable Tree Isolation**
   - Diff against C40 baseline: strictly 1 file (`system/apex/com.android.tethering.capex`)
   - C40 Media Profiles fix (`ro.media.xml_variant.codecs=_V1_0`): **VERIFIED PRESENT**
   - Result: **PASS**

8. **Gate 8: LP Metadata Verification**
   - `simg2img` + `lpdump` verified all 6 logical partitions (`mi_ext_a`, `odm_a`, `product_a`, `system_a`, `system_ext_a`, `vendor_a`).
   - Result: **PASS**

---

## 6. Flash Readiness

- Flashing tool: `tools/flash_candidate44.ps1`
- Target partitions: strictly `super` and `vbmeta_system_a`
- Userdata / Metadata: 100% untouched (no wipe / format)
- Automatic reboot: **STRICTLY FORBIDDEN** (will stay in Bootloader Fastboot after write)
- Device prerequisite: User needs to switch device `[REDACTED_DEVICE_ID]` from Standalone Diagnostic mode back to Bootloader Fastboot (hold Power + Vol Down).
