[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$RunDir,
    [switch]$Execute,
    [switch]$UserWatchingConfirmed,
    [Parameter(Mandatory=$true)][string]$Serial
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$FastbootExe = Join-Path $Root 'tools\platform-tools\fastboot.exe'
$ObservationRoot = Join-Path $Root 'work\reports\20260927_CANDIDATE23_SF_PRIME_SKIP\observations'
if ([string]::IsNullOrWhiteSpace($Serial)) { throw 'Pass the verified target serial explicitly with -Serial.' }
$ResolvedRunDir = (Resolve-Path -LiteralPath $RunDir).Path
if (-not (Test-Path -LiteralPath $ObservationRoot -PathType Container)) { throw "C23 observation directory missing: $ObservationRoot" }
$ResolvedObservationRoot = (Resolve-Path -LiteralPath $ObservationRoot).Path
$ObservationPrefix = $ResolvedObservationRoot.TrimEnd([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
if (-not $ResolvedRunDir.StartsWith($ObservationPrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'RunDir must be inside the C23 observation directory.'
}
$ArmedPath = Join-Path $ResolvedRunDir 'observer_armed.json'
if (-not (Test-Path -LiteralPath $ArmedPath -PathType Leaf)) { throw "Observer has not created observer_armed.json: $ArmedPath" }
$Armed = Get-Content -LiteralPath $ArmedPath -Raw | ConvertFrom-Json
if ($Armed.candidate -ne 'C23-sf-prime-skip' -or $Armed.serial -ne $Serial -or
    $Armed.usb_pnp_state -ne 'present' -or $Armed.adb_state -ne 'absent' -or
    $Armed.fastboot_state -ne 'fastboot') {
    throw 'Observer ARMED record does not match C23 and the expected Fastboot device.'
}
$ArmedTime = [DateTimeOffset]::Parse($Armed.armed_utc).ToUniversalTime()
if (([DateTimeOffset]::UtcNow - $ArmedTime).TotalMinutes -gt 10 -or $ArmedTime -gt [DateTimeOffset]::UtcNow.AddMinutes(1)) {
    throw 'Observer ARMED record is stale or has an invalid future timestamp.'
}

function Get-FastbootVar([string]$Name) {
    $output = & $FastbootExe -s $Serial getvar $Name 2>&1 | Out-String
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) { throw "fastboot getvar $Name failed ($exitCode): $output" }
    $pattern = "(?m)^\s*(?:\(bootloader\)\s*)?$([regex]::Escape($Name)):\s*(?<value>[^\r\n]+?)\s*$"
    if ($output -match $pattern) { return $Matches['value'].Trim() }
    throw "Could not read Fastboot variable '$Name'. Output: $output"
}

$Devices = & $FastbootExe devices -l 2>&1 | Out-String
if ($LASTEXITCODE -ne 0 -or $Devices -notmatch "(?m)^\s*$([regex]::Escape($Serial))\s+fastboot\b") {
    throw "Expected Fastboot target $Serial is not connected: $Devices"
}
$Product = Get-FastbootVar 'product'
$Slot = Get-FastbootVar 'current-slot'
$Unlocked = Get-FastbootVar 'unlocked'
$Userspace = Get-FastbootVar 'is-userspace'
$SlotUnbootable = Get-FastbootVar 'slot-unbootable:a'
$SlotSuccessful = Get-FastbootVar 'slot-successful:a'
$SlotRetryCount = Get-FastbootVar 'slot-retry-count:a'
if ($Product -ne 'thyme' -or $Slot -ne 'a' -or $Unlocked -ne 'yes' -or $Userspace -ne 'no') {
    throw "Target preflight mismatch: product=$Product slot=$Slot unlocked=$Unlocked is-userspace=$Userspace."
}
if ($SlotUnbootable -ne 'no' -or [int]$SlotRetryCount -le 0) {
    throw "A-slot is not eligible for another boot attempt: unbootable=$SlotUnbootable successful=$SlotSuccessful retry=$SlotRetryCount. No reboot issued."
}

$PrebootUtc = [DateTimeOffset]::UtcNow.ToString('o')
$PrebootLocal = [DateTimeOffset]::Now.ToString('o')
$PrebootPath = Join-Path $ResolvedRunDir 'fastboot_preboot_state.txt'
$PrebootLines = @(
    'C23 preboot Fastboot state; read-only queries only',
    "host_local=$PrebootLocal", "host_utc=$PrebootUtc",
    'candidate=C23-sf-prime-skip', "serial=$Serial", "product=$Product",
    "current_slot=$Slot", "unlocked=$Unlocked", "is_userspace=$Userspace",
    "slot_unbootable_a=$SlotUnbootable", "slot_successful_a=$SlotSuccessful",
    "slot_retry_count_a=$SlotRetryCount"
)
[IO.File]::WriteAllLines($PrebootPath, $PrebootLines, [Text.UTF8Encoding]::new($false))

$EventsPath = Join-Path $ResolvedRunDir 'host_events.jsonl'
$Event = [ordered]@{
    host_utc = $PrebootUtc; event = 'fastboot_preboot_state'; candidate = 'C23-sf-prime-skip'
    serial = $Serial; current_slot = $Slot; slot_unbootable_a = $SlotUnbootable
    slot_successful_a = $SlotSuccessful; slot_retry_count_a = [int]$SlotRetryCount
}
[IO.File]::AppendAllText($EventsPath, (($Event | ConvertTo-Json -Compress) + "`n"), [Text.UTF8Encoding]::new($false))

Write-Host "PASS observer ARMED for C23-sf-prime-skip at $($Armed.armed_utc)"
Write-Host "PASS device $Serial product=$Product slot=$Slot unlocked=$Unlocked is-userspace=$Userspace; A unbootable=$SlotUnbootable successful=$SlotSuccessful retry=$SlotRetryCount"
Write-Host "PASS preboot state saved: $PrebootPath"
if (-not $Execute) {
    Write-Host 'DRY-RUN complete. No reboot issued. User must separately confirm they are watching before C23 first boot.' -ForegroundColor Yellow
    return
}
if (-not $UserWatchingConfirmed) { throw 'The user must explicitly confirm they are watching before the C23 first boot.' }
$BootEvent = [ordered]@{ host_utc = [DateTimeOffset]::UtcNow.ToString('o'); event = 'candidate_boot_command'; candidate = 'C23-sf-prime-skip'; command = 'fastboot reboot'; serial = $Serial }
[IO.File]::AppendAllText($EventsPath, (($BootEvent | ConvertTo-Json -Compress) + "`n"), [Text.UTF8Encoding]::new($false))
& $FastbootExe -s $Serial reboot
$ExitCode = $LASTEXITCODE
$ReturnEvent = [ordered]@{ host_utc = [DateTimeOffset]::UtcNow.ToString('o'); event = 'candidate_boot_command_returned'; candidate = 'C23-sf-prime-skip'; exit_code = $ExitCode }
[IO.File]::AppendAllText($EventsPath, (($ReturnEvent | ConvertTo-Json -Compress) + "`n"), [Text.UTF8Encoding]::new($false))
if ($ExitCode -ne 0) { throw "fastboot reboot failed ($ExitCode); see $EventsPath" }
Write-Host 'C23 fastboot reboot command returned. Observer should continue running; do not reboot again.' -ForegroundColor Green
