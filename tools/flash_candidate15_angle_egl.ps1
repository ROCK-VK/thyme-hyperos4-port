[CmdletBinding()]
param(
    [switch]$Execute,
    [string]$Serial = '[REDACTED_DEVICE_ID]'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $PSScriptRoot
$FastbootExe = Join-Path $Root 'tools\platform-tools\fastboot.exe'
$ImageDir = Join-Path $Root 'work\stage_e_thyme_os4_candidate_15_angle_egl_run1\images'
$ManifestPath = Join-Path $ImageDir 'BUILD_MANIFEST.json'
$ExpectedSerial = $Serial
$ExpectedSerial = $ExpectedSerial.Trim()
if ([string]::IsNullOrWhiteSpace($ExpectedSerial)) { throw 'A target device serial is required.' }
$ExpectedProduct = 'thyme'
$ExpectedSlot = 'a'

$Targets = @(
    [pscustomobject]@{
        Partition = 'vbmeta_system_a'
        File = 'vbmeta_system.img'
        Bytes = 131072
        Sha256 = '634EB12F681ECFFFF5E07CEF633377F5C16903E32901AFE7B6EF56FE4D5A4190'
    }
    [pscustomobject]@{
        Partition = 'super'
        File = 'super.img'
        Bytes = 7684274964
        Sha256 = '4CD34B53A7E47E25522C191AC748B8EE91348091C9B0F31FF59EC677CF8C9B56'
    }
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

Write-Host '=== THYME-OS4 CANDIDATE 15 ANGLE EGL FLASH PREFLIGHT ===' -ForegroundColor Cyan
Write-Host "Candidate images: $ImageDir"
Write-Host "Target: $ExpectedSerial / $ExpectedProduct / slot $ExpectedSlot"
Write-Host "Mode: $(if ($Execute) { 'EXECUTE (DEVICE WRITES)' } else { 'DRY-RUN (NO DEVICE WRITES)' })" -ForegroundColor $(if ($Execute) { 'Red' } else { 'Yellow' })

if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) {
    throw "Candidate 15 build manifest missing: $ManifestPath"
}
$Manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
if ($Manifest.candidate -ne 'Candidate 15 ANGLE EGL diagnostic' -or $Manifest.base -ne 'Candidate 14 BPF bootstrap bypass run5') {
    throw 'Build manifest does not identify the expected Candidate 15 / Candidate 14 base.'
}
$ManifestScope = @($Manifest.flash_scope_prepared)
if (($ManifestScope -join ',') -ne 'vbmeta_system_a,super') {
    throw "Unexpected prepared flash scope: $($ManifestScope -join ',')"
}
$ExpectedImageNames = @('boot.img', 'vendor_boot.img', 'dtbo.img', 'vbmeta.img', 'vbmeta_system.img', 'super.img')
$ManifestImageNames = @($Manifest.images.PSObject.Properties.Name | Sort-Object)
if (Compare-Object ($ExpectedImageNames | Sort-Object) $ManifestImageNames) {
    throw 'Candidate 15 manifest does not contain exactly the expected six-image set.'
}

Write-Host ''
Write-Host '[1/3] Checking the two Candidate 15 images to be written...' -ForegroundColor Cyan
foreach ($Image in $Targets) {
    $Path = Join-Path $ImageDir $Image.File
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Candidate image is missing: $Path"
    }
    $Item = Get-Item -LiteralPath $Path
    if ($Item.Length -ne $Image.Bytes) {
        throw "Size mismatch for $($Image.File): expected $($Image.Bytes), got $($Item.Length)"
    }
    $ManifestImage = $Manifest.images.PSObject.Properties[$Image.File].Value
    if ([int64]$ManifestImage.bytes -ne $Image.Bytes -or $ManifestImage.sha256.ToUpperInvariant() -ne $Image.Sha256) {
        throw "Build manifest mismatch for $($Image.File)."
    }
    $Hash = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToUpperInvariant()
    if ($Hash -ne $Image.Sha256) {
        throw "SHA256 mismatch for $($Image.File): expected $($Image.Sha256), got $Hash"
    }
    Write-Host "  PASS $($Image.File): $($Item.Length) bytes, SHA256=$Hash" -ForegroundColor Green
}

Write-Host ''
Write-Host '[2/3] Planned sequential writes:' -ForegroundColor Cyan
foreach ($Image in $Targets) {
    $Path = Join-Path $ImageDir $Image.File
    Write-Host ('  fastboot -s ' + $ExpectedSerial + ' flash ' + $Image.Partition + ' ' + $Path)
}
Write-Host 'No data erase, other partition write, bootloader-state operation, or reboot is included.'

if (-not $Execute) {
    Write-Host ''
    Write-Host 'DRY-RUN complete. No Fastboot device query or device write was issued.' -ForegroundColor Yellow
    Write-Host 'An authorized operator must explicitly pass -Execute to write the two listed partitions.' -ForegroundColor Yellow
    return
}

if (-not (Test-Path -LiteralPath $FastbootExe -PathType Leaf)) {
    throw "Local Fastboot executable missing: $FastbootExe"
}

Write-Host ''
Write-Host '[3/3] Checking the connected Fastboot target before any write...' -ForegroundColor Cyan
$Devices = & $FastbootExe devices -l 2>&1 | Out-String
if ($LASTEXITCODE -ne 0 -or $Devices -notmatch "(?m)^\s*$([regex]::Escape($ExpectedSerial))\s+fastboot\b") {
    throw "Expected Fastboot device $ExpectedSerial is not connected. Output: $Devices"
}
$Product = Get-FastbootVar 'product'
$Slot = Get-FastbootVar 'current-slot'
$Unlocked = Get-FastbootVar 'unlocked'
$Userspace = Get-FastbootVar 'is-userspace'
if ($Product -ne $ExpectedProduct) { throw "Product mismatch: expected $ExpectedProduct, got '$Product'." }
if ($Slot -ne $ExpectedSlot) { throw "Slot mismatch: expected $ExpectedSlot, got '$Slot'. Refusing to write." }
if ($Unlocked -ne 'yes') { throw "Bootloader is not confirmed unlocked (unlocked='$Unlocked'). Refusing to write." }
if ($Userspace -ne 'no') { throw "Device is not in bootloader Fastboot (is-userspace='$Userspace'). Refusing to write." }
Write-Host "  PASS serial=$ExpectedSerial product=$Product current-slot=$Slot unlocked=$Unlocked is-userspace=$Userspace" -ForegroundColor Green

Write-Host ''
Write-Host 'Writing Candidate 15 sequentially. Keep USB connected and do not interrupt the super write.' -ForegroundColor Red
foreach ($Image in $Targets) {
    $Path = Join-Path $ImageDir $Image.File
    Write-Host "[FLASH] $($Image.Partition) <= $($Image.File)"
    & $FastbootExe -s $ExpectedSerial flash $Image.Partition $Path
    if ($LASTEXITCODE -ne 0) {
        throw "Fastboot write failed on $($Image.Partition) with exit code $LASTEXITCODE. Sequence stopped; no retry or reboot was issued."
    }
}

Write-Host ''
Write-Host 'Candidate 15 writes completed. The phone remains in Fastboot; this script does not reboot.' -ForegroundColor Green
