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
$ImageDir = Join-Path $Root 'work\stage_c42_display_config_fix_20261004\images'
$ManifestPath = Join-Path $ImageDir 'BUILD_MANIFEST.json'
$ExpectedProduct = 'thyme'
$ExpectedSlot = 'a'
$ExpectedSerial = $Serial.Trim()

if ([string]::IsNullOrWhiteSpace($ExpectedSerial)) { throw 'Pass the serial from the live Bootloader Fastboot device list.' }
if (-not (Test-Path -LiteralPath $FastbootExe -PathType Leaf)) { throw "Fastboot executable missing: $FastbootExe" }
if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) { throw "C42 manifest missing: $ManifestPath" }

$Manifest = Get-Content -LiteralPath $ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($Manifest.candidate -ne 'Candidate 42 DisplayDeviceConfig Minimum Brightness Fix' -or
    $Manifest.base_candidate -ne 'Candidate 40 MediaProfiles Single-Variable Property Fix') {
    throw 'Manifest is not the expected C42 image set based on C40.'
}

if ($Manifest.single_variable_modification.old_value -ne '0.001709819' -or
    $Manifest.single_variable_modification.new_value -ne '0.000854597' -or
    $Manifest.single_variable_modification.byte_diff_count -ne 7) {
    throw 'Candidate 42 single-variable modification constraint violated in manifest!'
}

$Targets = @(
    [pscustomobject]@{ Partition='super'; File='super.img' },
    [pscustomobject]@{ Partition='vbmeta_a'; File='vbmeta.img' }
)
foreach ($Target in $Targets) {
    $Path = Join-Path $ImageDir $Target.File
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "C42 image missing: $Path" }
    $Item = Get-Item -LiteralPath $Path
    $ExpectedBytes = if ($Target.Partition -eq 'super') { $Manifest.super_image.bytes } else { 131072 }
    $ExpectedSha = if ($Target.Partition -eq 'super') { $Manifest.super_image.sha256 } else { $Manifest.vbmeta_image.new_vbmeta_sha256 }
    $Hash = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToUpperInvariant()
    if ([int64]$Item.Length -ne [int64]$ExpectedBytes -or $Hash -ne $ExpectedSha.ToUpperInvariant()) {
        throw "C42 manifest/image mismatch: $($Target.File)"
    }
    Write-Host "PASS $($Target.File): $($Item.Length) bytes SHA256=$Hash" -ForegroundColor Green
}

if (-not $Execute) {
    Write-Host 'DRY-RUN complete. No Fastboot query or device write was issued.' -ForegroundColor Yellow
    return
}

$LogDir = Join-Path $Root 'reports\c42_candidate42_build_20261004'
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
$LogPath = Join-Path $LogDir ('C42_FLASH_' + (Get-Date).ToUniversalTime().ToString('yyyyMMdd_HHmmss_fff') + '.txt')
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
        if ($Snap['slot-retry-count:a'] -eq '0') { throw "Slot A retry count exhausted." }
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

    Write-Host '=== THYME-OS4 C42 RESTRICTED FLASH ==='
    Write-Host 'Only super and vbmeta_a may be written. Reboot/set_active/erase are STRICTLY EXCLUDED.'

    Assert-OnlyTarget $ExpectedSerial | Out-Null
    $Pre = Get-SlotSnapshot
    Assert-TargetReady $Pre
    Write-Host "=== PRE-FLASH DEVICE AND A/B STATE ==="
    foreach ($K in $Pre.Keys) { Write-Host "$K=$($Pre[$K])" }

    foreach ($Target in $Targets) {
        Write-Partition -Partition $Target.Partition -File $Target.File
    }

    Assert-OnlyTarget $ExpectedSerial | Out-Null
    $Post = Get-SlotSnapshot
    Assert-TargetReady $Post
    Write-Host "=== POST-FLASH DEVICE AND A/B STATE ==="
    foreach ($K in $Post.Keys) { Write-Host "$K=$($Post[$K])" }

    Write-Host "`n[COMPLETE] C42 flash sequence complete. Device safely retained in Bootloader Fastboot." -ForegroundColor Green
} finally {
    Stop-Transcript | Out-Null
}
