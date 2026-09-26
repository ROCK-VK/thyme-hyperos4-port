[CmdletBinding()]
param(
    [switch]$Execute,
    [Parameter(Mandatory=$true)][string]$Serial
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $PSScriptRoot
$FastbootExe = Join-Path $Root 'tools\platform-tools\fastboot.exe'
$ImageDir = Join-Path $Root 'work\stage_j_thyme_os4_candidate_20_angle_route_diag_run1\images'
$ManifestPath = Join-Path $ImageDir 'BUILD_MANIFEST.json'
$ExpectedSerial = $Serial.Trim()
$ExpectedProduct = 'thyme'
$ExpectedSlot = 'a'

if ([string]::IsNullOrWhiteSpace($ExpectedSerial)) { throw 'A target device serial is required.' }
if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) { throw "Candidate 20 manifest missing: $ManifestPath" }
$Manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
if ($Manifest.candidate -ne 'Candidate 20 ANGLE EGL route and runtime diagnostics' -or
    $Manifest.base -ne 'Candidate 19 RGBX EGLConfig compatibility experiment') {
    throw 'Build manifest is not the expected C20 image set based on C19.'
}
if ((@($Manifest.flash_scope_prepared) -join ',') -ne 'super,vbmeta_system_a') {
    throw 'Unexpected C20 prepared flash scope.'
}

$ExpectedImageNames = @('boot.img', 'vendor_boot.img', 'dtbo.img', 'vbmeta.img', 'vbmeta_system.img', 'super.img')
$ManifestImageNames = @($Manifest.images.PSObject.Properties.Name | Sort-Object)
if (Compare-Object ($ExpectedImageNames | Sort-Object) $ManifestImageNames) {
    throw 'C20 manifest does not contain exactly the expected six-image set.'
}
$Targets = @(
    [pscustomobject]@{ Partition='super'; File='super.img' }
    [pscustomobject]@{ Partition='vbmeta_system_a'; File='vbmeta_system.img' }
)

function Get-FastbootVar([string]$Name) {
    $output = & $FastbootExe -s $ExpectedSerial getvar $Name 2>&1 | Out-String
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) { throw "fastboot getvar $Name failed ($exitCode): $output" }
    $pattern = "(?m)^\s*(?:\(bootloader\)\s*)?$([regex]::Escape($Name)):\s*(?<value>[^\r\n]+?)\s*$"
    if ($output -match $pattern) { return $Matches['value'].Trim() }
    throw "Could not read Fastboot variable '$Name'. Output: $output"
}

Write-Host '=== THYME-OS4 CANDIDATE 20 ANGLE EGL PREFLIGHT ===' -ForegroundColor Cyan
Write-Host "Images: $ImageDir"
Write-Host "Target: $ExpectedSerial / $ExpectedProduct / slot $ExpectedSlot"
Write-Host "Mode: $(if ($Execute) { 'EXECUTE (DEVICE WRITES)' } else { 'DRY-RUN (NO DEVICE WRITES)' })" -ForegroundColor $(if ($Execute) { 'Red' } else { 'Yellow' })

foreach ($Target in $Targets) {
    $Path = Join-Path $ImageDir $Target.File
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "C20 image missing: $Path" }
    $Item = Get-Item -LiteralPath $Path
    $Expected = $Manifest.images.PSObject.Properties[$Target.File].Value
    $Hash = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToUpperInvariant()
    if ([int64]$Item.Length -ne [int64]$Expected.bytes -or $Hash -ne $Expected.sha256.ToUpperInvariant()) {
        throw "C20 manifest/image mismatch: $($Target.File)"
    }
    Write-Host "PASS $($Target.File): $($Item.Length) bytes SHA256=$Hash" -ForegroundColor Green
}

Write-Host ''
Write-Host '[Planned sequential writes]' -ForegroundColor Cyan
foreach ($Target in $Targets) {
    Write-Host ('  fastboot -s ' + $ExpectedSerial + ' flash ' + $Target.Partition + ' ' + (Join-Path $ImageDir $Target.File))
}
Write-Host 'Only super and vbmeta_system_a are in scope. No wipe, other partition write, lock, or reboot is included.'
Write-Host 'The large super write runs as one uninterrupted Fastboot command; keep USB connected.' -ForegroundColor Yellow
if (-not $Execute) {
    Write-Host 'DRY-RUN complete. No device query or write was issued.' -ForegroundColor Yellow
    return
}
if (-not (Test-Path -LiteralPath $FastbootExe -PathType Leaf)) { throw "Local Fastboot executable missing: $FastbootExe" }

$Devices = & $FastbootExe devices -l 2>&1 | Out-String
if ($LASTEXITCODE -ne 0 -or $Devices -notmatch "(?m)^\s*$([regex]::Escape($ExpectedSerial))\s+fastboot\b") {
    throw "Expected Bootloader Fastboot device $ExpectedSerial is not connected. Output: $Devices"
}
$Product = Get-FastbootVar 'product'
$Slot = Get-FastbootVar 'current-slot'
$Unlocked = Get-FastbootVar 'unlocked'
$Userspace = Get-FastbootVar 'is-userspace'
$Unbootable = Get-FastbootVar 'slot-unbootable:a'
if ($Product -ne $ExpectedProduct -or $Slot -ne $ExpectedSlot -or $Unlocked -ne 'yes' -or
    $Userspace -ne 'no' -or $Unbootable -ne 'no') {
    throw "Target preflight mismatch: product=$Product slot=$Slot unlocked=$Unlocked is-userspace=$Userspace unbootable_a=$Unbootable; no writes issued."
}
Write-Host "PASS serial=$ExpectedSerial product=$Product slot=$Slot unlocked=$Unlocked is-userspace=$Userspace unbootable_a=$Unbootable" -ForegroundColor Green

foreach ($Target in $Targets) {
    $Path = Join-Path $ImageDir $Target.File
    Write-Host "[FLASH] $($Target.Partition) <= $($Target.File)"
    & $FastbootExe -s $ExpectedSerial flash $Target.Partition $Path
    if ($LASTEXITCODE -ne 0) { throw "Fastboot failed on $($Target.Partition) ($LASTEXITCODE); stopped without retry or reboot." }
}
Write-Host 'C20 writes completed. Device remains in Bootloader Fastboot; no reboot was issued.' -ForegroundColor Green
