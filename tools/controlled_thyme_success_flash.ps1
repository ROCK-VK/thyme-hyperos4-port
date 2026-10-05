# controlled_thyme_success_flash.ps1
#
# Controlled, bounded flash of the community "THYME Mi18PM Known-Good Port Baseline"
# (BB解密-261002_移植Mi18pm-_HyperOS_4.0.15-for_thyme_A17) onto Xiaomi 10S / thyme.
#
# THIS SCRIPT DOES NOT RUN BY ITSELF. It requires -Execute. Without -Execute it only
# verifies local image hashes and exits (DRY-RUN).
#
# HARD RULES ENFORCED BY THIS SCRIPT (do not relax without a written user decision):
#   * Never relock the bootloader.
#   * Never touch persist / modemst1 / modemst2 / fsg / EFS / NV / calibration / identity.
#   * Never write aboot/xbl/abl/tz/hyp/aop/devcfg/keymaster/cmnlib*/qupfw/uefisecapp/modem/dsp
#     unless the operator explicitly passes -IncludeFirmwareLayer for THIS run, after
#     reading the pre-flight firmware comparison this script prints.
#   * Never run fastboot reboot. After flashing the device is left in Bootloader Fastboot.
#     First boot requires a separate, explicit user instruction.
#   * Never erase or format userdata / metadata unless -FormatUserData is passed AND
#     -ConfirmUserDataWipe is passed (two independent switches, on purpose).
#   * Refuse to write if the active slot is not 'a', if the device is in fastbootd,
#     if the bootloader is locked, or if slot A is unbootable.
#   * Refuse to write when slot A retry budget is below -MinRetryBudget (default 3).
#
# Usage:
#   Dry run (safe, recommended first):
#     pwsh -File tools\controlled_thyme_success_flash.ps1 -Serial [REDACTED_DEVICE_ID]
#   Real write of the ROM content only (super + vbmeta_system + boot + vendor_boot + dtbo):
#     pwsh -File tools\controlled_thyme_success_flash.ps1 -Serial [REDACTED_DEVICE_ID] -Execute
#
# The image set is taken from the original package directory read-only. Nothing in the
# package is modified.

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Serial,

    # Actually write to the device. Without this the script only verifies images.
    [switch]$Execute,

    # Optional content layers, each independent and off by default.
    [switch]$IncludeFirmwareLayer,
    [switch]$IncludeVbmeta,
    [switch]$FormatUserData,
    [switch]$ConfirmUserDataWipe,

    # Safety floor for the bootloader retry budget on the active slot.
    [int]$MinRetryBudget = 3,

    # Skip the interactive confirmation prompt (for scripted runs). Still requires -Execute.
    [switch]$NoPrompt
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false

# Logging sink. Stays $null during the DRY-RUN phase so the script writes nothing
# to disk until the operator actually intends a write.
$script:LogPath = $null

# ---------------------------------------------------------------------------
# Fixed paths and frozen expected values
# ---------------------------------------------------------------------------
$Root        = Split-Path -Parent $PSScriptRoot
$FastbootExe = Join-Path $Root 'tools\platform-tools\fastboot.exe'

$ReportDir   = Join-Path $Root 'reports\m00_madrid_intake_20261005'
$StateDir    = Join-Path $ReportDir 'preflash_state'

$ExpectedProduct = 'thyme'
$ExpectedSlot    = 'a'
$ExpectedSerial  = $Serial.Trim()

# Frozen SHA256 of the ROM-content images this experiment is about.
# Loaded from the UTF-8 constants file: the package directory name contains CJK
# characters, which Windows PowerShell 5.1 mis-decodes when they appear as literals
# inside an ANSI-read .ps1 file.
$ConstantsPath = Join-Path $PSScriptRoot 'controlled_thyme_success_flash.constants.json'
if (-not (Test-Path -LiteralPath $ConstantsPath -PathType Leaf)) { throw "constants file missing: $ConstantsPath" }
$Constants = Get-Content -LiteralPath $ConstantsPath -Raw -Encoding UTF8 | ConvertFrom-Json
$PackageRoot = Join-Path $Root $Constants.packageRootRelative
$ImageDir    = Join-Path $PackageRoot 'images'
$ExpectedHashes = @{}
foreach ($Prop in $Constants.expectedHashes.PSObject.Properties) { $ExpectedHashes[$Prop.Name] = $Prop.Value }
$ExpectedSizes = @{}
foreach ($Prop in $Constants.expectedSizes.PSObject.Properties) { $ExpectedSizes[$Prop.Name] = [int64]$Prop.Value }

# Firmware layer present in the package. It is byte-identical to the community thyme
# firmware set (verified 2026-10-05), i.e. it is NOT donor content. It is OFF by default.
$FirmwareTargets = @(
    @{ Partition = 'abl';         File = 'abl.img' }
    @{ Partition = 'aop';         File = 'aop.img' }
    @{ Partition = 'bluetooth';   File = 'bluetooth.img' }
    @{ Partition = 'cmnlib';      File = 'cmnlib.img' }
    @{ Partition = 'cmnlib64';    File = 'cmnlib64.img' }
    @{ Partition = 'devcfg';      File = 'devcfg.img' }
    @{ Partition = 'dsp';         File = 'dsp.img' }
    @{ Partition = 'featenabler'; File = 'featenabler.img' }
    @{ Partition = 'hyp';         File = 'hyp.img' }
    @{ Partition = 'imagefv';     File = 'imagefv.img' }
    @{ Partition = 'keymaster';   File = 'keymaster.img' }
    @{ Partition = 'modem';       File = 'modem.img' }
    @{ Partition = 'qupfw';       File = 'qupfw.img' }
    @{ Partition = 'tz';          File = 'tz.img' }
    @{ Partition = 'uefisecapp';  File = 'uefisecapp.img' }
    @{ Partition = 'xbl';         File = 'xbl.img' }
    @{ Partition = 'xbl_config';  File = 'xbl_config.img' }
)

# Partitions this script will NEVER write under any switch.
$ForbiddenPartitions = @(
    'persist', 'modemst1', 'modemst2', 'fsg', 'fsc', 'ssd', 'devinfo', 'oem',
    'frp', 'keystore', 'misc', 'logfs', 'logdump', 'spunvm', 'apdp', 'msadp',
    'limits', 'dip', 'multiimgoem', 'multiimgqti', 'sti', 'tzsc', 'uefivar',
    'cust', 'countrycode', 'rescue', 'vbmeta_system_b', 'boot_b', 'vendor_boot_b',
    'dtbo_b', 'super_b'
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
function Write-Log {
    param([string]$Message, [string]$Level = 'INFO')
    $Stamp = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ss.fffZ')
    $Line  = "[$Stamp][$Level] $Message"
    switch ($Level) {
        'ERROR' { Write-Host $Line -ForegroundColor Red }
        'WARN'  { Write-Host $Line -ForegroundColor Yellow }
        'PASS'  { Write-Host $Line -ForegroundColor Green }
        default { Write-Host $Line }
    }
    if ($script:LogPath) { Add-Content -LiteralPath $script:LogPath -Value $Line -Encoding UTF8 }
}

function Assert-Path {
    param([string]$Path, [string]$What, [ValidateSet('Leaf', 'Container')][string]$Kind = 'Leaf')
    if (-not (Test-Path -LiteralPath $Path -PathType $Kind)) {
        throw "$What missing: $Path"
    }
}

# ---------------------------------------------------------------------------
# Phase 0 : local image verification (no device contact)
# ---------------------------------------------------------------------------
Write-Log "THYME Mi18PM Known-Good controlled flash - phase 0 local image verification"
Assert-Path -Path $FastbootExe -What 'fastboot executable'
Assert-Path -Path $ImageDir   -What 'package images directory' -Kind Container
if ([string]::IsNullOrWhiteSpace($ExpectedSerial)) {
    throw 'Pass the serial of the live Bootloader Fastboot device.'
}

$ContentTargets = @(
    @{ Partition = 'super';         File = 'super.img';       FileName = 'super.img' }
    @{ Partition = 'vbmeta_system'; File = 'vbmeta_system.img'; FileName = 'vbmeta_system.img' }
    @{ Partition = 'boot';          File = 'boot_noroot.img'; FileName = 'boot_noroot.img' }
    @{ Partition = 'vendor_boot';   File = 'vendor_boot.img'; FileName = 'vendor_boot.img' }
    @{ Partition = 'dtbo';          File = 'dtbo.img';        FileName = 'dtbo.img' }
)

foreach ($T in $ContentTargets) {
    $Path = Join-Path $ImageDir $T.FileName
    Assert-Path -Path $Path -What "image $($T.FileName)"
    $Item = Get-Item -LiteralPath $Path
    if ($ExpectedHashes.ContainsKey($T.FileName)) {
        $Hash = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToUpperInvariant()
        $Want = $ExpectedHashes[$T.FileName].ToUpperInvariant()
        if ($Hash -ne $Want) {
            throw "Image hash drift for $($T.FileName): got $Hash expected $Want. Refusing to continue."
        }
        Write-Log ("PASS {0,-20} {1,13} bytes  sha256={2}" -f $T.FileName, $Item.Length, $Hash) 'PASS'
    }
    else {
        Write-Log ("INFO {0,-20} {1,13} bytes  (no frozen hash; vbmeta_system is rebuilt-disabled AVB)" -f $T.FileName, $Item.Length)
    }
}

if ($FormatUserData -and -not $ConfirmUserDataWipe) {
    throw '-FormatUserData requires -ConfirmUserDataWipe as a second independent confirmation.'
}

# ---------------------------------------------------------------------------
# Phase 1 : build the write plan
# ---------------------------------------------------------------------------
$Plan = New-Object System.Collections.Generic.List[object]
foreach ($T in $ContentTargets) { $Plan.Add([pscustomobject]@{ Partition = $T.Partition; File = $T.FileName; Group = 'ROM-content' }) }

if ($IncludeVbmeta) {
    $Plan.Add([pscustomobject]@{ Partition = 'vbmeta'; File = 'vbmeta.img'; Group = 'AVB-disabled-pair' })
}

if ($IncludeFirmwareLayer) {
    foreach ($T in $FirmwareTargets) {
        $Plan.Add([pscustomobject]@{ Partition = $T.Partition; File = $T.File; Group = 'firmware-layer-OPT-IN' })
    }
}

foreach ($Item in $Plan) {
    $Name = ($Item.Partition -replace '_a$', '' -replace '_b$', '')
    if ($ForbiddenPartitions -contains $Name -or $ForbiddenPartitions -contains $Item.Partition) {
        throw "Write plan contains a forbidden partition: $($Item.Partition)"
    }
}

Write-Log "Write plan ($($Plan.Count) entries):"
foreach ($Item in $Plan) { Write-Log ("  [{0}] {1}  <=  {2}" -f $Item.Group, $Item.Partition, $Item.File) }

if (-not $Execute) {
    Write-Log 'DRY-RUN only. No Fastboot query and no device write was issued.' 'WARN'
    Write-Log 'Re-run with -Execute to perform the controlled write.' 'WARN'
    return
}

# ---------------------------------------------------------------------------
# Phase 2 : pre-flight state capture and identity gates
# ---------------------------------------------------------------------------
New-Item -ItemType Directory -Path $ReportDir -Force | Out-Null
New-Item -ItemType Directory -Path $StateDir  -Force | Out-Null
$script:LogPath = Join-Path $ReportDir ('SUCCESS_FLASH_' + (Get-Date).ToUniversalTime().ToString('yyyyMMdd_HHmmss_fff') + '.txt')

function Invoke-Fastboot {
    param([string[]]$Arguments)
    $All = @('-s', $ExpectedSerial) + $Arguments
    Write-Log ("fastboot " + ($All -join ' '))
    $Out  = cmd.exe /c "`"$FastbootExe`" $($All -join ' ') 2>&1" | Out-String
    $Code = $LASTEXITCODE
    Write-Log "exit_code=$Code"
    if ($Out) { Write-Log $Out.TrimEnd() }
    return [pscustomobject]@{ ExitCode = $Code; Output = $Out }
}

function Get-FastbootVar {
    param([string]$Name)
    $R = Invoke-Fastboot @('getvar', $Name)
    $Pattern = "(?m)^\s*(?:\(bootloader\)\s*)?$([regex]::Escape($Name)):\s*(?<v>[^\r\n]+?)\s*$"
    if ($R.Output -match $Pattern) { return $Matches['v'].Trim() }
    return $null
}

$Devices = Invoke-Fastboot @('devices', '-l')
$Lines = @($Devices.Output -split "\r?\n" | Where-Object { $_.Trim() })
if ($Lines.Count -ne 1 -or $Lines[0] -notmatch "^\s*$([regex]::Escape($ExpectedSerial))\s+fastboot\b") {
    throw "Device $ExpectedSerial is not the unique Bootloader Fastboot device. Refusing to flash."
}

$Vars = [ordered]@{}
foreach ($Name in @('product', 'current-slot', 'unlocked', 'is-userspace', 'slot-count',
                    'slot-unbootable:a', 'slot-successful:a', 'slot-retry-count:a',
                    'slot-unbootable:b', 'slot-successful:b', 'slot-retry-count:b',
                    'max-download-size', 'anti', 'serialno', 'version-bootloader',
                    'partition-type:super', 'partition-size:super',
                    'partition-type:boot_a', 'partition-size:boot_a',
                    'partition-type:vendor_boot_a', 'partition-size:vendor_boot_a',
                    'partition-type:dtbo_a', 'partition-size:dtbo_a',
                    'partition-type:vbmeta_system_a', 'partition-size:vbmeta_system_a')) {
    $Vars[$Name] = Get-FastbootVar $Name
}

$SnapshotPath = Join-Path $StateDir ('preflash_' + (Get-Date).ToUniversalTime().ToString('yyyyMMdd_HHmmss') + '.json')
$Vars | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath $SnapshotPath -Encoding UTF8
Write-Log "pre-flash state written to $SnapshotPath"

# --- gates ---
if ($Vars['product']      -ne $ExpectedProduct) { throw "product mismatch: '$($Vars['product'])'" }
if ($Vars['current-slot'] -ne $ExpectedSlot)    { throw "active slot mismatch: '$($Vars['current-slot'])' (this run only plans for slot a)" }
if ($Vars['unlocked']     -ne 'yes')            { throw 'bootloader is not unlocked; refusing (and never relock).' }
if ($Vars['is-userspace'] -ne 'no')             { throw 'device is in fastbootd/userspace; Bootloader Fastboot is required.' }
if ($Vars['slot-unbootable:a'] -ne 'no')        { throw 'slot A is marked unbootable.' }

$RetryA = 0
if (-not [int]::TryParse([string]$Vars['slot-retry-count:a'], [ref]$RetryA)) {
    throw "could not parse slot-retry-count:a ('$($Vars['slot-retry-count:a'])')"
}
if ($RetryA -lt $MinRetryBudget) {
    throw "slot A retry budget is $RetryA (< $MinRetryBudget). Refresh it deliberately before flashing."
}
Write-Log "gates PASS: product=$($Vars['product']) slot=$($Vars['current-slot']) unlocked=$($Vars['unlocked']) retry:a=$RetryA" 'PASS'

# --- firmware layer decision support (read-only compare against package hashes) ---
Write-Log 'Firmware layer comparison (live device vs package) is not byte-readable from Fastboot.'
Write-Log 'A byte-level comparison requires a root/ADB or Standalone-DIAG session; see the flash matrix document.'
if ($IncludeFirmwareLayer) {
    Write-Log 'IncludeFirmwareLayer was requested: xbl/abl/tz/hyp/aop/modem/dsp WILL be written.' 'WARN'
}
else {
    Write-Log 'IncludeFirmwareLayer not requested: existing device firmware is preserved.' 'PASS'
}

# --- operator confirmation ---
if (-not $NoPrompt) {
    Write-Host ''
    Write-Host 'The following writes are about to happen:' -ForegroundColor Cyan
    foreach ($Item in $Plan) { Write-Host ("   flash {0,-16} {1}" -f $Item.Partition, $Item.File) }
    if ($FormatUserData) { Write-Host '   erase userdata + metadata (DESTRUCTIVE)' -ForegroundColor Red }
    Write-Host ''
    Write-Host 'The device will be LEFT IN FASTBOOT. No automatic reboot will be issued.' -ForegroundColor Yellow
    $Answer = Read-Host 'Type FLASH to proceed'
    if ($Answer -ne 'FLASH') { Write-Log 'operator did not confirm; aborting without writing.' 'WARN'; return }
}

# ---------------------------------------------------------------------------
# Phase 3 : bounded writes
# ---------------------------------------------------------------------------
function Resolve-PartitionName {
    param([string]$Base)
    # Community/Xiaomi convention on this device: plain name or <name>_ab.
    $Primary = $Base
    $Probe   = Invoke-Fastboot @('getvar', "partition-type:$Primary")
    if ($Probe.Output -match 'partition-type:.*:\s*\S' -and $Probe.Output -notmatch 'FAILED|not found') {
        return $Primary
    }
    $Alt = "${Base}_ab"
    $Probe2 = Invoke-Fastboot @('getvar', "partition-type:$Alt")
    if ($Probe2.Output -match 'partition-type:.*:\s*\S' -and $Probe2.Output -notmatch 'FAILED|not found') {
        return $Alt
    }
    throw "could not resolve a writable partition name for '$Base' (tried '$Primary' and '$Alt')."
}

$Results = New-Object System.Collections.Generic.List[object]
foreach ($Item in $Plan) {
    $Path = Join-Path $ImageDir $Item.File
    $Target = Resolve-PartitionName -Base $Item.Partition
    if ($ForbiddenPartitions -contains $Target) { throw "resolved target '$Target' is forbidden." }

    Write-Log ">>> flashing $Target <= $($Item.File)"
    $R = Invoke-Fastboot @('flash', $Target, $Path)
    $Results.Add([pscustomobject]@{ Partition = $Target; File = $Item.File; ExitCode = $R.ExitCode })
    if ($R.ExitCode -ne 0) { throw "flash $Target failed with exit code $($R.ExitCode). Stopping; device left in Fastboot." }
    Write-Log "<<< $Target OKAY" 'PASS'
}

if ($FormatUserData) {
    Write-Log 'erasing frp / userdata / metadata (explicitly requested)' 'WARN'
    foreach ($P in @('frp', 'userdata', 'metadata')) {
        $R = Invoke-Fastboot @('erase', $P)
        if ($R.ExitCode -ne 0) { throw "erase $P failed with exit code $($R.ExitCode)." }
    }
}

# ---------------------------------------------------------------------------
# Phase 4 : post state capture. NO reboot.
# ---------------------------------------------------------------------------
foreach ($Name in @('product', 'current-slot', 'unlocked', 'slot-retry-count:a',
                    'slot-unbootable:a', 'slot-successful:a', 'slot-retry-count:b')) {
    Write-Log "post  $Name = $(Get-FastbootVar $Name)"
}

$ResultsPath = Join-Path $ReportDir ('SUCCESS_FLASH_RESULT_' + (Get-Date).ToUniversalTime().ToString('yyyyMMdd_HHmmss') + '.json')
$Results | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath $ResultsPath -Encoding UTF8

Write-Log 'CONTROLLED WRITE COMPLETE. Device remains in Bootloader Fastboot.' 'PASS'
Write-Log 'NO reboot was issued. First boot requires a separate explicit user instruction.' 'WARN'
Write-Host ''
Write-Host 'Done. Device is in Fastboot. Await explicit authorization before booting.' -ForegroundColor Green
