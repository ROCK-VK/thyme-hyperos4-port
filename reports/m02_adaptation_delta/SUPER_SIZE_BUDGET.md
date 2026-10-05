# MADRID-M02 super size budget

Updated: 2026-10-05 21:52 HKT
Status: measured candidate r3 filesystem sizes and validated LP metadata; not boot-tested.

## Physical target and candidate result

| Quantity | Bytes | Meaning |
| --- | ---: | --- |
| thyme physical `super` | 9,126,805,504 | Exact candidate raw size and hard target limit |
| Official Madrid 4.0.19 declared super | 18,790,481,920 | Not usable as thyme size |
| Official Madrid 4.0.19 group maximum | 18,779,996,160 | Do not copy to candidate |
| MADRID-M02 r3 sparse `super.img` | 8,063,690,032 | Image flashed to the shared `super` partition |
| MADRID-M02 r3 expanded raw size | 9,126,805,504 | Exact physical thyme super capacity |
| Six populated A-slot partition extents | 8,140,926,976 | Sum reported by `lpdump` |
| Raw capacity minus A-slot extents | 985,878,528 | Extent residual before accounting separately for LP reserved metadata/alignment |

The candidate was produced by `lpmake` with 64 KiB LP metadata, three metadata slots, 4 KiB logical blocks, 1 MiB alignment, and the exact 9,126,805,504-byte device size. AOSP `lpdump` and the independent parser agree on all partition sizes; geometry, header and tables checksums pass. The B-slot partitions have zero extents. The final sparse super expands to exactly the physical target size. The 985,878,528-byte residual is a raw-capacity comparison, not a claim that all of it is allocatable after LP metadata reservations.

## Per-partition measurements

EROFS allocation is `block count × 4,096`; “file bytes” is the filesystem's original regular-file byte total, while “on-image file bytes” is the compressed data total. They are different quantities. Official declared/image bytes include image padding or footer and are not the minimum rebuilt filesystem requirement. Ext4 rows retain the Known-Good allocations.

| Partition | Official 4.0.19 image/declaration | Official 4.0.19 filesystem / file bytes | Known-Good allocation / file bytes | MADRID-M02 r3 allocation / file bytes | Candidate choice |
| --- | ---: | --- | --- | --- | --- |
| `system` | 977,055,744 B | EROFS 958,676,992 B; files 1,456,429,743 B; on-image data 957,392,585 B | EROFS 959,201,280 B; files 1,457,012,506 B; on-image data 957,915,626 B | EROFS 959,004,672 B; files 1,457,012,506 B; on-image data 957,719,018 B | Known-Good thyme tree + 219 Official 4.0.19 changed paths |
| `system_ext` | 817,614,848 B | EROFS 802,222,080 B; files 1,359,043,464 B; on-image data 801,099,183 B | EROFS 850,153,472 B; files 1,464,497,046 B; on-image data 848,981,637 B | EROFS 849,969,152 B; files 1,464,497,002 B; on-image data 848,797,317 B | Known-Good thyme tree + 60 Official 4.0.19 changed paths, including VNDK30 |
| `product` | 5,667,659,776 B | EROFS 5,561,454,592 B; files 7,164,463,089 B; on-image data 5,557,926,450 B | EROFS 4,110,647,296 B; files 5,451,864,644 B; on-image data 4,107,958,291 B | EROFS 4,109,991,936 B; files 5,451,864,644 B; on-image data 4,107,302,931 B | Known-Good thyme product tree + allowlisted 4.0.19 build properties |
| `vendor` | 1,512,136,704 B | EROFS 1,483,735,040 B; files 1,481,914,107 B | ext4 2,044,887,040 B; used blocks 1,989,791,744 B; tree file bytes 2,024,640,304 B | ext4 2,044,887,040 B; unchanged Known-Good bytes | Preserve thyme hardware stack byte-for-byte |
| `odm` | 5,976,252,416 B | EROFS 5,864,275,968 B; files 5,860,681,948 B | ext4 2,351,104 B; used blocks 1,404,928 B; tree file bytes 1,302,473 B | ext4 2,351,104 B; unchanged Known-Good bytes | Preserve thyme image byte-for-byte |
| `mi_ext` | 173,858,816 B | EROFS 171,126,784 B; files 171,100,557 B | ext4 174,723,072 B; used blocks 173,764,608 B; tree file bytes 172,992,153 B | ext4 174,723,072 B; same-size allowlisted build.prop write | Preserve Known-Good hybrid tree and thyme identity |
| `system_dlkm` | 8,949,760 B | EROFS 8,695,808 B; files 8,674,769 B | Absent | Absent | Omit: Official 6.18.21 modules are not used by the 4.19.325 Known-Good stack or its fstab |
| `vendor_dlkm` | 78,315,520 B | EROFS 76,759,040 B; files 76,619,705 B | Absent | Absent | Omit for the same kernel/fstab compatibility reason |
| `mi_product` | 348,160 B | EROFS 4,096 B; file data 32 B | Absent | Absent | Omit: one-block stub, unmounted and absent from Known-Good |

For ext4 tree file bytes, hard links and sparse files mean the sum of file lengths is not interchangeable with occupied ext4 blocks. The allocation is unchanged from the real Known-Good images; `e2fsck -fn` passed for candidate `mi_ext` and the retained `vendor`/`odm` images.

## Final candidate gate results

- Rebuilt `system_a`, `system_ext_a`, and `product_a` pass `fsck.erofs`.
- All three EROFS round-trips report zero file-tree differences, including path/type/content hash/mode/owner/symlink and readable SELinux/capability metadata checks.
- Candidate `mi_ext_a`, retained `vendor_a`, and `odm_a` pass read-only `e2fsck -fn`.
- LP has exactly the six selected A-slot partitions populated; all six B-slot partitions are empty.
- `lpdump` and the independent parser agree on partition sizes; LP geometry/header/table checksums pass.
- Frozen Known-Good boot-stack hashes match, image inventory and SHA256 manifest agree, both property merges pass allowlists, and the validator reports `passed=true` with no errors.
- Candidate static report: `work/madrid_m02_candidate_r3/metadata/STATIC_GATE_REPORT.json`; image inventory and SHA256 list are under the same candidate's `metadata/` directory.

Static acceptance is complete. This does not establish OS4.0.19 runtime compatibility; the candidate has not yet been flashed or boot-tested.
