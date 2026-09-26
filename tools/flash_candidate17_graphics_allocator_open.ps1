[CmdletBinding()]
param(
    [switch]$Execute,
    [string]$Serial = '[REDACTED_DEVICE_ID]'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $PSScriptRoot
$FastbootExe = Join-Path $Root 'tools\platform-tools\fastboot.exe'
$ImageDir = Join-Path $Root 'work\stage_g_thyme_os4_candidate_17_graphics_allocator_open_run1\images'
$ManifestPath = Join-Path $ImageDir 'BUILD_MANIFEST.json'
$ExpectedSerial = $Serial.Trim()
$ExpectedProduct = 'thyme'
$ExpectedSlot = 'a'

if ([string]::IsNullOrWhiteSpace($ExpectedSerial)) { throw 'A target device serial is required.' }
if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) { throw "Candidate 17 manifest missing: $ManifestPath" }
$Manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
if ($Manifest.candidate -ne 'Candidate 17 graphics allocator ion_device open fix' -or
    $Manifest.base -ne 'Candidate 16 graphics allocator ion_device read fix') {
    throw 'Build manifest does not identify the expected Candidate 17 / Candidate 16 base.'
}
if ((@($Manifest.flash_scope_prepared) -join ',') -ne 'vbmeta_system_a,super') {
    throw 'Unexpected prepared flash scope.'
}

$Targets = @(
    [pscustomobject]@{ Partition='vbmeta_system_a'; File='vbmeta_system.img' }
    [pscustomobject]@{ Partition='super'; File='super.img' }
)
$ExpectedImageNames = @('boot.img', 'vendor_boot.img', 'dtbo.img', 'vbmeta.img', 'vbmeta_system.img', 'super.img')
$ManifestImageNames = @($Manifest.images.PSObject.Properties.Name | Sort-Object)
if (Compare-Object ($ExpectedImageNames | Sort-Object) $ManifestImageNames) {
    throw 'Candidate 17 manifest does not contain exactly the expected six-image set.'
}

function Get-FastbootVar([string]$Name) {
    $output = & $FastbootExe -s $ExpectedSerial getvar $Name 2>&1 | Out-String
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) { throw "fastboot getvar $Name failed ($exitCode): $output" }
    $pattern = "(?m)^\s*(?:\(bootloader\)\s*)?$([regex]::Escape($Name)):\s*(?<value>[^\r\n]+?)\s*$"
    if ($output -match $pattern) { return $Matches['value'].Trim() }
    throw "Could not read Fastboot variable '$Name'. Output: $output"
}

Write-Host '=== THYME-OS4 CANDIDATE 17 GRAPHICS ALLOCATOR OPEN PREFLIGHT ===' -ForegroundColor Cyan
Write-Host "Candidate images: $ImageDir"
Write-Host "Target: $ExpectedSerial / $ExpectedProduct / slot $ExpectedSlot"
Write-Host "Mode: $(if ($Execute) { 'EXECUTE (DEVICE WRITES)' } else { 'DRY-RUN (NO DEVICE WRITES)' })" -ForegroundColor $(if ($Execute) { 'Red' } else { 'Yellow' })

foreach ($Target in $Targets) {
    $Path = Join-Path $ImageDir $Target.File
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "Candidate image missing: $Path" }
    $Image = Get-Item -LiteralPath $Path
    $Expected = $Manifest.images.PSObject.Properties[$Target.File].Value
    $Hash = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToUpperInvariant()
    if ([int64]$Image.Length -ne [int64]$Expected.bytes -or $Hash -ne $Expected.sha256.ToUpperInvariant()) {
        throw "Candidate 17 manifest/image mismatch: $($Target.File)"
    }
    Write-Host "PASS $($Target.File): $($Image.Length) bytes SHA256=$Hash" -ForegroundColor Green
}

Write-Host ''
Write-Host '[Planned sequential writes]' -ForegroundColor Cyan
foreach ($Target in $Targets) {
    Write-Host ('  fastboot -s ' + $ExpectedSerial + ' flash ' + $Target.Partition + ' ' + (Join-Path $ImageDir $Target.File))
}
Write-Host 'Only vbmeta_system_a and super are in scope. No erase, other partition write, or reboot is included.'

if (-not $Execute) {
    Write-Host 'DRY-RUN complete. No Fastboot device query or device write was issued.' -ForegroundColor Yellow
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
if ($Product -ne $ExpectedProduct -or $Slot -ne $ExpectedSlot -or $Unlocked -ne 'yes' -or $Userspace -ne 'no') {
    throw "Target preflight mismatch: product=$Product slot=$Slot unlocked=$Unlocked is-userspace=$Userspace; no writes issued."
}
Write-Host "PASS serial=$ExpectedSerial product=$Product slot=$Slot unlocked=$Unlocked is-userspace=$Userspace" -ForegroundColor Green

foreach ($Target in $Targets) {
    Write-Host "[FLASH] $($Target.Partition) <= $($Target.File)"
    & $FastbootExe -s $ExpectedSerial flash $Target.Partition (Join-Path $ImageDir $Target.File)
    if ($LASTEXITCODE -ne 0) { throw "Fastboot failed on $($Target.Partition) ($LASTEXITCODE); stopped without retry or reboot." }
}
Write-Host 'Candidate 17 writes completed. Device remains in Fastboot; no reboot was issued.' -ForegroundColor Green
