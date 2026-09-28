[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$RunDir,
    [Parameter(Mandatory=$true)][string]$Serial,
    [switch]$Execute,
    [switch]$UserWatchingConfirmed
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$FastbootExe = Join-Path $Root 'tools\platform-tools\fastboot.exe'
$ObservationRoot = Join-Path $Root 'work\reports\20260929_C26_ZYGOTE_FIRST_EXIT\observations'
$Candidate = 'C26-zygote-first-exit'

if ([string]::IsNullOrWhiteSpace($Serial)) { throw 'Pass the freshly verified Fastboot serial.' }
if (-not (Test-Path -LiteralPath $FastbootExe -PathType Leaf)) { throw "Local Fastboot missing: $FastbootExe" }
$ResolvedRunDir = (Resolve-Path -LiteralPath $RunDir).Path
$ResolvedObservationRoot = (Resolve-Path -LiteralPath $ObservationRoot).Path
$ObservationPrefix = $ResolvedObservationRoot.TrimEnd([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
if (-not $ResolvedRunDir.StartsWith($ObservationPrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'RunDir must be inside the C26 observation directory.'
}

$ArmedPath = Join-Path $ResolvedRunDir 'observer_armed.json'
if (-not (Test-Path -LiteralPath $ArmedPath -PathType Leaf)) { throw "Observer has not created observer_armed.json: $ArmedPath" }
$Armed = Get-Content -LiteralPath $ArmedPath -Raw | ConvertFrom-Json
if ($Armed.candidate -ne $Candidate -or $Armed.serial -ne $Serial -or
    $Armed.usb_pnp_state -ne 'present' -or $Armed.adb_state -ne 'absent' -or
    $Armed.fastboot_state -ne 'fastboot') {
    throw 'Observer ARMED record does not match C26 and the expected Fastboot device.'
}
$ArmedTime = [DateTimeOffset]::Parse($Armed.armed_utc).ToUniversalTime()
if (([DateTimeOffset]::UtcNow - $ArmedTime).TotalMinutes -gt 10 -or $ArmedTime -gt [DateTimeOffset]::UtcNow.AddMinutes(1)) {
    throw 'Observer ARMED record is stale or has an invalid future timestamp.'
}

function Get-FastbootVar([string]$Name) {
    $Output = & $FastbootExe -s $Serial getvar $Name 2>&1 | Out-String
    $ExitCode = $LASTEXITCODE
    if ($ExitCode -ne 0) { throw "fastboot getvar $Name failed ($ExitCode): $Output" }
    $Pattern = "(?m)^\s*(?:\(bootloader\)\s*)?$([regex]::Escape($Name)):\s*(?<value>[^\r\n]+?)\s*$"
    if ($Output -match $Pattern) { return $Matches['value'].Trim() }
    throw "Could not read Fastboot variable '$Name'. Output: $Output"
}

$Devices = & $FastbootExe devices -l 2>&1 | Out-String
$DeviceLines = @($Devices -split "\r?\n" | Where-Object { $_.Trim() })
if ($LASTEXITCODE -ne 0 -or $DeviceLines.Count -ne 1 -or $DeviceLines[0] -notmatch "^\s*$([regex]::Escape($Serial))\s+fastboot\b") {
    throw "Expected exactly one Bootloader Fastboot device $Serial. Output: $Devices"
}
$Product = Get-FastbootVar 'product'
$Slot = Get-FastbootVar 'current-slot'
$Unlocked = Get-FastbootVar 'unlocked'
$Userspace = Get-FastbootVar 'is-userspace'
$SlotUnbootable = Get-FastbootVar 'slot-unbootable:a'
$SlotSuccessful = Get-FastbootVar 'slot-successful:a'
$SlotRetryCount = Get-FastbootVar 'slot-retry-count:a'
if ($Product -ne 'thyme' -or $Slot -ne 'a' -or $Unlocked -ne 'yes' -or $Userspace -ne 'no' -or
    $SlotUnbootable -ne 'no' -or [int]$SlotRetryCount -le 0) {
    throw "Target preflight mismatch or A slot not bootable: product=$Product slot=$Slot unlocked=$Unlocked userspace=$Userspace unbootable=$SlotUnbootable successful=$SlotSuccessful retry=$SlotRetryCount. No reboot issued."
}

$PrebootUtc = [DateTimeOffset]::UtcNow.ToString('o')
$EventsPath = Join-Path $ResolvedRunDir 'host_events.jsonl'
$PrebootPath = Join-Path $ResolvedRunDir 'fastboot_preboot_state.txt'
$PrebootLines = @(
    'C26 preboot Fastboot state; read-only queries only',
    "host_utc=$PrebootUtc",
    "candidate=$Candidate",
    "serial=$Serial",
    "product=$Product",
    "current_slot=$Slot",
    "unlocked=$Unlocked",
    "is_userspace=$Userspace",
    "slot_unbootable_a=$SlotUnbootable",
    "slot_successful_a=$SlotSuccessful",
    "slot_retry_count_a=$SlotRetryCount"
)
[IO.File]::WriteAllLines($PrebootPath, $PrebootLines, [Text.UTF8Encoding]::new($false))
$PrebootEvent = [ordered]@{
    host_utc = $PrebootUtc; event = 'fastboot_preboot_state'; candidate = $Candidate
    current_slot = $Slot; slot_unbootable_a = $SlotUnbootable
    slot_successful_a = $SlotSuccessful; slot_retry_count_a = [int]$SlotRetryCount
}
[IO.File]::AppendAllText($EventsPath, (($PrebootEvent | ConvertTo-Json -Compress) + [Environment]::NewLine), [Text.UTF8Encoding]::new($false))

Write-Host "PASS observer ARMED for $Candidate at $($Armed.armed_utc)"
Write-Host "PASS product=$Product slot=$Slot unlocked=$Unlocked userspace=$Userspace; A unbootable=$SlotUnbootable successful=$SlotSuccessful retry=$SlotRetryCount"
Write-Host "PASS preboot state saved: $PrebootPath"
if (-not $Execute) {
    Write-Host 'DRY-RUN complete. No reboot issued. Wait for the user onsite confirmation before first boot.' -ForegroundColor Yellow
    return
}
if (-not $UserWatchingConfirmed) { throw 'The user must explicitly confirm they are watching before C26 first boot.' }
$BootUtc = [DateTimeOffset]::UtcNow.ToString('o')
$BootEvent = [ordered]@{ host_utc = $BootUtc; event = 'candidate_boot_command'; candidate = $Candidate; command = 'fastboot reboot'; serial = $Serial }
[IO.File]::AppendAllText($EventsPath, (($BootEvent | ConvertTo-Json -Compress) + [Environment]::NewLine), [Text.UTF8Encoding]::new($false))
& $FastbootExe -s $Serial reboot
$ExitCode = $LASTEXITCODE
$ReturnEvent = [ordered]@{ host_utc = [DateTimeOffset]::UtcNow.ToString('o'); event = 'candidate_boot_command_returned'; candidate = $Candidate; exit_code = $ExitCode }
[IO.File]::AppendAllText($EventsPath, (($ReturnEvent | ConvertTo-Json -Compress) + [Environment]::NewLine), [Text.UTF8Encoding]::new($false))
if ($ExitCode -ne 0) { throw "fastboot reboot failed ($ExitCode); see $EventsPath" }
Write-Host 'C26 fastboot reboot command returned. Keep the observer active; do not reboot again.' -ForegroundColor Green
