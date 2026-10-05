# Stage MADRID-M02 candidate r3 in Bootloader Fastboot and stop before boot.
# Dry-run is the default. -Execute is used only after static acceptance gates pass.
# The only data partitions erased here are userdata and metadata, as required for
# the first OS4.0.19 base. This script contains no reboot command.

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Serial,
    [string]$WorkspaceRoot = (Split-Path -Parent $PSScriptRoot),
    [switch]$Execute
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
$script:LogPath = $null

$Root = (Resolve-Path -LiteralPath $WorkspaceRoot).Path
$FastbootExe = Join-Path $Root 'tools\platform-tools\fastboot.exe'
$Candidate = Join-Path $Root 'work\madrid_m02_candidate_r3'
$ImageDir = Join-Path $Candidate 'images'
$MetaDir = Join-Path $Candidate 'metadata'
$ReportDir = Join-Path $Root 'reports\m02_adaptation_delta\madrid_m02_staging'
$Serial = $Serial.Trim()

if ([string]::IsNullOrWhiteSpace($Serial)) { throw 'Pass the Fastboot serial.' }
if (-not (Test-Path -LiteralPath $FastbootExe -PathType Leaf)) { throw "fastboot executable missing: $FastbootExe" }
if (-not (Test-Path -LiteralPath $ImageDir -PathType Container)) { throw "Candidate image directory missing: $ImageDir" }

$FlashPlan = @(
    [pscustomobject]@{ Partition = 'boot_a';          File = 'boot_noroot.img';    SHA256 = 'b059e885daaa11f0032e05ff5b16c7ee6a13d84b8cdbd51033ac2b4999c3fa0f'; Bytes = 134217728L }
    [pscustomobject]@{ Partition = 'vendor_boot_a';   File = 'vendor_boot.img';    SHA256 = 'ed5391f9ad2be11a0636657968972d005600658c45ff631e5462ce9779840b07'; Bytes = 100663296L }
    [pscustomobject]@{ Partition = 'dtbo_a';          File = 'dtbo.img';           SHA256 = 'a0f550a32c15b95a6ba0bbe141976bad905d23fc74367e3e3ff0f41bc90c6d3a'; Bytes = 33554432L }
    [pscustomobject]@{ Partition = 'super';           File = 'super.img';          SHA256 = '51cf39c0d456c5bd2dd1e8fdf0d560d2a1deb647cf877c73678c6d259a73dfcd'; Bytes = 8063690032L }
    [pscustomobject]@{ Partition = 'vbmeta_a';        File = 'vbmeta.img';         SHA256 = 'd2e1979739ec67076a90b0fc625dae84a1aa2ed72d05d2b55d52539e3462b442'; Bytes = 4096L }
    [pscustomobject]@{ Partition = 'vbmeta_system_a'; File = 'vbmeta_system.img';  SHA256 = 'd2e1979739ec67076a90b0fc625dae84a1aa2ed72d05d2b55d52539e3462b442'; Bytes = 4096L }
)
$Forbidden = @(
    'persist', 'modemst1', 'modemst2', 'fsg', 'fsc', 'efs', 'nv',
    'calibration', 'identity', 'frp', 'misc', 'bootloader', 'xbl', 'xbl_config',
    'abl', 'tz', 'hyp', 'aop', 'devcfg', 'keymaster', 'qupfw', 'uefisecapp',
    'imagefv', 'modem', 'dsp', 'bluetooth', 'cmnlib', 'cmnlib64',
    'boot_b', 'vendor_boot_b', 'dtbo_b', 'vbmeta_b', 'vbmeta_system_b', 'super_b'
)
foreach ($Target in $FlashPlan) {
    if ($Forbidden -contains $Target.Partition.ToLowerInvariant()) { throw "Forbidden partition in fixed plan: $($Target.Partition)" }
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
    if ($Result.ExitCode -ne 0) { throw "fastboot getvar $Name failed with exit $($Result.ExitCode)." }
    if ($Result.Output -match "(?m)^\s*(?:\(bootloader\)\s*)?$([regex]::Escape($Name)):\s*(?<v>[^\r\n]+?)\s*$") {
        return $Matches['v'].Trim()
    }
    return $null
}

function Convert-SizeToInt64 {
    param([string]$Value, [string]$Name)
    if ([string]::IsNullOrWhiteSpace($Value)) { throw "Fastboot did not report $Name." }
    if ($Value -match '^0[xX]([0-9a-fA-F]+)$') { return [Convert]::ToInt64($Matches[1], 16) }
    if ($Value -match '^\d+$') { return [int64]$Value }
    throw "Unrecognized Fastboot size for ${Name}: '$Value'."
}

function Assert-CandidateStaticGates {
    $GatePath = Join-Path $MetaDir 'STATIC_GATE_REPORT.json'
    $InventoryPath = Join-Path $MetaDir 'inventory\IMAGE_INVENTORY.json'
    $SumsPath = Join-Path $MetaDir 'SHA256SUMS'
    foreach ($Path in @($GatePath, $InventoryPath, $SumsPath)) {
        if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "Required candidate evidence missing: $Path" }
    }
    $Gate = Get-Content -LiteralPath $GatePath -Raw -Encoding UTF8 | ConvertFrom-Json
    if (-not $Gate.passed -or $Gate.image_count -ne 12 -or $Gate.physical_super_bytes -ne 9126805504) {
        throw 'Candidate static-gate report is not a passing 12-image thyme-super report.'
    }
    if ($Gate.lp_headroom_bytes -lt 67108864 -or -not $Gate.lp_a_populated_b_empty) { throw 'Candidate LP size/slot gate failed.' }
    foreach ($Name in @('geometry', 'header', 'tables')) {
        if (-not $Gate.independent_lp_checksums.$Name) { throw "Independent LP $Name checksum gate failed." }
    }
    foreach ($Name in @('system_a', 'system_ext_a', 'product_a')) {
        if ($Gate.erofs_roundtrip.$Name -ne 0) { throw "EROFS round-trip gate failed for $Name." }
        $RoundtripPath = Join-Path $MetaDir "roundtrip_$Name.json"
        if (-not (Test-Path -LiteralPath $RoundtripPath -PathType Leaf)) { throw "Round-trip evidence missing: $RoundtripPath" }
        $Roundtrip = Get-Content -LiteralPath $RoundtripPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($Roundtrip.difference_count -ne 0 -or $Roundtrip.staged_entries -ne $Roundtrip.roundtrip_entries) { throw "Round-trip manifest gate failed for $Name." }
    }

    $Inventory = Get-Content -LiteralPath $InventoryPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($Inventory.file_count -ne 12 -or @($Inventory.images).Count -ne 12) { throw 'Candidate inventory does not contain exactly 12 images.' }
    $InventoryByName = @{}
    foreach ($Row in $Inventory.images) { $InventoryByName[[string]$Row.file] = $Row }
    $SumByName = @{}
    foreach ($Line in Get-Content -LiteralPath $SumsPath -Encoding UTF8) {
        if ($Line -match '^([0-9a-fA-F]{64})\s+\*?(.+?)\s*$') { $SumByName[[IO.Path]::GetFileName($Matches[2])] = $Matches[1].ToLowerInvariant() }
    }
    if ($InventoryByName.Count -ne 12 -or $SumByName.Count -ne 12) { throw 'Candidate inventory and SHA256 manifest sets are incomplete.' }
    foreach ($Name in $InventoryByName.Keys) {
        if (-not $SumByName.ContainsKey($Name) -or $SumByName[$Name] -ne ([string]$InventoryByName[$Name].sha256).ToLowerInvariant()) {
            throw "Inventory/SHA256 manifest mismatch for $Name."
        }
    }

    Write-Log 'PASS static gate report, inventory, checksums and round-trip reports.' 'PASS'
}

Write-Log 'MADRID-M02 r3 local image gate.'
Assert-CandidateStaticGates
foreach ($Target in $FlashPlan) {
    $Path = Join-Path $ImageDir $Target.File
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "Candidate image missing: $Path" }
    $Item = Get-Item -LiteralPath $Path
    if ([int64]$Item.Length -ne [int64]$Target.Bytes) { throw "Image byte-size mismatch for $($Target.File): $($Item.Length)." }
    $ActualHash = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($ActualHash -ne $Target.SHA256) { throw "Frozen candidate hash mismatch for $($Target.File): $ActualHash." }
    Write-Log ("PASS {0,-18} {1,13} bytes sha256={2}" -f $Target.File, $Item.Length, $ActualHash) 'PASS'
}
Write-Log 'Fixed deployment plan: flash A-slot boot/vbmeta targets and shared super; erase only userdata and metadata; set active slot A; then stop in Fastboot.'
Write-Log 'No firmware, B slot, FRP, persist, modemst, EFS/NV, calibration, identity or relock target exists in the fixed plan.'
if (-not $Execute) {
    Write-Log 'DRY-RUN complete. No Fastboot command or device write was issued.' 'PASS'
    return
}

New-Item -ItemType Directory -Path $ReportDir -Force | Out-Null
$script:LogPath = Join-Path $ReportDir ('MADRID_M02_STAGE_' + (Get-Date).ToUniversalTime().ToString('yyyyMMdd_HHmmss_fff') + '.log')
Write-Log 'Execute mode: require exactly one Bootloader Fastboot device and validate target state.'
$Devices = Invoke-Fastboot @('devices', '-l')
$DeviceLines = @($Devices.Output -split "\r?\n" | Where-Object { $_.Trim() })
if ($Devices.ExitCode -ne 0 -or $DeviceLines.Count -ne 1 -or $DeviceLines[0] -notmatch "^\s*$([regex]::Escape($Serial))\s+fastboot\b") {
    throw "Expected exactly one Bootloader Fastboot device with serial $Serial."
}

$State = [ordered]@{}
foreach ($Name in @('product', 'current-slot', 'unlocked', 'is-userspace', 'slot-unbootable:a', 'slot-successful:a', 'slot-retry-count:a')) {
    $State[$Name] = Get-FastbootVar $Name
}
if ($State['product'] -ne 'thyme') { throw "Product gate failed: '$($State['product'])'." }
if ($State['current-slot'] -ne 'a') { throw "Active slot gate failed: '$($State['current-slot'])'; this candidate is staged only to A." }
if ($State['unlocked'] -ne 'yes') { throw 'Bootloader is not unlocked.' }
if ($State['is-userspace'] -ne 'no') { throw 'Device is in fastbootd; Bootloader Fastboot is required.' }
if ($State['slot-unbootable:a'] -notin @('no', $null)) { throw "A slot is marked unbootable before staging: '$($State['slot-unbootable:a'])'." }
Write-Log ("PASS device gates: product={0} current-slot={1} unlocked={2} is-userspace={3}" -f $State['product'], $State['current-slot'], $State['unlocked'], $State['is-userspace']) 'PASS'

$PartitionCapacities = [ordered]@{}
foreach ($Target in $FlashPlan) {
    $VarName = "partition-size:$($Target.Partition)"
    $CapacityText = Get-FastbootVar $VarName
    $Capacity = Convert-SizeToInt64 -Value $CapacityText -Name $VarName
    if ([int64]$Target.Bytes -gt $Capacity) { throw "Partition-size gate failed for $($Target.Partition): image=$($Target.Bytes) capacity=$Capacity." }
    $PartitionCapacities[$Target.Partition] = $Capacity
    Write-Log ("PASS partition capacity {0}: image={1} capacity={2}" -f $Target.Partition, $Target.Bytes, $Capacity) 'PASS'
}

$PrePath = Join-Path $ReportDir ('pre_stage_' + (Get-Date).ToUniversalTime().ToString('yyyyMMdd_HHmmss_fff') + '.json')
[pscustomobject]@{ State = $State; PartitionCapacities = $PartitionCapacities } |
    ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $PrePath -Encoding UTF8
Write-Log "Fastboot pre-state saved: $PrePath"

$FlashResults = New-Object System.Collections.Generic.List[object]
foreach ($Target in $FlashPlan) {
    $Path = Join-Path $ImageDir $Target.File
    Write-Log ">>> flash $($Target.Partition) <= $($Target.File)"
    $Result = Invoke-Fastboot @('flash', $Target.Partition, $Path)
    $FlashResults.Add([pscustomobject]@{ Partition = $Target.Partition; File = $Target.File; ExitCode = $Result.ExitCode })
    if ($Result.ExitCode -ne 0) { throw "Flash failed for $($Target.Partition), exit=$($Result.ExitCode). Stop; device remains in Fastboot." }
    Write-Log "PASS flash $($Target.Partition)" 'PASS'
}

foreach ($Partition in @('userdata', 'metadata')) {
    Write-Log ">>> erase $Partition"
    $Result = Invoke-Fastboot @('erase', $Partition)
    if ($Result.ExitCode -ne 0) { throw "Erase failed for $Partition, exit=$($Result.ExitCode). Stop in Fastboot." }
    Write-Log "PASS erase $Partition" 'PASS'
}

Write-Log 'Set A active to establish the intended candidate slot and retry budget.'
$Activate = Invoke-Fastboot @('set_active', 'a')
if ($Activate.ExitCode -ne 0) { throw "set_active a failed, exit=$($Activate.ExitCode). Device remains in Fastboot." }

$Post = [ordered]@{}
foreach ($Name in @('product', 'current-slot', 'unlocked', 'is-userspace', 'slot-unbootable:a', 'slot-successful:a', 'slot-retry-count:a')) {
    $Post[$Name] = Get-FastbootVar $Name
}
if ($Post['product'] -ne 'thyme' -or $Post['current-slot'] -ne 'a' -or $Post['unlocked'] -ne 'yes' -or $Post['is-userspace'] -ne 'no') {
    throw 'Post-stage Fastboot state gate failed; inspect logs before proceeding.'
}
if ($Post['slot-unbootable:a'] -ne 'no') { throw "A slot remains unbootable: '$($Post['slot-unbootable:a'])'." }
$RetryA = 0
if (-not [int]::TryParse([string]$Post['slot-retry-count:a'], [ref]$RetryA) -or $RetryA -lt 3) {
    throw "A retry budget is below the staging minimum: '$($Post['slot-retry-count:a'])'."
}
$StillOnline = Invoke-Fastboot @('devices', '-l')
$OnlineLines = @($StillOnline.Output -split "\r?\n" | Where-Object { $_.Trim() })
if ($StillOnline.ExitCode -ne 0 -or $OnlineLines.Count -ne 1 -or $OnlineLines[0] -notmatch "^\s*$([regex]::Escape($Serial))\s+fastboot\b") {
    throw 'Post-stage Fastboot presence gate failed.'
}

$ResultPath = Join-Path $ReportDir ('stage_result_' + (Get-Date).ToUniversalTime().ToString('yyyyMMdd_HHmmss_fff') + '.json')
[pscustomobject]@{
    GeneratedUtc = (Get-Date).ToUniversalTime().ToString('o')
    Candidate = 'MADRID-M02-r3'
    Product = $Post['product']
    CurrentSlot = $Post['current-slot']
    Fastboot = $true
    Erased = @('userdata', 'metadata')
    FlashResults = $FlashResults
    PostState = $Post
    RebootIssued = $false
} | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $ResultPath -Encoding UTF8

Write-Log "PASS candidate staged; device remains in Bootloader Fastboot. Result: $ResultPath" 'PASS'
Write-Log 'No formal candidate boot was started. Wait for the single first-boot confirmation.' 'WARN'
