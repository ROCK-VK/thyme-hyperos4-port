[CmdletBinding()]
param(
    [switch]$Execute,
    [Parameter(Mandatory=$true)][string]$Serial = ''
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$FastbootExe = Join-Path $Root 'tools\platform-tools\fastboot.exe'
$ImageDir = Join-Path $Root 'work\stage_c27_netd_zygote_cycle_break_20260929_run1\images'
$ManifestPath = Join-Path $ImageDir 'BUILD_MANIFEST.json'
$ExpectedSerial = $Serial.Trim()
$ExpectedProduct = 'thyme'
$ExpectedSlot = 'a'

if ([string]::IsNullOrWhiteSpace($ExpectedSerial)) { throw 'Pass the freshly verified Fastboot serial with -Serial.' }
if (-not (Test-Path -LiteralPath $FastbootExe -PathType Leaf)) { throw "Local Fastboot executable missing: $FastbootExe" }
if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) { throw "C27 manifest missing: $ManifestPath" }
$Manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
if ($Manifest.candidate -ne 'Candidate 27 netd-to-Zygote restart-cycle fix and diagnostic' -or
    $Manifest.base -ne 'Candidate 26 Zygote first-exit diagnostic') {
    throw 'Manifest is not the expected C27 image set based on C26.'
}
if ((@($Manifest.flash_scope_prepared) -join ',') -ne 'super,vbmeta_system_a') {
    throw 'Unexpected C27 flash scope.'
}
$ExpectedImageNames = @('boot.img', 'vendor_boot.img', 'dtbo.img', 'vbmeta.img', 'vbmeta_system.img', 'super.img')
$ManifestImageNames = @($Manifest.images.PSObject.Properties.Name | Sort-Object)
if (Compare-Object ($ExpectedImageNames | Sort-Object) $ManifestImageNames) { throw 'C27 manifest does not contain exactly six images.' }
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

Write-Host '=== THYME-OS4 CANDIDATE 27 PREFLIGHT ===' -ForegroundColor Cyan
Write-Host "Images: $ImageDir"
Write-Host "Target: $ExpectedSerial / $ExpectedProduct / slot $ExpectedSlot"
Write-Host "Mode: $(if ($Execute) { 'EXECUTE (DEVICE WRITES)' } else { 'DRY-RUN (NO DEVICE WRITES)' })" -ForegroundColor $(if ($Execute) { 'Red' } else { 'Yellow' })
Write-Host 'Change: bounded Zygote/logcat diagnostics; writes limited to super and vbmeta_system_a.' -ForegroundColor Yellow

foreach ($Target in $Targets) {
    $Path = Join-Path $ImageDir $Target.File
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "C27 image missing: $Path" }
    $Item = Get-Item -LiteralPath $Path
    $Expected = $Manifest.images.PSObject.Properties[$Target.File].Value
    $Hash = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToUpperInvariant()
    if ([int64]$Item.Length -ne [int64]$Expected.bytes -or $Hash -ne $Expected.sha256.ToUpperInvariant()) {
        throw "C27 manifest/image mismatch: $($Target.File)"
    }
    Write-Host "PASS $($Target.File): $($Item.Length) bytes SHA256=$Hash" -ForegroundColor Green
}

Write-Host ''
Write-Host '[Planned sequential writes]' -ForegroundColor Cyan
foreach ($Target in $Targets) { Write-Host ('  fastboot -s ' + $ExpectedSerial + ' flash ' + $Target.Partition + ' ' + (Join-Path $ImageDir $Target.File)) }
Write-Host 'No wipe, other partition write, lock, slot switch, misc/BCB operation, or reboot is included.'
if (-not $Execute) { Write-Host 'DRY-RUN complete. No device query or write was issued.' -ForegroundColor Yellow; return }

$Devices = & $FastbootExe devices -l 2>&1 | Out-String
if ($LASTEXITCODE -ne 0) { throw "fastboot devices failed: $Devices" }
$DeviceLines = @($Devices -split "`r?`n" | Where-Object { $_.Trim() })
if ($DeviceLines.Count -ne 1 -or $DeviceLines[0] -notmatch "^\s*$([regex]::Escape($ExpectedSerial))\s+fastboot\b") {
    throw "Expected exactly one Bootloader Fastboot device $ExpectedSerial. Output: $Devices"
}
$Product = Get-FastbootVar 'product'
$Slot = Get-FastbootVar 'current-slot'
$Unlocked = Get-FastbootVar 'unlocked'
$Userspace = Get-FastbootVar 'is-userspace'
$Unbootable = Get-FastbootVar 'slot-unbootable:a'
$Successful = Get-FastbootVar 'slot-successful:a'
$Retry = Get-FastbootVar 'slot-retry-count:a'
if ($Product -ne $ExpectedProduct -or $Slot -ne $ExpectedSlot -or $Unlocked -ne 'yes' -or
    $Userspace -ne 'no' -or $Unbootable -ne 'no' -or [int]$Retry -le 0) {
    throw "Target preflight mismatch or A slot not bootable: product=$Product slot=$Slot unlocked=$Unlocked is-userspace=$Userspace unbootable_a=$Unbootable successful_a=$Successful retry_a=$Retry; no writes issued."
}
Write-Host "PASS serial=$ExpectedSerial product=$Product slot=$Slot unlocked=$Unlocked is-userspace=$Userspace A(unbootable=$Unbootable successful=$Successful retry=$Retry)" -ForegroundColor Green

foreach ($Target in $Targets) {
    $Path = Join-Path $ImageDir $Target.File
    Write-Host "[FLASH] $($Target.Partition) <= $($Target.File)"
    & $FastbootExe -s $ExpectedSerial flash $Target.Partition $Path
    if ($LASTEXITCODE -ne 0) { throw "Fastboot failed on $($Target.Partition) ($LASTEXITCODE); stopped without retry or reboot." }
}

$AfterDevices = & $FastbootExe devices -l 2>&1 | Out-String
if ($LASTEXITCODE -ne 0 -or $AfterDevices -notmatch "(?m)^\s*$([regex]::Escape($ExpectedSerial))\s+fastboot\b") {
    throw "Writes returned successfully, but the device is no longer enumerated in Fastboot. No reboot issued. Output: $AfterDevices"
}
$AfterProduct = Get-FastbootVar 'product'
$AfterSlot = Get-FastbootVar 'current-slot'
$AfterUnlocked = Get-FastbootVar 'unlocked'
$AfterUserspace = Get-FastbootVar 'is-userspace'
if ($AfterProduct -ne $ExpectedProduct -or $AfterSlot -ne $ExpectedSlot -or
    $AfterUnlocked -ne 'yes' -or $AfterUserspace -ne 'no') {
    throw "Writes returned, but final Fastboot state differs: product=$AfterProduct slot=$AfterSlot unlocked=$AfterUnlocked is-userspace=$AfterUserspace. No reboot issued."
}
Write-Host 'C27 writes completed. Device remains in Bootloader Fastboot; no reboot or data wipe was issued.' -ForegroundColor Green
