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
$ImageDir = Join-Path $Root 'work\stage_c39_diag_runtime_abort_20261003\images'
$ManifestPath = Join-Path $ImageDir 'BUILD_MANIFEST.json'
$ExpectedProduct = 'thyme'
$ExpectedSlot = 'a'
$ExpectedSerial = $Serial.Trim()

if ([string]::IsNullOrWhiteSpace($ExpectedSerial)) { throw 'Pass the serial from the live Bootloader Fastboot device list.' }
if (-not (Test-Path -LiteralPath $FastbootExe -PathType Leaf)) { throw "Fastboot executable missing: $FastbootExe" }
if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) { throw "C39 manifest missing: $ManifestPath" }

$Manifest = Get-Content -LiteralPath $ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($Manifest.candidate -ne 'Candidate 39-DIAG Real Zygote ART Runtime::Abort Level-2 Caller and Message in-situ capture' -or
    $Manifest.base -ne 'Candidate 32-DIAG zygote-domain crash-dump isolation canary') {
    throw 'Manifest is not the expected C39-DIAG image set based on C32.'
}
if ((@($Manifest.flash_scope_prepared) -join ',') -ne 'super,vbmeta_system_a') {
    throw 'C39-DIAG flash scope is not exactly super,vbmeta_system_a.'
}
if (@($Manifest.source_delta.removed).Count -ne 0 -or
    @($Manifest.source_delta.added).Count -ne 0 -or
    @($Manifest.source_delta.modified).Count -ne 2) {
    throw 'C32-to-C39 system tree delta is outside the expected 2 files.'
}

$CanonicalLinkerSha = 'aab9dbfcde057e7c2d934d0f9be1a31629ce17e6c26f008264893d9cd97adedd'
if ($Manifest.canonical_linker64_sha256.ToLowerInvariant() -ne $CanonicalLinkerSha) {
    throw "Manifest canonical linker64 SHA256 mismatch: $($Manifest.canonical_linker64_sha256)"
}

$Targets = @(
    [pscustomobject]@{ Partition='super'; File='super.img' },
    [pscustomobject]@{ Partition='vbmeta_system_a'; File='vbmeta_system.img' }
)
foreach ($Target in $Targets) {
    $Path = Join-Path $ImageDir $Target.File
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "C39 image missing: $Path" }
    $Item = Get-Item -LiteralPath $Path
    $Expected = $Manifest.images.PSObject.Properties[$Target.File].Value
    $Hash = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToUpperInvariant()
    if ([int64]$Item.Length -ne [int64]$Expected.bytes -or $Hash -ne $Expected.sha256.ToUpperInvariant()) {
        throw "C39 manifest/image mismatch: $($Target.File)"
    }
    Write-Host "PASS $($Target.File): $($Item.Length) bytes SHA256=$Hash" -ForegroundColor Green
}

if (-not $Execute) {
    Write-Host 'DRY-RUN complete. No Fastboot query or device write was issued.' -ForegroundColor Yellow
    return
}

$LogDir = Join-Path $Root 'reports\c39_diag_candidate39_build_20261003'
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
$LogPath = Join-Path $LogDir ('C39_DIAG_FLASH_' + (Get-Date).ToUniversalTime().ToString('yyyyMMdd_HHmmss_fff') + '.txt')
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

    Write-Host '=== THYME-OS4 C39-DIAG RESTRICTED FLASH ==='
    Write-Host 'Only super and vbmeta_system_a may be written. Reboot/set_active/erase are excluded.'

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

    Write-Host "`n[COMPLETE] C39-DIAG flash sequence complete. Device safely retained in Bootloader Fastboot." -ForegroundColor Green
} finally {
    Stop-Transcript | Out-Null
}
