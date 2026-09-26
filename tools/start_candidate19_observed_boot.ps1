[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$RunDir,
    [switch]$Execute,
    [switch]$UserWatchingConfirmed,
    [string]$Serial = '[REDACTED_DEVICE_ID]'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$FastbootExe = Join-Path $Root 'tools\platform-tools\fastboot.exe'
$ObservationRoot = Join-Path $Root 'work\reports\20260927_CANDIDATE19_RGBX_EGL\observations'
$ResolvedRunDir = (Resolve-Path -LiteralPath $RunDir).Path
$ResolvedObservationRoot = (Resolve-Path -LiteralPath $ObservationRoot -ErrorAction Stop).Path
$ObservationPrefix = $ResolvedObservationRoot.TrimEnd([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
if (-not $ResolvedRunDir.StartsWith($ObservationPrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'RunDir must be inside the C19 observation directory.'
}
$ArmedPath = Join-Path $ResolvedRunDir 'observer_armed.json'
if (-not (Test-Path -LiteralPath $ArmedPath -PathType Leaf)) { throw "Observer has not created observer_armed.json: $ArmedPath" }
$Armed = Get-Content -LiteralPath $ArmedPath -Raw | ConvertFrom-Json
if ($Armed.candidate -ne 'C19-rgbx-format' -or $Armed.serial -ne $Serial -or
    $Armed.usb_pnp_state -ne 'present' -or $Armed.adb_state -ne 'absent' -or
    $Armed.fastboot_state -ne 'fastboot') {
    throw 'Observer ARMED record does not match C19-rgbx-format and the expected Fastboot device.'
}
$ArmedTime = [DateTimeOffset]::Parse($Armed.armed_utc).ToUniversalTime()
if (([DateTimeOffset]::UtcNow - $ArmedTime).TotalMinutes -gt 10 -or $ArmedTime -gt [DateTimeOffset]::UtcNow.AddMinutes(1)) {
    throw 'Observer ARMED record is stale or has an invalid future timestamp.'
}

$FastbootTranscript = [Collections.Generic.List[string]]::new()
function Get-FastbootVar([string]$Name) {
    $startedUtc = [DateTimeOffset]::UtcNow.ToString('o')
    $output = & $FastbootExe -s $Serial getvar $Name 2>&1 | Out-String
    $exitCode = $LASTEXITCODE
    $FastbootTranscript.Add("--- fastboot -s $Serial getvar $Name; started_utc=$startedUtc; exit=$exitCode ---")
    $FastbootTranscript.Add($output.TrimEnd())
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
if ($SlotUnbootable -ne 'no' -or $SlotSuccessful -ne 'no' -or $SlotRetryCount -ne '6') {
    throw "A-slot boot-control state differs from C19 prepared baseline: unbootable=$SlotUnbootable successful=$SlotSuccessful retry=$SlotRetryCount. No reboot issued."
}

$PrebootUtc = [DateTimeOffset]::UtcNow.ToString('o')
$PrebootLocal = [DateTimeOffset]::Now.ToString('o')
$PrebootPath = Join-Path $ResolvedRunDir 'fastboot_preboot_state.txt'
$PrebootLines = @(
    'C19 preboot Fastboot state; read-only queries only',
    "host_local=$PrebootLocal",
    "host_utc=$PrebootUtc",
    'candidate=C19-rgbx-format',
    "serial=$Serial",
    "product=$Product",
    "current_slot=$Slot",
    "unlocked=$Unlocked",
    "is_userspace=$Userspace",
    "slot_unbootable_a=$SlotUnbootable",
    "slot_successful_a=$SlotSuccessful",
    "slot_retry_count_a=$SlotRetryCount",
    '',
    '--- raw Fastboot query transcript ---'
) + $FastbootTranscript.ToArray()
[IO.File]::WriteAllLines($PrebootPath, $PrebootLines, [Text.UTF8Encoding]::new($false))

$EventsPath = Join-Path $ResolvedRunDir 'host_events.jsonl'
$BootControlEvent = [ordered]@{
    host_utc = $PrebootUtc
    event = 'fastboot_preboot_state'
    candidate = 'C19-rgbx-format'
    serial = $Serial
    current_slot = $Slot
    slot_unbootable_a = $SlotUnbootable
    slot_successful_a = $SlotSuccessful
    slot_retry_count_a = [int]$SlotRetryCount
    source_file = 'fastboot_preboot_state.txt'
}
[IO.File]::AppendAllText($EventsPath, (($BootControlEvent | ConvertTo-Json -Compress) + "`n"), [Text.UTF8Encoding]::new($false))

Write-Host "PASS observer ARMED for C19-rgbx-format at $($Armed.armed_utc)"
Write-Host "PASS device $Serial product=$Product slot=$Slot unlocked=$Unlocked is-userspace=$Userspace; A unbootable=$SlotUnbootable successful=$SlotSuccessful retry=$SlotRetryCount"
Write-Host "PASS raw preboot state saved: $PrebootPath"
if (-not $Execute) {
    Write-Host 'DRY-RUN complete. No reboot issued. The user must confirm they are watching before the C19 first boot.' -ForegroundColor Yellow
    return
}
if (-not $UserWatchingConfirmed) { throw 'The user must explicitly confirm they are watching before the C19 first boot.' }
$Event = [ordered]@{ host_utc = [DateTimeOffset]::UtcNow.ToString('o'); event = 'candidate_boot_command'; candidate = 'C19-rgbx-format'; command = 'fastboot reboot'; serial = $Serial }
[IO.File]::AppendAllText($EventsPath, (($Event | ConvertTo-Json -Compress) + "`n"), [Text.UTF8Encoding]::new($false))
& $FastbootExe -s $Serial reboot
$ExitCode = $LASTEXITCODE
$ReturnEvent = [ordered]@{ host_utc = [DateTimeOffset]::UtcNow.ToString('o'); event = 'candidate_boot_command_returned'; candidate = 'C19-rgbx-format'; exit_code = $ExitCode }
[IO.File]::AppendAllText($EventsPath, (($ReturnEvent | ConvertTo-Json -Compress) + "`n"), [Text.UTF8Encoding]::new($false))
if ($ExitCode -ne 0) { throw "fastboot reboot failed ($ExitCode); see $EventsPath" }
Write-Host 'C19 fastboot reboot command returned. Observer should continue running; do not reboot again.' -ForegroundColor Green
