[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Serial,
    [switch]$Execute,
    [switch]$RestoreRetryBudget
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
$Root = Split-Path -Parent $PSScriptRoot
$FastbootExe = Join-Path $Root 'tools\platform-tools\fastboot.exe'
$ImageDir = Join-Path $Root 'work\stage_c44_capex_digest_fix_20261004\images'
$ManifestPath = Join-Path $ImageDir 'BUILD_MANIFEST.json'
$ExpectedProduct = 'thyme'
$ExpectedSlot = 'a'
$ExpectedSerial = $Serial.Trim()

if ([string]::IsNullOrWhiteSpace($ExpectedSerial)) { throw 'Pass the serial from the live Bootloader Fastboot device list.' }
if (-not (Test-Path -LiteralPath $FastbootExe -PathType Leaf)) { throw "Fastboot executable missing: $FastbootExe" }
if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) { throw "C44 manifest missing: $ManifestPath" }

$Manifest = Get-Content -LiteralPath $ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($Manifest.candidate -ne 'Candidate 44 Tethering CAPEX originalApexDigest Fix' -or
    $Manifest.base_candidate -ne 'Candidate 43 Netd eBPF Init Abort Surgical Bypass') {
    throw 'Manifest is not the expected C44 image set based on C43.'
}

if ($Manifest.single_variable_modification.actual_payload_root_digest -ne '4bdfe2f9158035e7d4dd5efe814f5d1dd9eee1d9052eb7c1f571125e9c67e042' -or
    $Manifest.single_variable_modification.outer_original_apex_digest -ne '4bdfe2f9158035e7d4dd5efe814f5d1dd9eee1d9052eb7c1f571125e9c67e042') {
    throw 'Candidate 44 root digest alignment violated in manifest!'
}

$Targets = @(
    [pscustomobject]@{ Partition='super'; File='super.img' },
    [pscustomobject]@{ Partition='vbmeta_system_a'; File='vbmeta_system.img' }
)
foreach ($Target in $Targets) {
    $Path = Join-Path $ImageDir $Target.File
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "C44 image missing: $Path" }
    $Item = Get-Item -LiteralPath $Path
    $ExpectedBytes = if ($Target.Partition -eq 'super') { $Manifest.super_image.bytes } else { 131072 }
    $ExpectedSha = if ($Target.Partition -eq 'super') { $Manifest.super_image.sha256 } else { $Manifest.vbmeta_system_image.new_sha256 }
    $Hash = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToUpperInvariant()
    if ([int64]$Item.Length -ne [int64]$ExpectedBytes -or $Hash -ne $ExpectedSha.ToUpperInvariant()) {
        throw "C44 manifest/image mismatch: $($Target.File) (Length: $($Item.Length) vs $ExpectedBytes, Hash: $Hash vs $ExpectedSha)"
    }
    Write-Host "PASS $($Target.File): $($Item.Length) bytes SHA256=$Hash" -ForegroundColor Green
}

if (-not $Execute) {
    Write-Host 'DRY-RUN complete. No Fastboot query or device write was issued.' -ForegroundColor Yellow
    return
}

$LogDir = Join-Path $Root 'reports\c44_candidate44_build_20261004'
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
$LogPath = Join-Path $LogDir ('C44_FLASH_' + (Get-Date).ToUniversalTime().ToString('yyyyMMdd_HHmmss_fff') + '.txt')
Start-Transcript -Path $LogPath | Out-Null
try {
    function Get-DeviceList {
        Write-Host '[CMD] fastboot devices -l'
        $Output = cmd.exe /c "`"$FastbootExe`" devices -l 2>&1" | Out-String
        $Code = $LASTEXITCODE
        if ($Code -ne 0) { throw "fastboot devices -l failed ($Code): $Output" }
        Write-Host $Output.TrimEnd()
        return [pscustomobject]@{ Output=$Output; Lines=@($Output -split "`r?`n" | Where-Object { $_.Trim() }) }
    }

    function Assert-OnlyTarget([string]$Expected) {
        $List = Get-DeviceList
        if ($List.Lines.Count -ne 1 -or $List.Lines[0] -notmatch "^\s*$([regex]::Escape($Expected))\s+fastboot\b") {
            throw "Expected exactly one Bootloader Fastboot device '$Expected'; no further writes issued. Output: $($List.Output)"
        }
        return $List
    }

    function Get-FastbootVar([string]$Name) {
        Write-Host "[CMD] fastboot -s $ExpectedSerial getvar $Name"
        $Output = cmd.exe /c "`"$FastbootExe`" -s $ExpectedSerial getvar $Name 2>&1" | Out-String
        $Code = $LASTEXITCODE
        if ($Code -ne 0) { throw "fastboot getvar $Name failed ($Code): $Output" }
        Write-Host $Output.TrimEnd()
        $Pattern = "(?m)^\s*(?:\(bootloader\)\s*)?$([regex]::Escape($Name)):\s*(?<value>[^\r\n]+?)\s*$"
        if ($Output -match $Pattern) { return $Matches['value'].Trim() }
        throw "Could not parse Fastboot variable '$Name'. Output: $Output"
    }

    function Get-SlotSnapshot {
        $Names = @(
            'product', 'current-slot', 'unlocked', 'is-userspace',
            'slot-unbootable:a', 'slot-successful:a', 'slot-retry-count:a',
            'slot-unbootable:b', 'slot-successful:b', 'slot-retry-count:b'
        )
        $Values = [ordered]@{}
        foreach ($Name in $Names) { $Values[$Name] = Get-FastbootVar $Name }
        return $Values
    }

    function Assert-TargetReady([System.Collections.Specialized.IOrderedDictionary]$Snap) {
        if ($Snap['product'] -ne $ExpectedProduct) { throw "Target product is '$($Snap['product'])', expected '$ExpectedProduct'." }
        if ($Snap['current-slot'] -ne $ExpectedSlot) { throw "Target current-slot is '$($Snap['current-slot'])', expected '$ExpectedSlot'." }
        if ($Snap['unlocked'] -ne 'yes') { throw "Target bootloader is not unlocked." }
        if ($Snap['is-userspace'] -ne 'no') { throw "Target is fastbootd, not Bootloader Fastboot." }
        if ($Snap['slot-unbootable:a'] -ne 'no') { throw "Slot A is marked unbootable." }
    }

    function Write-Partition([string]$Partition, [string]$File) {
        $ImgPath = Join-Path $ImageDir $File
        Write-Host "`n[FLASH] $Partition <- $ImgPath"
        Assert-OnlyTarget $ExpectedSerial | Out-Null
        $Args = @('-s', $ExpectedSerial, 'flash', $Partition, $ImgPath)
        & $FastbootExe @Args
        $Code = $LASTEXITCODE
        Write-Host "[FASTBOOT-EXIT] flash $Partition exit_code=$Code"
        if ($Code -ne 0) { throw "Flashing $Partition failed with exit code $Code." }
    }

    Write-Host '=== THYME-OS4 C44 RESTRICTED FLASH ==='
    Write-Host 'Only super and vbmeta_system_a may be written. Automatic reboot is STRICTLY FORBIDDEN.'

    Assert-OnlyTarget $ExpectedSerial | Out-Null
    $Pre = Get-SlotSnapshot
    Assert-TargetReady $Pre
    Write-Host "`n=== PRE-FLASH DEVICE AND A/B STATE ==="
    foreach ($K in $Pre.Keys) { Write-Host "$K=$($Pre[$K])" }

    # Budget recovery handling
    if ($RestoreRetryBudget -or [int]$Pre['slot-retry-count:a'] -le 2) {
        Write-Host "`n[BUDGET] Restoring Slot A retry budget (fastboot set_active a)..."
        Assert-OnlyTarget $ExpectedSerial | Out-Null
        $Args = @('-s', $ExpectedSerial, 'set_active', 'a')
        & $FastbootExe @Args
        $Code = $LASTEXITCODE
        Write-Host "[FASTBOOT-EXIT] set_active a exit_code=$Code"
        if ($Code -ne 0) { throw "fastboot set_active a failed with exit code $Code." }

        $PostActive = Get-SlotSnapshot
        Assert-TargetReady $PostActive
        Write-Host "`n=== POST SET_ACTIVE A SLOT SNAPSHOT ==="
        foreach ($K in $PostActive.Keys) { Write-Host "$K=$($PostActive[$K])" }
        if ([int]$PostActive['slot-retry-count:a'] -lt 6) {
            throw "Slot A retry count did not recover to >= 6 (got $($PostActive['slot-retry-count:a']))."
        }
    }

    foreach ($Target in $Targets) {
        Write-Partition -Partition $Target.Partition -File $Target.File
    }

    Assert-OnlyTarget $ExpectedSerial | Out-Null
    $Post = Get-SlotSnapshot
    Assert-TargetReady $Post
    Write-Host "`n=== POST-FLASH DEVICE AND A/B STATE ==="
    foreach ($K in $Post.Keys) { Write-Host "$K=$($Post[$K])" }

    Write-Host "`n[COMPLETE] C44 flash sequence complete. Device safely retained in Bootloader Fastboot." -ForegroundColor Green
    Write-Host "[DISCIPLINE] NO REBOOT ISSUED. Awaiting explicit user command: 开始启动 C44." -ForegroundColor Yellow
} finally {
    Stop-Transcript | Out-Null
}
