[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Serial,
    [switch]$Execute
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
$Root = Split-Path -Parent $PSScriptRoot
$FastbootExe = Join-Path $Root 'tools\platform-tools\fastboot.exe'
$AdbExe = Join-Path $Root 'tools\platform-tools\adb.exe'

if ([string]::IsNullOrWhiteSpace($Serial)) { throw 'Pass the serial number.' }
if (-not (Test-Path -LiteralPath $FastbootExe -PathType Leaf)) { throw "Fastboot missing: $FastbootExe" }
if (-not (Test-Path -LiteralPath $AdbExe -PathType Leaf)) { throw "ADB missing: $AdbExe" }

function Get-FastbootVar([string]$Name) {
    $Output = cmd.exe /c "`"$FastbootExe`" -s $Serial getvar $Name 2>&1" | Out-String
    $Code = $LASTEXITCODE
    if ($Code -ne 0) { throw "fastboot getvar $Name failed ($Code): $Output" }
    $Pattern = "(?m)^\s*(?:\(bootloader\)\s*)?$([regex]::Escape($Name)):\s*(?<value>[^\r\n]+?)\s*$"
    if ($Output -match $Pattern) { return $Matches['value'].Trim() }
    throw "Could not parse Fastboot variable '$Name'. Output: $Output"
}

Write-Host "=== CANDIDATE 45 CONTROLLED FIRST BOOT ==="
Write-Host "Pre-boot preflight verification..."

$Devices = cmd.exe /c "`"$FastbootExe`" devices -l 2>&1" | Out-String
$DeviceLines = @($Devices -split "\r?\n" | Where-Object { $_.Trim() })
if ($DeviceLines.Count -ne 1 -or $DeviceLines[0] -notmatch "^\s*$([regex]::Escape($Serial))\s+fastboot\b") {
    throw "Device $Serial is not in Bootloader Fastboot mode. Output: $Devices"
}

$Product = Get-FastbootVar 'product'
$Slot = Get-FastbootVar 'current-slot'
$Unlocked = Get-FastbootVar 'unlocked'
$Userspace = Get-FastbootVar 'is-userspace'
$SlotUnbootable = Get-FastbootVar 'slot-unbootable:a'
$SlotRetry = Get-FastbootVar 'slot-retry-count:a'

Write-Host "Product: $Product"
Write-Host "Current Slot: $Slot"
Write-Host "Unlocked: $Unlocked"
Write-Host "Is Userspace: $Userspace"
Write-Host "Slot A Unbootable: $SlotUnbootable"
Write-Host "Slot A Retry: $SlotRetry"

if ($Product -ne 'thyme' -or $Slot -ne 'a' -or $Unlocked -ne 'yes' -or $Userspace -ne 'no' -or $SlotUnbootable -ne 'no' -or [int]$SlotRetry -le 0) {
    throw "Preflight verification failed! Refusing reboot."
}

if (-not $Execute) {
    Write-Host "`n[DRY-RUN] Preflight PASS. Re-run with -Execute to trigger official first boot." -ForegroundColor Yellow
    return
}

Write-Host "`n[REBOOT] Executing fastboot -s $Serial reboot..." -ForegroundColor Green
$RebootOutput = cmd.exe /c "`"$FastbootExe`" -s $Serial reboot 2>&1" | Out-String
$Code = $LASTEXITCODE
Write-Host $RebootOutput.TrimEnd()
if ($Code -ne 0) {
    throw "fastboot reboot failed ($Code): $RebootOutput"
}

$BootStartTime = [DateTime]::UtcNow
Write-Host "`n[BOOT LAUNCHED] Reboot issued at $BootStartTime. Entering observation window..." -ForegroundColor Cyan
Write-Host "Monitoring for ADB connection (timeout 120s)..."

$AdbFound = $false
$Deadline = (Get-Date).AddSeconds(120)
while ((Get-Date) -lt $Deadline) {
    Start-Sleep -Seconds 2
    $Elapsed = [int](([DateTime]::UtcNow) - $BootStartTime).TotalSeconds
    $AdbOut = cmd.exe /c "`"$AdbExe`" devices 2>&1" | Out-String
    if ($AdbOut -match "$([regex]::Escape($Serial))\s+(device|recovery)") {
        $AdbFound = $true
        Write-Host "`n>>> [ADB DETECTED] Device connected via ADB after ${Elapsed}s! State: $($Matches[1]) <<<" -ForegroundColor Green
        break
    }
    Write-Host -NoNewline "."
}

if ($AdbFound) {
    Write-Host "`n[LOGCAT] Capturing initial logcat..."
    $LogcatDir = Join-Path $Root 'reports\c45_candidate45_build_20261004\logcat'
    New-Item -ItemType Directory -Path $LogcatDir -Force | Out-Null
    $LogcatFile = Join-Path $LogcatDir 'c45_live_boot_logcat.txt'
    cmd.exe /c "`"$AdbExe`" -s $Serial logcat -d > `"$LogcatFile`" 2>&1"
    Write-Host "Logcat captured to $LogcatFile"
} else {
    Write-Host "`n[NOTE] ADB did not connect within 120s observation window." -ForegroundColor Yellow
    Write-Host "Please observe the physical screen and report:"
    Write-Host "  1. 第一屏: Mi Logo + powered by Android"
    Write-Host "  2. 第二屏: Xiaomi HyperOS + 三点动画 (或启动动画持续时间)"
    Write-Host "  3. 是否黑屏、白屏、常亮、振动或进入系统桌面/向导"
}
