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
$ObservationRoot = Join-Path $Root 'work\reports\20260926_CANDIDATE18_NATIVE_ADRENO\observations'
$ResolvedRunDir = (Resolve-Path -LiteralPath $RunDir).Path
$ResolvedObservationRoot = (Resolve-Path -LiteralPath $ObservationRoot -ErrorAction Stop).Path
$ObservationPrefix = $ResolvedObservationRoot.TrimEnd([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
if (-not $ResolvedRunDir.StartsWith($ObservationPrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'RunDir must be inside the C18 observation directory.'
}
$ArmedPath = Join-Path $ResolvedRunDir 'observer_armed.json'
if (-not (Test-Path -LiteralPath $ArmedPath -PathType Leaf)) { throw "Observer has not created observer_armed.json: $ArmedPath" }
$Armed = Get-Content -LiteralPath $ArmedPath -Raw | ConvertFrom-Json
if ($Armed.candidate -ne 'C18-native-adreno' -or $Armed.serial -ne $Serial -or
    $Armed.usb_pnp_state -ne 'present' -or $Armed.adb_state -ne 'absent' -or
    $Armed.fastboot_state -ne 'fastboot') {
    throw 'Observer ARMED record does not match C18-native-adreno and the expected Fastboot device.'
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
if ($Product -ne 'thyme' -or $Slot -ne 'a' -or $Unlocked -ne 'yes' -or $Userspace -ne 'no') {
    throw "Target preflight mismatch: product=$Product slot=$Slot unlocked=$Unlocked is-userspace=$Userspace."
}

Write-Host "PASS observer ARMED for C18-native-adreno at $($Armed.armed_utc)"
Write-Host "PASS device $Serial product=$Product slot=$Slot unlocked=$Unlocked is-userspace=$Userspace"
if (-not $Execute) {
    Write-Host 'DRY-RUN complete. No reboot issued. The user must confirm they are watching before -Execute.' -ForegroundColor Yellow
    return
}
if (-not $UserWatchingConfirmed) { throw 'The user must explicitly confirm they are watching before the C18 first boot.' }
$Event = [ordered]@{ host_utc = [DateTimeOffset]::UtcNow.ToString('o'); event = 'candidate_boot_command'; candidate = 'C18-native-adreno'; command = 'fastboot reboot'; serial = $Serial }
$EventsPath = Join-Path $ResolvedRunDir 'host_events.jsonl'
$EventJson = $Event | ConvertTo-Json -Compress
[IO.File]::AppendAllText($EventsPath, ($EventJson + "`n"), [Text.UTF8Encoding]::new($false))
& $FastbootExe -s $Serial reboot
$ExitCode = $LASTEXITCODE
$ReturnEvent = [ordered]@{ host_utc = [DateTimeOffset]::UtcNow.ToString('o'); event = 'candidate_boot_command_returned'; candidate = 'C18-native-adreno'; exit_code = $ExitCode }
$ReturnEventJson = $ReturnEvent | ConvertTo-Json -Compress
[IO.File]::AppendAllText($EventsPath, ($ReturnEventJson + "`n"), [Text.UTF8Encoding]::new($false))
if ($ExitCode -ne 0) { throw "fastboot reboot failed ($ExitCode); see $EventsPath" }
Write-Host 'C18 fastboot reboot command returned. Observer should continue running; do not reboot again.' -ForegroundColor Green
