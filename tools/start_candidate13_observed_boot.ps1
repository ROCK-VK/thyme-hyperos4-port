[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string]$RunDir,
    [switch]$Execute
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $PSScriptRoot
$FastbootExe = Join-Path $Root 'tools\platform-tools\fastboot.exe'
$ExpectedSerial = '[REDACTED_DEVICE_ID]'
$ExpectedProduct = 'thyme'
$ExpectedSlot = 'a'
$ObservationRoot = [IO.Path]::GetFullPath((Join-Path $Root 'work\reports\20260925_CANDIDATE13_STORAGE_SAFETY_AND_FIRST_FAILURE\observations'))
$RunPath = [IO.Path]::GetFullPath((Resolve-Path -LiteralPath $RunDir).Path)
$RootPrefix = $ObservationRoot.TrimEnd('\') + '\'
if (-not $RunPath.StartsWith($RootPrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Run directory must be inside $ObservationRoot"
}

$ArmedPath = Join-Path $RunPath 'observer_armed.json'
if (-not (Test-Path -LiteralPath $ArmedPath -PathType Leaf)) {
    throw 'Observer has not completed its first poll; start it and wait for [ARMED].'
}
$Armed = Get-Content -LiteralPath $ArmedPath -Raw | ConvertFrom-Json
if ($Armed.candidate -notmatch '^C17(?:[-_]|$)') {
    throw "Observer candidate label must identify C17; got '$($Armed.candidate)'."
}
if ($Armed.serial -ne $ExpectedSerial -or $Armed.usb_pnp_state -ne 'present' -or $Armed.fastboot_state -ne 'fastboot' -or $Armed.adb_state -ne 'absent') {
    throw "Observer armed for an unexpected state: serial=$($Armed.serial), USB=$($Armed.usb_pnp_state), adb=$($Armed.adb_state), fastboot=$($Armed.fastboot_state)."
}
$ArmedAt = [DateTimeOffset]::Parse($Armed.armed_utc).ToUniversalTime()
if (([DateTimeOffset]::UtcNow - $ArmedAt).TotalMinutes -gt 10 -or $ArmedAt -gt [DateTimeOffset]::UtcNow.AddMinutes(1)) {
    throw 'Observer arm record is older than 10 minutes or has a future timestamp; restart the observer.'
}
if (-not (Test-Path -LiteralPath $FastbootExe -PathType Leaf)) {
    throw "Local Fastboot executable missing: $FastbootExe"
}

function Get-FastbootVar([string]$Name) {
    $Output = & $FastbootExe -s $ExpectedSerial getvar $Name 2>&1 | Out-String
    $ExitCode = $LASTEXITCODE
    if ($ExitCode -ne 0) { throw "fastboot getvar $Name failed: $Output" }
    $Pattern = "(?m)^\s*(?:\(bootloader\)\s*)?$([regex]::Escape($Name)):\s*(?<value>[^\r\n]+?)\s*$"
    if ($Output -match $Pattern) { return $Matches['value'].Trim() }
    throw "Could not read Fastboot variable '$Name': $Output"
}

$Devices = & $FastbootExe devices -l 2>&1 | Out-String
if ($LASTEXITCODE -ne 0) {
    throw "Expected bootloader Fastboot device $ExpectedSerial is not connected: $Devices"
}
$ListedDevices = @([regex]::Matches($Devices, '(?m)^\s*(\S+)\s+fastboot\b') | ForEach-Object { $_.Groups[1].Value })
if ($ListedDevices.Count -ne 1 -or $ListedDevices[0] -ne $ExpectedSerial) {
    throw "Expected exactly one Fastboot device $ExpectedSerial; found: $($ListedDevices -join ', ')."
}
$Product = Get-FastbootVar 'product'
$Slot = Get-FastbootVar 'current-slot'
$Unlocked = Get-FastbootVar 'unlocked'
$IsUserspace = Get-FastbootVar 'is-userspace'
if ($Product -ne $ExpectedProduct) { throw "Product mismatch: expected $ExpectedProduct, got '$Product'." }
if ($Slot -ne $ExpectedSlot) { throw "Slot mismatch: expected $ExpectedSlot, got '$Slot'." }
if ($Unlocked -ne 'yes') { throw "Bootloader is not confirmed unlocked (unlocked='$Unlocked')." }
if ($IsUserspace -ne 'no') { throw "Target is not confirmed in bootloader Fastboot (is-userspace='$IsUserspace')." }

Write-Host "PASS serial=$ExpectedSerial product=$Product slot=$Slot unlocked=$Unlocked is-userspace=$IsUserspace"
Write-Host 'Planned command: fastboot -s [REDACTED_DEVICE_ID] reboot'
if (-not $Execute) {
    Write-Host 'DRY-RUN: no startup command issued. Use -Execute only after separate user startup authorization.' -ForegroundColor Yellow
    return
}

$Timeline = Join-Path $RunPath 'host_fastboot_commands.csv'
if (-not (Test-Path -LiteralPath $Timeline -PathType Leaf)) {
    'host_utc,event,command,exit_code,details' | Set-Content -LiteralPath $Timeline -Encoding utf8
}
$Now = [DateTimeOffset]::UtcNow.ToString('o')
$StartLine = '"{0}","command_start","fastboot -s {1} reboot","","product={2};slot={3};unlocked={4};is-userspace={5}"' -f $Now,$ExpectedSerial,$Product,$Slot,$Unlocked,$IsUserspace
Add-Content -LiteralPath $Timeline -Value $StartLine -Encoding utf8
Write-Host "[$Now] Issuing the one authorized Fastboot reboot. Keep watching the phone."
$Output = & $FastbootExe -s $ExpectedSerial reboot 2>&1 | Out-String
$ExitCode = $LASTEXITCODE
$End = [DateTimeOffset]::UtcNow.ToString('o')
$SafeOutput = $Output.Replace('"', '""').Replace("`r", ' ').Replace("`n", ' | ')
$EndLine = '"{0}","command_finished","fastboot -s {1} reboot",{2},"{3}"' -f $End,$ExpectedSerial,$ExitCode,$SafeOutput
Add-Content -LiteralPath $Timeline -Value $EndLine -Encoding utf8
Write-Host $Output
if ($ExitCode -ne 0) { throw "Fastboot reboot returned exit code $ExitCode; see $Timeline" }
Write-Host "Startup command completed at $End; passive observer remains responsible for ADB/Fastboot monitoring."
