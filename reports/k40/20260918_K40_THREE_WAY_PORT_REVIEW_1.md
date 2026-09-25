# K40 三方逆向 Phase 1 独立审核

## 审核结论

`REVERSE_ENGINEERING / IMAGE_READY=false / DEVICE_WRITE_STOP`

本审核独立复核了移植窗口的报告、5 个 TSV、输入目录和关键文件头/脚本。输入路径、文件大小、TSV 列数与 `bad_rows=0` 均可复现；本轮没有设备操作。

## 已复核事实

- K40 官方包存在 `images/super.img`（7,877,133,784 bytes）、`boot.img`（134,217,728）、`vendor_boot.img`（100,663,296）、`dtbo.img`（33,554,432）、metadata 和 rawprogram/partition XML。
- K40 移植包存在 `super.img.zst`（5,108,797,958 bytes）、`firmware-update/boot.img`（201,326,592）、`vendor_boot.img`（100,663,296）、`dtbo.img`（33,554,432）和自定义刷机脚本；脚本确实检查 alioth、解压 zstd、禁用 verity/verification、擦除/刷写双槽并设置 A 槽。
- 移植包脚本引用 `firmware-update/recovery.img`，当前有界清单中未找到该文件；这只能记为包完整性疑点，不能自行补镜像。
- 小米15 OTA 存在 `payload.bin`（8,702,335,155 bytes）和 payload 属性；本轮尚未读取 manifest/分区列表。

## 语义修正

boot/vendor_boot/dtbo 的大小或头字段不同，只能证明“观察到包级差异”，不能单独证明 porter 修改、重编或重建，也不能证明来源。审核要求这些条目按 `UNKNOWN` 加“observed difference”备注处理；`PORTER_MODIFIED` 仅保留给有直接证据的自定义部署/刷机行为。`PORTER_REBUILT` 与 `PORTER_NEW` 仍未证明。

## 批准的唯一下一步

`P1-METADATA-OWNER-SLICE-1`：串行、低内存读取移植 super 的 dynamic-partition metadata 和小米15 OTA CrAU manifest/partition list；不执行 lpunpack，不展开逻辑分区，不构造 thyme 镜像，不刷机。K40 zstd 若必须物化临时 raw，只能在 E 盘明确临时目录中单份处理，结束后删除并记录释放空间。

## 资源/安全

审核时 Free RAM 约 10.97 GiB，Commit 约 29.33/64.22 GiB，C/D/E 可用约 111.81/194.72/192.47 GiB；未发现真实 lpmake/lpunpack/payload/zstd/7z 等目标 worker。未触碰 Docker VHDX、未执行 `wsl --shutdown`、未计算 standalone SHA-256。
