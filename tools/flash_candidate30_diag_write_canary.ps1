[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Serial,
    [switch]$Execute
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$FastbootExe = Join-Path $Root 'tools\platform-tools\fastboot.exe'
$ImageDir = Join-Path $Root 'work\stage_c30_diag_write_canary_20260930_run1\images'
$ManifestPath = Join-Path $ImageDir 'BUILD_MANIFEST.json'
$ExpectedSerial = $Serial.Trim()
$ExpectedProduct = 'thyme'
$ExpectedSlot = 'a'

if ([string]::IsNullOrWhiteSpace($ExpectedSerial)) { throw 'Pass the serial from the live Fastboot device list.' }
if (-not (Test-Path -LiteralPath $FastbootExe -PathType Leaf)) { throw "Fastboot executable missing: $FastbootExe" }
if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) { throw "C30 manifest missing: $ManifestPath" }

$Manifest = Get-Content -LiteralPath $ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($Manifest.candidate -ne 'Candidate 30 dedicated-domain write canary and ordered startup diagnostics' -or
    $Manifest.base -ne 'Candidate 29 PID1/Zygote ordered diagnostic baseline') {
    throw 'Manifest is not the expected C30 image set based on C29.'
}
if ((@($Manifest.flash_scope_prepared) -join ',') -ne 'super,vbmeta_system_a') {
    throw 'C30 manifest flash scope is not exactly super,vbmeta_system_a.'
}
if (@($Manifest.tree_delta.unexpected_changes).Count -ne 0 -or
    -not $Manifest.tree_changes.netd_zygote_callbacks_remain_absent -or
    -not $Manifest.tree_changes.primary_zygote_critical_unchanged -or
    -not $Manifest.tree_changes.secondary_zygote_rc_unchanged) {
    throw 'C30 tree delta or inherited boot-behavior assertions failed.'
}

$ExpectedModified = @(
    'system/etc/init/hw/init.rc',
    'system/etc/selinux/plat_file_contexts',
    'system/etc/selinux/plat_property_contexts',
    'system/etc/selinux/plat_sepolicy.cil'
)
$ExpectedRemoved = @('system/bin/c29_pid1_zygote_diag', 'system/etc/init/c29_pid1_zygote_diag.rc')
$ExpectedAdded = @('system/bin/c30_diag', 'system/etc/init/c30_diag.rc')
foreach ($Check in @(
    @{ Name='modified'; Expected=$ExpectedModified; Actual=@($Manifest.tree_delta.modified) },
    @{ Name='removed'; Expected=$ExpectedRemoved; Actual=@($Manifest.tree_delta.removed) },
    @{ Name='added'; Expected=$ExpectedAdded; Actual=@($Manifest.tree_delta.added) }
)) {
    $Diff = Compare-Object -ReferenceObject @($Check.Expected | Sort-Object) -DifferenceObject @($Check.Actual | Sort-Object)
    if ($Diff) { throw "C29-to-C30 $($Check.Name) file set differs from the approved diagnostic-only delta." }
}

$Policy = [string]$Manifest.tree_changes.plat_policy_fragment
foreach ($Required in @('(type c30_diag)', '(type c30_diag_exec)',
        '(typetransition init c30_diag_exec process c30_diag)',
        '(allow c30_diag c25_diag_data_file (file (create open read write append getattr setattr)))')) {
    if (-not $Policy.Contains($Required)) { throw "C30 SELinux policy fragment missing: $Required" }
}
if ($Policy -match 'allow\s+c30_diag\s+proc\s*\(' -or $Policy -match 'allow\s+coredomain\s+c30_diag') {
    throw 'C30 policy fragment contains a forbidden broad proc/coredomain grant.'
}
if ($Manifest.system_build.platform_policy_validation.secilc_exit -ne 0 -or
    $Manifest.system_build.platform_policy_validation.neverallow_checks -ne 'enabled') {
    throw 'C30 secilc/neverallow validation is not passing in the manifest.'
}

$Targets = @(
    [pscustomobject]@{ Partition='super'; File='super.img' },
    [pscustomobject]@{ Partition='vbmeta_system_a'; File='vbmeta_system.img' }
)
foreach ($Target in $Targets) {
    $Path = Join-Path $ImageDir $Target.File
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "C30 image missing: $Path" }
    $Item = Get-Item -LiteralPath $Path
    $Expected = $Manifest.images.PSObject.Properties[$Target.File].Value
    $Hash = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToUpperInvariant()
    if ([int64]$Item.Length -ne [int64]$Expected.bytes -or $Hash -ne $Expected.sha256.ToUpperInvariant()) {
        throw "C30 manifest/image mismatch: $($Target.File)"
    }
    Write-Host "PASS $($Target.File): $($Item.Length) bytes SHA256=$Hash" -ForegroundColor Green
}

if (-not $Execute) {
    Write-Host 'DRY-RUN complete. No Fastboot query or device write was issued.' -ForegroundColor Yellow
    return
}

$LogDir = Join-Path $Root 'work\reports\candidate30_flash_20260930'
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
$LogPath = Join-Path $LogDir ('C30_FLASH_' + (Get-Date).ToUniversalTime().ToString('yyyyMMdd_HHmmss_fff') + '.txt')
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
            throw "Expected exactly one Bootloader Fastboot device '$Expected'; no writes issued. Output: $($List.Output)"
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

    Write-Host '=== THYME-OS4 C30 RESTRICTED FLASH ===' -ForegroundColor Cyan
    Write-Host "Serial: $ExpectedSerial; mode: EXECUTE (DEVICE WRITES)"
    $null = Assert-OnlyTarget $ExpectedSerial
    $Before = Get-SlotSnapshot
    Show-Snapshot 'PRE-FLASH DEVICE AND A/B STATE' $Before
    if ($Before['product'] -ne $ExpectedProduct -or $Before['current-slot'] -ne $ExpectedSlot -or
        $Before['unlocked'] -ne 'yes' -or $Before['is-userspace'] -ne 'no' -or
        $Before['slot-unbootable:a'] -ne 'no' -or [int]$Before['slot-retry-count:a'] -le 0) {
        throw 'C30 preflight failed; no writes issued.'
    }

    foreach ($Target in $Targets) {
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
        if ($After[$Name] -ne $Before[$Name]) { throw "Post-flash state changed unexpectedly: $Name $($Before[$Name]) -> $($After[$Name]). No further action issued." }
    }
    if ($After['product'] -ne $ExpectedProduct -or $After['current-slot'] -ne $ExpectedSlot -or
        $After['unlocked'] -ne 'yes' -or $After['is-userspace'] -ne 'no' -or
        $After['slot-unbootable:a'] -ne 'no' -or [int]$After['slot-retry-count:a'] -le 0) {
        throw 'Post-flash Fastboot identity/bootability check failed. No reboot issued.'
    }
    Write-Host 'C30 flash completed. Only super and vbmeta_system_a were written; A/B metadata is unchanged.' -ForegroundColor Green
    Write-Host 'Device remains in Bootloader Fastboot. No reboot, set_active, erase, or other partition operation was issued.' -ForegroundColor Green
}
finally {
    Stop-Transcript | Out-Null
    Write-Host "Fastboot transcript: $LogPath"
}
