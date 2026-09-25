[CmdletBinding()]
param(
    [switch]$Execute
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $PSScriptRoot
$FastbootExe = Join-Path $Root 'tools\platform-tools\fastboot.exe'
$ImageDir = Join-Path $Root 'work\stage_c_thyme_os4_candidate_13_treble_ion_fix\images'
$ExpectedSerial = '[REDACTED_DEVICE_ID]'
$ExpectedProduct = 'thyme'
$ExpectedSlot = 'a'

$Images = @(
    [pscustomobject]@{ Partition = 'vbmeta_a';        File = 'vbmeta.img';        Bytes = 131072;     Sha256 = '013335BCA9B312E0BEFF737D30903A9B0A1EF829BA19A7BD5802BF83C04F40E9'; DisableVerification = $true }
    [pscustomobject]@{ Partition = 'vbmeta_system_a'; File = 'vbmeta_system.img'; Bytes = 131072;     Sha256 = 'BF4155CD99F125B8CAD26490FD2F3412EA4389F090CE56F36FAA2BF2A759C633'; DisableVerification = $false }
    [pscustomobject]@{ Partition = 'boot_a';          File = 'boot.img';          Bytes = 201326592;  Sha256 = 'E5A016056D5C93C7A886980A7C062617EC44DC06A48417D7DD0F4476708A6368'; DisableVerification = $false }
    [pscustomobject]@{ Partition = 'vendor_boot_a';   File = 'vendor_boot.img';   Bytes = 100663296;  Sha256 = '02333B82BA936F1BAAB1ECAB744632C70F8FC16688A206C7041EF319F112A137'; DisableVerification = $false }
    [pscustomobject]@{ Partition = 'dtbo_a';          File = 'dtbo.img';          Bytes = [REDACTED_DEVICE_ID];   Sha256 = '50E1AC0EDCBD333778217AA6FE8D972F6FF85ADD0DAE8A015A6642C2172DD886'; DisableVerification = $false }
    [pscustomobject]@{ Partition = 'super';           File = 'super.img';         Bytes = 7684274964; Sha256 = '8AFEFDDBCA2357D003DEF055418CC08A832B91EA08EDCB40DEECBEBD42FA2252'; DisableVerification = $false }
)

function Get-FastbootVar([string]$Name) {
    $output = & $FastbootExe -s $ExpectedSerial getvar $Name 2>&1 | Out-String
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        throw "fastboot getvar $Name failed with exit code $exitCode. Output: $output"
    }
    $pattern = "(?m)^\s*(?:\(bootloader\)\s*)?$([regex]::Escape($Name)):\s*(?<value>[^\r\n]+?)\s*$"
    if ($output -match $pattern) {
        return $Matches['value'].Trim()
    }
    throw "Could not read Fastboot variable '$Name'. Output: $output"
}

Write-Host '=== THYME-OS4 CANDIDATE 13 FLASH PREFLIGHT ===' -ForegroundColor Cyan
Write-Host "Candidate images: $ImageDir"
Write-Host "Target: $ExpectedSerial / $ExpectedProduct / slot $ExpectedSlot"
Write-Host "Mode: $(if ($Execute) { 'EXECUTE (DEVICE WRITES)' } else { 'DRY-RUN (NO DEVICE WRITES)' })" -ForegroundColor $(if ($Execute) { 'Red' } else { 'Yellow' })

if (-not (Test-Path -LiteralPath $FastbootExe -PathType Leaf)) {
    throw "Local Fastboot executable missing: $FastbootExe"
}

Write-Host "`n[1/3] Checking all six Candidate 13 images..." -ForegroundColor Cyan
foreach ($image in $Images) {
    $path = Join-Path $ImageDir $image.File
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Candidate image is missing: $path"
    }
    $item = Get-Item -LiteralPath $path
    if ($item.Length -ne $image.Bytes) {
        throw "Size mismatch for $($image.File): expected $($image.Bytes), got $($item.Length)"
    }
    $hash = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToUpperInvariant()
    if ($hash -ne $image.Sha256) {
        throw "SHA256 mismatch for $($image.File): expected $($image.Sha256), got $hash"
    }
    Write-Host "  PASS $($image.File): $($item.Length) bytes, SHA256=$hash" -ForegroundColor Green
}

Write-Host "`n[2/3] Planned sequential writes (super is last):" -ForegroundColor Cyan
foreach ($image in $Images) {
    $path = Join-Path $ImageDir $image.File
    if ($image.DisableVerification) {
        Write-Host "  fastboot -s $ExpectedSerial --disable-verity --disable-verification flash $($image.Partition) `"$path`""
    } else {
        Write-Host "  fastboot -s $ExpectedSerial flash $($image.Partition) `"$path`""
    }
}

if (-not $Execute) {
    Write-Host "`nDRY-RUN complete. No Fastboot device query or device write was issued." -ForegroundColor Yellow
    Write-Host 'To perform device writes, an authorized operator must explicitly pass -Execute.' -ForegroundColor Yellow
    return
}

Write-Host "`n[3/3] Checking the connected Fastboot target before any write..." -ForegroundColor Cyan
$devices = & $FastbootExe devices -l 2>&1 | Out-String
if ($LASTEXITCODE -ne 0 -or $devices -notmatch "(?m)^\s*$([regex]::Escape($ExpectedSerial))\s+fastboot\b") {
    throw "Expected Fastboot device $ExpectedSerial is not connected. Output: $devices"
}
$product = Get-FastbootVar 'product'
$slot = Get-FastbootVar 'current-slot'
$unlocked = Get-FastbootVar 'unlocked'
if ($product -ne $ExpectedProduct) { throw "Product mismatch: expected $ExpectedProduct, got '$product'." }
if ($slot -ne $ExpectedSlot) { throw "Slot mismatch: expected $ExpectedSlot, got '$slot'. Refusing to write." }
if ($unlocked -ne 'yes') { throw "Bootloader is not confirmed unlocked (unlocked='$unlocked'). Refusing to write." }
Write-Host "  PASS serial=$ExpectedSerial product=$product current-slot=$slot unlocked=$unlocked" -ForegroundColor Green

Write-Host "`nWriting Candidate 13 sequentially. Do not disconnect or interrupt the super write." -ForegroundColor Red
foreach ($image in $Images) {
    $path = Join-Path $ImageDir $image.File
    Write-Host "[FLASH] $($image.Partition) <= $($image.File)"
    if ($image.DisableVerification) {
        & $FastbootExe -s $ExpectedSerial --disable-verity --disable-verification flash $image.Partition $path
    } else {
        & $FastbootExe -s $ExpectedSerial flash $image.Partition $path
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Fastboot write failed on $($image.Partition) with exit code $LASTEXITCODE. Sequence stopped; do not retry super automatically."
    }
}

Write-Host "`nCandidate 13 writes completed. The phone remains in Fastboot; this script does not reboot." -ForegroundColor Green
