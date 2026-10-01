[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Serial,
    [switch]$Execute
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$FastbootExe = Join-Path $Root 'tools\platform-tools\fastboot.exe'
$ImageDir = Join-Path $Root 'work\stage_c31_diag_zygote_critical_20261001_run1\images'
$ManifestPath = Join-Path $ImageDir 'BUILD_MANIFEST.json'
$C30ManifestPath = Join-Path $Root 'work\stage_c30_diag_write_canary_20260930_run1\images\BUILD_MANIFEST.json'
$ExpectedProduct = 'thyme'
$ExpectedSlot = 'a'
$ExpectedSerial = $Serial.Trim()

if ([string]::IsNullOrWhiteSpace($ExpectedSerial)) { throw 'Pass the serial from the live Fastboot device list.' }
if (-not (Test-Path -LiteralPath $FastbootExe -PathType Leaf)) { throw "Fastboot executable missing: $FastbootExe" }
if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) { throw "C31-DIAG manifest missing: $ManifestPath" }

$Manifest = Get-Content -LiteralPath $ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($Manifest.candidate -ne 'Candidate 31-DIAG primary Zygote critical escalation causal capture' -or
    $Manifest.base -ne 'Candidate 30 dedicated-domain write canary and ordered startup diagnostics') {
    throw 'Manifest is not the expected C31-DIAG image set based on C30.'
}
if ((@($Manifest.flash_scope_prepared) -join ',') -ne 'super,vbmeta_system_a') {
    throw 'C31-DIAG flash scope is not exactly super,vbmeta_system_a.'
}
if (-not (Test-Path -LiteralPath $C30ManifestPath -PathType Leaf)) { throw "C30 baseline manifest missing: $C30ManifestPath" }
$C30Manifest = Get-Content -LiteralPath $C30ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
if (@($Manifest.source_delta.removed).Count -ne 0 -or @($Manifest.source_delta.added).Count -ne 0 -or
    @($Manifest.source_delta.modified).Count -ne 1 -or
    $Manifest.source_delta.modified[0] -ne 'system/etc/init/hw/init.rc' -or
    @($Manifest.source_delta.unexpected_changes).Count -ne 0) {
    throw 'C30-to-C31-DIAG tree delta is outside the single init.rc diagnostic change.'
}
if ($Manifest.system_build.new_files.Count -ne 0 -or
    $Manifest.system_build.changed_files.Count -ne 1 -or
    $Manifest.system_build.changed_files[0] -ne 'system/etc/init/hw/init.rc' -or
    $Manifest.system_build.platform_policy_sha256_unchanged -ne
        $C30Manifest.system_build.final_erofs_readback.'/system/etc/selinux/plat_sepolicy.cil'.sha256 -or
    $Manifest.system_build.property_contexts_sha256_unchanged -ne
        $C30Manifest.system_build.final_erofs_readback.'/system/etc/selinux/plat_property_contexts'.sha256) {
    throw 'C31-DIAG system change set is inconsistent with the single-file diagnostic.'
}
if ($Manifest.system_build.existing_init_permissions.new_selinux_rules -ne $false) {
    throw 'C31-DIAG unexpectedly adds SELinux rules.'
}

$Targets = @(
    [pscustomobject]@{ Partition='super'; File='super.img' },
    [pscustomobject]@{ Partition='vbmeta_system_a'; File='vbmeta_system.img' }
)
foreach ($Target in $Targets) {
    $Path = Join-Path $ImageDir $Target.File
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "C31-DIAG image missing: $Path" }
    $Item = Get-Item -LiteralPath $Path
    $Expected = $Manifest.images.PSObject.Properties[$Target.File].Value
    $Hash = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToUpperInvariant()
    if ([int64]$Item.Length -ne [int64]$Expected.bytes -or $Hash -ne $Expected.sha256.ToUpperInvariant()) {
        throw "C31-DIAG manifest/image mismatch: $($Target.File)"
    }
    Write-Host "PASS $($Target.File): $($Item.Length) bytes SHA256=$Hash" -ForegroundColor Green
}

if (-not $Execute) {
    Write-Host 'DRY-RUN complete. No Fastboot query or device write was issued.' -ForegroundColor Yellow
    return
}

$LogDir = Join-Path $Root 'work\reports\candidate31_diag_20261001'
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
$LogPath = Join-Path $LogDir ('C31_DIAG_FLASH_' + (Get-Date).ToUniversalTime().ToString('yyyyMMdd_HHmmss_fff') + '.txt')
Start-Transcript -Path $LogPath | Out-Null
try {
    function Get-DeviceList {
        Write-Host '[CMD] fastboot devices -l'
        $Output = & $FastbootExe devices -l 2>&1 | Out-String
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
        $Output = & $FastbootExe -s $ExpectedSerial getvar $Name 2>&1 | Out-String
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
        $Snapshot = [ordered]@{}
        foreach ($Name in $Names) { $Snapshot[$Name] = Get-FastbootVar $Name }
        return $Snapshot
    }

    function Show-Snapshot([string]$Label, $Snapshot) {
        Write-Host "=== $Label ===" -ForegroundColor Cyan
        foreach ($Name in $Snapshot.Keys) { Write-Host ("{0}={1}" -f $Name, $Snapshot[$Name]) }
    }

    Write-Host '=== THYME-OS4 C31-DIAG RESTRICTED FLASH ===' -ForegroundColor Cyan
    Write-Host "Serial: $ExpectedSerial; mode: EXECUTE (DEVICE WRITES)"
    $null = Assert-OnlyTarget $ExpectedSerial
    $Before = Get-SlotSnapshot
    Show-Snapshot 'PRE-FLASH DEVICE AND A/B STATE' $Before
    if ($Before['product'] -ne $ExpectedProduct -or $Before['current-slot'] -ne $ExpectedSlot -or
        $Before['unlocked'] -ne 'yes' -or $Before['is-userspace'] -ne 'no' -or
        $Before['slot-unbootable:a'] -ne 'no' -or [int]$Before['slot-retry-count:a'] -le 0) {
        throw 'C31-DIAG preflight failed; no writes issued.'
    }

    foreach ($Target in $Targets) {
        $null = Assert-OnlyTarget $ExpectedSerial
        $Path = Join-Path $ImageDir $Target.File
        Write-Host "[FLASH] $($Target.Partition) <= $($Target.File)"
        & $FastbootExe -s $ExpectedSerial flash $Target.Partition $Path
        $Code = $LASTEXITCODE
        Write-Host "[FASTBOOT-EXIT] flash $($Target.Partition) exit_code=$Code"
        if ($Code -ne 0) { throw "Fastboot failed on $($Target.Partition) ($Code); stopped without retry or reboot." }
    }

    $null = Assert-OnlyTarget $ExpectedSerial
    $After = Get-SlotSnapshot
    Show-Snapshot 'POST-FLASH DEVICE AND A/B STATE' $After
    foreach ($Name in @('product','current-slot','unlocked','is-userspace',
            'slot-unbootable:a','slot-successful:a','slot-retry-count:a',
            'slot-unbootable:b','slot-successful:b','slot-retry-count:b')) {
        if ($After[$Name] -ne $Before[$Name]) {
            throw "Post-flash state changed unexpectedly: $Name $($Before[$Name]) -> $($After[$Name]). No further action issued."
        }
    }
    Write-Host 'C31-DIAG flash completed. Only super and vbmeta_system_a were written; A/B metadata is unchanged.' -ForegroundColor Green
    Write-Host 'Device remains in Bootloader Fastboot. No reboot, set_active, erase, or other partition operation was issued.' -ForegroundColor Green
}
finally {
    Stop-Transcript | Out-Null
    Write-Host "Fastboot transcript: $LogPath"
}
