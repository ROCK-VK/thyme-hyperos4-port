# Restore the proven madrid OS4.0.15 -> thyme Known-Good baseline.
#
# Dry-run is the default. The script contacts or writes to Fastboot only when
# -Execute is supplied. It never reboots the device.
#
# Protected partitions are never included in the write plan. -CleanData erases
# only userdata and metadata after all six image writes have succeeded.

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Serial,
    [string]$WorkspaceRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$ImageDirectory,
    [switch]$Execute,
    [switch]$CleanData
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
$script:LogPath = $null

$Root = (Resolve-Path -LiteralPath $WorkspaceRoot).Path
$FastbootExe = Join-Path $Root 'tools\platform-tools\fastboot.exe'
$ConstantsPath = Join-Path $PSScriptRoot 'controlled_thyme_success_flash.constants.json'
$ReportDir = Join-Path $Root 'reports\m02_adaptation_delta\restore_logs'
$Serial = $Serial.Trim()
$ExpectedProduct = 'thyme'

if ([string]::IsNullOrWhiteSpace($Serial)) { throw 'Pass the serial of the Fastboot device.' }
if (-not (Test-Path -LiteralPath $FastbootExe -PathType Leaf)) { throw "fastboot executable missing: $FastbootExe" }
if (-not (Test-Path -LiteralPath $ConstantsPath -PathType Leaf)) { throw "Known-Good constants missing: $ConstantsPath" }

$Constants = Get-Content -LiteralPath $ConstantsPath -Raw -Encoding UTF8 | ConvertFrom-Json
$ImageDir = if ([string]::IsNullOrWhiteSpace($ImageDirectory)) {
    Join-Path (Join-Path $Root $Constants.packageRootRelative) $Constants.imageDirRelative
} else {
    (Resolve-Path -LiteralPath $ImageDirectory).Path
}
if (-not (Test-Path -LiteralPath $ImageDir -PathType Container)) { throw "Known-Good image directory missing: $ImageDir" }

$ImagePlan = @(
    [pscustomobject]@{ Partition = 'boot_a';         File = 'boot_noroot.img' }
    [pscustomobject]@{ Partition = 'vendor_boot_a';  File = 'vendor_boot.img' }
    [pscustomobject]@{ Partition = 'dtbo_a';         File = 'dtbo.img' }
    [pscustomobject]@{ Partition = 'super';          File = 'super.img' }
    [pscustomobject]@{ Partition = 'vbmeta_a';       File = 'vbmeta.img' }
    [pscustomobject]@{ Partition = 'vbmeta_system_a';File = 'vbmeta_system.img' }
)

$Forbidden = @(
    'persist', 'modemst1', 'modemst2', 'fsg', 'fsc', 'efs', 'nv',
    'calibration', 'identity', 'frp', 'misc', 'bootloader', 'xbl', 'xbl_config',
    'abl', 'tz', 'hyp', 'aop', 'devcfg', 'keymaster', 'qupfw', 'uefisecapp',
    'imagefv', 'modem', 'dsp', 'bluetooth', 'cmnlib', 'cmnlib64',
    'boot_b', 'vendor_boot_b', 'dtbo_b', 'vbmeta_b', 'vbmeta_system_b', 'super_b'
)
foreach ($Target in $ImagePlan) {
    if ($Forbidden -contains $Target.Partition.ToLowerInvariant()) {
        throw "Forbidden partition appeared in the fixed restore plan: $($Target.Partition)"
    }
}

function Write-Log {
    param([string]$Message, [string]$Level = 'INFO')
    $Stamp = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ss.fffZ')
    $Line = "[$Stamp][$Level] $Message"
    Write-Host $Line
    if ($script:LogPath) { Add-Content -LiteralPath $script:LogPath -Value $Line -Encoding UTF8 }
}

function Invoke-Fastboot {
    param([string[]]$Arguments)
    $FastbootArgs = @('-s', $Serial) + $Arguments
    Write-Log ('fastboot ' + ($FastbootArgs -join ' '))
    $Output = & $FastbootExe @FastbootArgs 2>&1 | Out-String
    $Code = $LASTEXITCODE
    if ($Output.Trim()) { Write-Log $Output.TrimEnd() }
    Write-Log "exit_code=$Code"
    [pscustomobject]@{ ExitCode = $Code; Output = $Output }
}

function Get-FastbootVar {
    param([string]$Name)
    $Result = Invoke-Fastboot @('getvar', $Name)
    if ($Result.Output -match "(?m)^\s*(?:\(bootloader\)\s*)?$([regex]::Escape($Name)):\s*(?<v>[^\r\n]+?)\s*$") {
        return $Matches['v'].Trim()
    }
    return $null
}

function Convert-SizeToInt64 {
    param([string]$Value, [string]$Name)
    if ([string]::IsNullOrWhiteSpace($Value)) { throw "Fastboot did not report $Name." }
    $Text = $Value.Trim()
    if ($Text -match '^0[xX]([0-9a-fA-F]+)$') { return [Convert]::ToInt64($Matches[1], 16) }
    if ($Text -match '^\d+$') { return [int64]$Text }
    throw "Unrecognized Fastboot size for ${Name}: '$Value'."
}

Write-Log 'Known-Good madrid OS4.0.15 -> thyme restore: local image gate'
Write-Log "Known-Good package: $($Constants.packageRootName)"
foreach ($Target in $ImagePlan) {
    $Path = Join-Path $ImageDir $Target.File
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "Image missing: $Path" }
    $ExpectedHash = [string]$Constants.expectedHashes.($Target.File)
    $ExpectedSize = [int64]$Constants.expectedSizes.($Target.File)
    if ([string]::IsNullOrWhiteSpace($ExpectedHash) -or $ExpectedSize -le 0) {
        throw "No frozen hash/size exists for $($Target.File)."
    }
    $Item = Get-Item -LiteralPath $Path
    if ([int64]$Item.Length -ne $ExpectedSize) {
        throw "Size mismatch for $($Target.File): got $($Item.Length), expected $ExpectedSize."
    }
    $ActualHash = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToUpperInvariant()
    if ($ActualHash -ne $ExpectedHash.ToUpperInvariant()) {
        throw "SHA256 mismatch for $($Target.File): got $ActualHash, expected $ExpectedHash."
    }
    Write-Log ("PASS {0,-18} {1,13} bytes  sha256={2}" -f $Target.File, $Item.Length, $ActualHash) 'PASS'
}

Write-Log 'Fixed write plan:'
foreach ($Target in $ImagePlan) { Write-Log "  flash $($Target.Partition) <= $($Target.File)" }
if ($CleanData) {
    Write-Log 'Optional data plan: erase userdata; erase metadata (only these two partitions).' 'WARN'
}
Write-Log 'Never touched by this script: FRP, firmware, protected identity/calibration partitions, and slot B.'
Write-Log 'No reboot command exists in this script; completion leaves the device in Bootloader Fastboot.'

if (-not $Execute) {
    Write-Log 'DRY-RUN complete. No Fastboot command or device write was issued.' 'PASS'
    return
}

New-Item -ItemType Directory -Path $ReportDir -Force | Out-Null
$script:LogPath = Join-Path $ReportDir ('RESTORE_KNOWN_GOOD_' + (Get-Date).ToUniversalTime().ToString('yyyyMMdd_HHmmss_fff') + '.log')
Write-Log 'Execute mode: capture Fastboot state and enforce device gates.'

$Devices = Invoke-Fastboot @('devices', '-l')
$DeviceLines = @($Devices.Output -split "\r?\n" | Where-Object { $_.Trim() })
if ($Devices.ExitCode -ne 0 -or $DeviceLines.Count -ne 1 -or $DeviceLines[0] -notmatch "^\s*$([regex]::Escape($Serial))\s+fastboot\b") {
    throw "Expected exactly one Bootloader Fastboot device with serial $Serial."
}

$State = [ordered]@{}
foreach ($Name in @(
    'product', 'current-slot', 'slot-count', 'unlocked', 'is-userspace',
    'slot-unbootable:a', 'slot-successful:a', 'slot-retry-count:a',
    'slot-unbootable:b', 'slot-successful:b', 'slot-retry-count:b'
)) { $State[$Name] = Get-FastbootVar $Name }

if ($State['product'] -ne $ExpectedProduct) { throw "product gate failed: '$($State['product'])'." }
if ($State['unlocked'] -ne 'yes') { throw 'bootloader is not unlocked; refusing to flash.' }
if ($State['is-userspace'] -ne 'no') { throw 'Device is in fastbootd; Bootloader Fastboot is required.' }
if (@('a', 'b') -notcontains $State['current-slot']) { throw "Unrecognized current-slot: '$($State['current-slot'])'." }
Write-Log ("PASS device gates: product={0} current-slot={1} unlocked={2} is-userspace={3}" -f $State['product'], $State['current-slot'], $State['unlocked'], $State['is-userspace']) 'PASS'

# Require every fixed A/shared target to exist and hold the image before writing.
$PartitionCapacities = [ordered]@{}
foreach ($Target in $ImagePlan) {
    $VarName = "partition-size:$($Target.Partition)"
    $CapacityText = Get-FastbootVar $VarName
    $Capacity = Convert-SizeToInt64 -Value $CapacityText -Name $VarName
    $ImageSize = [int64](Get-Item -LiteralPath (Join-Path $ImageDir $Target.File)).Length
    if ($ImageSize -gt $Capacity) {
        throw "Partition-size gate failed for $($Target.Partition): image=$ImageSize capacity=$Capacity."
    }
    $PartitionCapacities[$Target.Partition] = $Capacity
    Write-Log ("PASS partition capacity {0}: image={1} capacity={2}" -f $Target.Partition, $ImageSize, $Capacity) 'PASS'
}

$StatePath = Join-Path $ReportDir ('pre_restore_' + (Get-Date).ToUniversalTime().ToString('yyyyMMdd_HHmmss_fff') + '.json')
[pscustomobject]@{ State = $State; PartitionCapacities = $PartitionCapacities } |
    ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $StatePath -Encoding UTF8
Write-Log "Fastboot pre-state saved: $StatePath"

$FlashResults = New-Object System.Collections.Generic.List[object]
foreach ($Target in $ImagePlan) {
    $Path = Join-Path $ImageDir $Target.File
    Write-Log ">>> flash $($Target.Partition) <= $($Target.File)"
    $Result = Invoke-Fastboot @('flash', $Target.Partition, $Path)
    $FlashResults.Add([pscustomobject]@{ Partition = $Target.Partition; File = $Target.File; ExitCode = $Result.ExitCode })
    if ($Result.ExitCode -ne 0) { throw "Flash failed for $($Target.Partition), exit=$($Result.ExitCode). Stopping in Fastboot." }
    Write-Log "PASS flash $($Target.Partition)" 'PASS'
}

if ($CleanData) {
    foreach ($Partition in @('userdata', 'metadata')) {
        Write-Log ">>> erase $Partition"
        $Result = Invoke-Fastboot @('erase', $Partition)
        if ($Result.ExitCode -ne 0) { throw "Erase failed for $Partition, exit=$($Result.ExitCode). Stopping in Fastboot." }
        Write-Log "PASS erase $Partition" 'PASS'
    }
}

Write-Log 'Activate the restored A baseline and refresh its retry budget.'
$Activate = Invoke-Fastboot @('set_active', 'a')
if ($Activate.ExitCode -ne 0) { throw "set_active a failed, exit=$($Activate.ExitCode). Device remains in Fastboot." }

$Post = [ordered]@{}
foreach ($Name in @('product', 'current-slot', 'unlocked', 'is-userspace', 'slot-unbootable:a', 'slot-successful:a', 'slot-retry-count:a')) {
    $Post[$Name] = Get-FastbootVar $Name
}
if ($Post['product'] -ne 'thyme' -or $Post['current-slot'] -ne 'a' -or $Post['is-userspace'] -ne 'no') {
    throw 'Post-write Fastboot state gate failed; inspect the recorded log before any boot.'
}
if ($Post['slot-unbootable:a'] -ne 'no') { throw "A baseline remains unbootable: '$($Post['slot-unbootable:a'])'." }
$RetryA = 0
if (-not [int]::TryParse([string]$Post['slot-retry-count:a'], [ref]$RetryA) -or $RetryA -lt 3) {
    throw "A retry budget was not restored to a safe minimum: '$($Post['slot-retry-count:a'])'."
}
$StillOnline = Invoke-Fastboot @('devices', '-l')
if ($StillOnline.ExitCode -ne 0 -or $StillOnline.Output -notmatch "(?m)^\s*$([regex]::Escape($Serial))\s+fastboot\b") {
    throw 'Post-write device presence gate failed; Fastboot device is no longer visible.'
}

$ResultPath = Join-Path $ReportDir ('restore_result_' + (Get-Date).ToUniversalTime().ToString('yyyyMMdd_HHmmss_fff') + '.json')
[pscustomobject]@{
    GeneratedUtc = (Get-Date).ToUniversalTime().ToString('o')
    Product = $Post['product']
    CurrentSlot = $Post['current-slot']
    Fastboot = $true
    CleanData = [bool]$CleanData
    Erased = $(if ($CleanData) { @('userdata', 'metadata') } else { @() })
    FlashResults = $FlashResults
    PostState = $Post
    RebootIssued = $false
} | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $ResultPath -Encoding UTF8

Write-Log "PASS restore completed; device remains in Bootloader Fastboot. Result: $ResultPath" 'PASS'
Write-Log 'No reboot was issued. Wait for the separate first-boot confirmation before starting Android.' 'WARN'
