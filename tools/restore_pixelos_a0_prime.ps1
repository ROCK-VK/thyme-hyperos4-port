# ==============================================================================
# THYME-OS4: PixelOS A0' Full Recovery Script
# Architecture: PixelOS A17 Baseline + Formal Dev VBMeta flags=3 (sys.boot_completed=1 verified)
# Safety Policy:
#   1. Read-Only verification by default unless -ExecuteFlash is explicitly passed.
#   2. Validates fastboot tool, device serial ([REDACTED_DEVICE_ID]), product (thyme), slot (a).
#   3. Pre-validates SHA-256 for all 6 recovery partitions before touching device.
#   4. Halts immediately on any failure ($LASTEXITCODE -ne 0).
#   5. Sensitive partitions (persist, modemst, fsg, fsc, devcfg, abl, xbl, tz) are NEVER touched.
#   6. Data wipe (userdata/metadata) is STRICTLY EXCLUDED and requires separate manual approval.
# ==============================================================================

[CmdletBinding()]
param(
    [switch]$ExecuteFlash,
    [switch]$SkipIdenticalDtbo
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$FastbootExe = "[LOCAL_PROJECT_ROOT]\tools\platform-tools\fastboot.exe"
if (-not (Test-Path $FastbootExe)) {
    $FastbootExe = "C:\Windows\System32\fastboot.exe"
}
$ExpectedSerial = "[REDACTED_DEVICE_ID]"
$ExpectedProduct = "thyme"

# Pure Windows Absolute Paths & Proven Checksums
$Images = [ordered]@{
    "boot_a" = @{
        Path = "[LOCAL_PROJECT_ROOT]\work\restore_pixelos_a0_prime\images\boot.img"
        ExpectedSha256 = "539EFE2107CF2EF21864DF6D74D4E645DC973F2D31CC23DC96E7E073A93B51AF"
        ExpectedBytes  = 201326592
        Description    = "PixelOS A0' Native Kernel + Ramdisk (AVB footer, verified boot completed)"
    }
    "vendor_boot_a" = @{
        Path = "[LOCAL_PROJECT_ROOT]\work\restore_pixelos_a0_prime\images\vendor_boot.img"
        ExpectedSha256 = "EBE05CCD7F6B8813A6EBC502A798DE56F1020B427AB4FC10FC0E8BA4ABC1B7FF"
        ExpectedBytes  = 100663296
        Description    = "PixelOS Original Vendor Boot"
    }
    "dtbo_a" = @{
        Path = "[LOCAL_PROJECT_ROOT]\work\restore_pixelos_a0_prime\images\dtbo.img"
        ExpectedSha256 = "50E1AC0EDCBD333778217AA6FE8D972F6FF85ADD0DAE8A015A6642C2172DD886"
        ExpectedBytes  = [REDACTED_DEVICE_ID]
        Description    = "PixelOS 12-entry DTBO (Entry 10 contains j2s panel match Fragment 58)"
    }
    "vbmeta_a" = @{
        Path = "[LOCAL_PROJECT_ROOT]\work\restore_pixelos_a0_prime\images\vbmeta.img"
        ExpectedSha256 = "FF44506A63F0797C0E15A415901810C7C40D3652779E446967530960A1B31650"
        ExpectedBytes  = 8192
        Description    = "PixelOS vbmeta_f3_formal (flags=3, verified boot completed)"
    }
    "vbmeta_system_a" = @{
        Path = "[LOCAL_PROJECT_ROOT]\work\restore_pixelos_a0_prime\images\vbmeta_system.img"
        ExpectedSha256 = "CD7EF53CDD4A4D2555C050F3341801223093516528F3E039C15DEC9A46446CD9"
        ExpectedBytes  = 4096
        Description    = "PixelOS Original VBMeta System"
    }
    "super" = @{
        Path = "[LOCAL_PROJECT_ROOT]\work\restore_pixelos_a0_prime\images\super.img"
        ExpectedSha256 = "260553A966CDE8E9E99A74D6AFED9481FA43073C88C09F3FD4EE07EC70218321"
        ExpectedBytes  = 6469630544
        Description    = "PixelOS Native Super Sparse (verified in TRY-ROUND-12 recovery)"
    }
}

function Write-Log([string]$msg, [string]$level = "INFO") {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$timestamp][$level] $msg"
}

function Get-FastbootVar([string]$varName) {
    $raw = cmd.exe /c "$FastbootExe getvar $varName 2>&1" | Out-String
    $pattern = "(?m)^\s*(?:\(bootloader\)\s*)?{0}:\s*(.*?)\s*$" -f [regex]::Escape($varName)
    if ($raw -match $pattern) {
        return $matches[1].Trim()
    }
    if ($raw -match "{0}:\s*([^\r\n]+?)(?:\s+Finished|\s*$)" -f [regex]::Escape($varName)) {
        return $matches[1].Trim()
    }
    return $null
}

Write-Log "=== THYME-OS4: PIXELOS A0' FULL RECOVERY PRE-FLIGHT VERIFICATION ==="

# 1. Fastboot tool check
if (!(Test-Path $FastbootExe)) {
    throw "Fastboot executable not found at: $FastbootExe"
}
$fbVersion = (& $FastbootExe --version 2>&1 | Select-Object -First 1)
Write-Log "Fastboot tool: $FastbootExe ($fbVersion)"

# 2. Host image integrity and SHA256 check
Write-Log "Verifying PixelOS recovery image files and SHA-256 checksums..."
foreach ($entry in $Images.GetEnumerator()) {
    $part = $entry.Key
    $meta = $entry.Value
    $imgPath = $meta.Path

    if (!(Test-Path $imgPath)) {
        throw "Image file missing for partition ${part}: $imgPath"
    }

    $item = Get-Item $imgPath
    if ($item.Length -ne $meta.ExpectedBytes) {
        throw "Byte size mismatch on ${part}: Actual $($item.Length) vs Expected $($meta.ExpectedBytes)"
    }

    $actualHash = (Get-FileHash -Path $imgPath -Algorithm SHA256).Hash.ToUpperInvariant()
    if ($actualHash -ne $meta.ExpectedSha256) {
        throw "SHA-256 MISMATCH on ${part}! Actual: $actualHash, Expected: $($meta.ExpectedSha256)"
    }

    Write-Log "[OK] ${part}: $($item.Length) bytes, SHA-256 matches $($meta.ExpectedSha256)"
}
Write-Log "All 6 recovery image files verified successfully on Windows NTFS filesystem."

# 3. Execution gate check
if (!$ExecuteFlash) {
    Write-Log "==========================================================================" "WARN"
    Write-Log "PRE-FLIGHT AUDIT PASSED. Recovery flash commands were NOT executed." "WARN"
    Write-Log "To execute recovery flashing on real device, you must explicitly pass: -ExecuteFlash" "WARN"
    Write-Log "Device writing, slot switching, rebooting, and data erasing remain BLOCKED." "WARN"
    Write-Log "==========================================================================" "WARN"
    return
}

# 4. Device state inspection (Only reached when -ExecuteFlash is explicitly passed)
Write-Log "Checking device state via Fastboot..."
$devList = cmd.exe /c "$FastbootExe devices 2>&1" | Out-String
if ($devList -notmatch "$ExpectedSerial\s+fastboot") {
    throw "Target device ($ExpectedSerial) is NOT detected in fastboot mode. Output:`n$devList"
}
Write-Log "Target device $ExpectedSerial detected in fastboot."

$prod = Get-FastbootVar "product"
if ($prod -ne $ExpectedProduct) {
    throw "Device product mismatch! Expected '$ExpectedProduct', but getvar product returned '$prod'."
}
Write-Log "Device product verified: $prod"

$unlocked = Get-FastbootVar "unlocked"
if ($unlocked -ne "yes") {
    throw "Device bootloader is locked! unlocked='$unlocked'."
}
Write-Log "Bootloader status: unlocked=$unlocked"

$slot = Get-FastbootVar "current-slot"
if ($slot -ne "a") {
    throw "ABORT: Current slot is '$slot', NOT 'a'! Script refuses to blindly execute set_active. Current slot must be manually confirmed."
}
Write-Log "Target slot verified: current-slot=a"

# 5. Flashing partitions with strict fail-fast policy
Write-Log "Starting recovery flashing sequence for PixelOS A0'..."

foreach ($entry in $Images.GetEnumerator()) {
    $part = $entry.Key
    $meta = $entry.Value
    $imgPath = $meta.Path

    if ($part -eq "dtbo_a" -and $SkipIdenticalDtbo) {
        Write-Log "SKIPPING $part : Hash is identical ($($meta.ExpectedSha256)), skipped as requested." "INFO"
        continue
    }

    Write-Log "Flashing $part from $imgPath ..."
    cmd.exe /c "$FastbootExe flash $part `"$imgPath`""
    $exitCode = $LASTEXITCODE

    if ($exitCode -ne 0) {
        throw "CRITICAL FAILURE: 'fastboot flash $part' failed with exit code $exitCode! Sequence terminated immediately."
    }
    Write-Log "[SUCCESS] Partition $part written successfully."
}

Write-Log "=== PixelOS A0' recovery flashing sequence COMPLETED successfully ==="
Write-Log "NOTE: No automatic wipe (userdata/metadata) was performed."
Write-Log "NOTE: No automatic reboot was performed. The device remains in fastboot mode."
