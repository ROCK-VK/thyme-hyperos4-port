[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$SourceRoot,
    [string]$DestinationRoot = (Split-Path -Parent $PSScriptRoot),
    [switch]$SkipRawEvidence,
    [string[]]$EvidenceCandidates = @()
)
$ErrorActionPreference = 'Stop'
$SourceRoot = (Resolve-Path -LiteralPath $SourceRoot).Path
$DestinationRoot = [System.IO.Path]::GetFullPath($DestinationRoot)
if (-not (Test-Path -LiteralPath $DestinationRoot)) { throw "Destination repository does not exist: $DestinationRoot" }

$LogDirName = [string]::Concat([char]0x65E5,[char]0x5FD7)
$StateMarker = [string]::Concat([char]0x9879,[char]0x76EE,[char]0x5F53,[char]0x524D,[char]0x72B6,[char]0x6001)
$ExecMarker = [string]::Concat([char]0x6267,[char]0x884C,[char]0x8BB0,[char]0x5F55)
$GuideMarker = [string]::Concat([char]0x5B89,[char]0x5353,[char]0x79FB,[char]0x690D,[char]0x5165,[char]0x95E8,[char]0x6307,[char]0x5357)
$PlanMarker = [string]::Concat([char]0x79FB,[char]0x690D,[char]0x51C6,[char]0x5907,[char]0x8BA1,[char]0x5212)

# Explicit allowlist: source paths not listed here are never copied.
$Allowlist = @(
    @{ Source='@PROJECT_STATUS'; Destination='logs/PROJECT_STATUS.md' }
    @{ Source='@EXECUTION_LOG'; Destination='logs/EXECUTION_LOG.md' }
    @{ Source='@PORTING_GUIDE'; Destination='docs/guides/android-porting-introduction.md' }
    @{ Source='@PREPARATION_PLAN'; Destination='docs/guides/porting-preparation-plan.md' }
    @{ Source='@REVIEW_HANDOFF'; Destination='docs/guides/thyme-os4-review-handoff.md' }
    @{ Source='tools/audit_candidate8_property_contexts.py'; Destination='tools/audit_candidate8_property_contexts.py' }
    @{ Source='tools/audit_c13_selinux.py'; Destination='tools/audit_c13_selinux.py' }
    @{ Source='tools/audit_salvaged_ramoops.py'; Destination='tools/audit_salvaged_ramoops.py' }
    @{ Source='tools/build_candidate9.py'; Destination='tools/build_candidate9.py' }
    @{ Source='tools/build_candidate10_warm_dtb.py'; Destination='tools/build_candidate10_warm_dtb.py' }
    @{ Source='tools/build_candidate11.py'; Destination='tools/build_candidate11.py' }
    @{ Source='tools/build_candidate12.py'; Destination='tools/build_candidate12.py' }
    @{ Source='tools/build_candidate13.py'; Destination='tools/build_candidate13.py' }
    @{ Source='tools/build_candidate13_1_data_guard.py'; Destination='tools/build_candidate13_1_data_guard.py' }
    @{ Source='tools/build_candidate14_bpf_bootstrap_bypass.py'; Destination='tools/build_candidate14_bpf_bootstrap_bypass.py' }
    @{ Source='tools/build_candidate15_angle_egl.py'; Destination='tools/build_candidate15_angle_egl.py' }
    @{ Source='tools/build_candidate16_graphics_allocator_ion.py'; Destination='tools/build_candidate16_graphics_allocator_ion.py' }
    @{ Source='tools/build_candidate17_graphics_allocator_open.py'; Destination='tools/build_candidate17_graphics_allocator_open.py' }
    @{ Source='tools/build_candidate18_native_adreno.py'; Destination='tools/build_candidate18_native_adreno.py' }
    @{ Source='tools/build_standalone_diag.py'; Destination='tools/build_standalone_diag.py' }
    @{ Source='tools/build_candidate25_first_screen_diag.py'; Destination='tools/build_candidate25_first_screen_diag.py' }
    @{ Source='tools/build_candidate26_zygote_diag.py'; Destination='tools/build_candidate26_zygote_diag.py' }
    @{ Source='tools/flash_candidate25_first_screen_diag.ps1'; Destination='tools/flash_candidate25_first_screen_diag.ps1' }
    @{ Source='tools/flash_candidate26_zygote_diag.ps1'; Destination='tools/flash_candidate26_zygote_diag.ps1' }
    @{ Source='tools/start_candidate25_observed_boot.ps1'; Destination='tools/start_candidate25_observed_boot.ps1' }
    @{ Source='tools/start_candidate26_observed_boot.ps1'; Destination='tools/start_candidate26_observed_boot.ps1' }
    @{ Source='tools/candidate25_bootdiag/c25_bootdiag.cpp'; Destination='tools/candidate25_bootdiag/c25_bootdiag.cpp' }
    @{ Source='tools/candidate25_bootdiag/c25_bootdiag.rc'; Destination='tools/candidate25_bootdiag/c25_bootdiag.rc' }
    @{ Source='tools/candidate25_bootdiag/c25_policy_fragment.cil'; Destination='tools/candidate25_bootdiag/c25_policy_fragment.cil' }
    @{ Source='tools/candidate26_zygote_diag/c26_zygote_diag.cpp'; Destination='tools/candidate26_zygote_diag/c26_zygote_diag.cpp' }
    @{ Source='tools/candidate26_zygote_diag/c26_zygote_diag.rc'; Destination='tools/candidate26_zygote_diag/c26_zygote_diag.rc' }
    @{ Source='tools/flash_candidate13.ps1'; Destination='tools/flash_candidate13.ps1' }
    @{ Source='tools/flash_candidate14_bpf_bootstrap_bypass.ps1'; Destination='tools/flash_candidate14_bpf_bootstrap_bypass.ps1' }
    @{ Source='tools/flash_candidate15_angle_egl.ps1'; Destination='tools/flash_candidate15_angle_egl.ps1' }
    @{ Source='tools/flash_candidate16_graphics_allocator_ion.ps1'; Destination='tools/flash_candidate16_graphics_allocator_ion.ps1' }
    @{ Source='tools/flash_candidate17_graphics_allocator_open.ps1'; Destination='tools/flash_candidate17_graphics_allocator_open.ps1' }
    @{ Source='tools/flash_candidate18_native_adreno.ps1'; Destination='tools/flash_candidate18_native_adreno.ps1' }
    @{ Source='tools/build_candidate19_rgbx_egl.py'; Destination='tools/build_candidate19_rgbx_egl.py' }
    @{ Source='tools/flash_candidate19_rgbx_egl.ps1'; Destination='tools/flash_candidate19_rgbx_egl.ps1' }
    @{ Source='tools/start_candidate19_observed_boot.ps1'; Destination='tools/start_candidate19_observed_boot.ps1' }
    @{ Source='tools/observe_candidate13_readonly.py'; Destination='tools/observe_candidate13_readonly.py' }
    @{ Source='tools/record_candidate13_event.ps1'; Destination='tools/record_candidate13_event.ps1' }
    @{ Source='tools/start_candidate13_observed_boot.ps1'; Destination='tools/start_candidate13_observed_boot.ps1' }
    @{ Source='tools/start_candidate18_observed_boot.ps1'; Destination='tools/start_candidate18_observed_boot.ps1' }
    @{ Source='tools/patch_candidate_fs_configs.py'; Destination='tools/patch_candidate_fs_configs.py' }
    @{ Source='tools/precheck_candidate9.py'; Destination='tools/precheck_candidate9.py' }
    @{ Source='tools/precheck_candidate10_warm_dtb.py'; Destination='tools/precheck_candidate10_warm_dtb.py' }
    @{ Source='tools/precheck_candidate11.py'; Destination='tools/precheck_candidate11.py' }
    @{ Source='tools/precheck_candidate12.py'; Destination='tools/precheck_candidate12.py' }
    @{ Source='tools/precheck_candidate13.py'; Destination='tools/precheck_candidate13.py' }
    @{ Source='tools/restore_pixelos_a0_prime.ps1'; Destination='tools/restore_pixelos_a0_prime.ps1' }
    @{ Source='tools/salvage_c10_diag.py'; Destination='tools/salvage_c10_diag.py' }
    @{ Source='tools/salvage_c11_diag.py'; Destination='tools/salvage_c11_diag.py' }
    @{ Source='tools/salvage_c12_diag.py'; Destination='tools/salvage_c12_diag.py' }
    @{ Source='tools/salvage_c13_diag.py'; Destination='tools/salvage_c13_diag.py' }
    @{ Source='work/reports/20260918_K40_THREE_WAY_PORT_REVERSE_ENGINEERING_1.md'; Destination='reports/k40/20260918_K40_THREE_WAY_PORT_REVERSE_ENGINEERING_1.md' }
    @{ Source='work/reports/20260918_K40_THREE_WAY_PORT_REVIEW_1.md'; Destination='reports/k40/20260918_K40_THREE_WAY_PORT_REVIEW_1.md' }
    @{ Source='work/reports/20260924_CANDIDATE9_POSTMORTEM_AND_CANDIDATE10_PLAN.md'; Destination='reports/20260924_CANDIDATE9_POSTMORTEM_AND_CANDIDATE10_PLAN.md' }
    @{ Source='work/reports/20260924_THYME_OS4_CANDIDATE10_WARMDTB_BUILD_AND_EXPERIMENT_PLAN.md'; Destination='reports/20260924_THYME_OS4_CANDIDATE10_WARMDTB_BUILD_AND_EXPERIMENT_PLAN.md' }
    @{ Source='work/reports/20260924_THYME_OS4_CANDIDATE9_RUN_AND_NEXT_BLOCKERS.md'; Destination='reports/20260924_THYME_OS4_CANDIDATE9_RUN_AND_NEXT_BLOCKERS.md' }
    @{ Source='work/reports/20260925_CANDIDATE13_RECOVERY_ANALYSIS.md'; Destination='reports/candidate13/20260925_CANDIDATE13_RECOVERY_ANALYSIS.md' }
    @{ Source='work/reports/20260925_CANDIDATE13_ROOT_CAUSE_AND_NEXT_EXPERIMENT.md'; Destination='reports/candidate13/20260925_CANDIDATE13_ROOT_CAUSE_AND_NEXT_EXPERIMENT.md' }
    @{ Source='work/reports/20260926_CANDIDATE13_SECOND_STAGE_CAPTURE_PREP.md'; Destination='reports/candidate13/20260926_CANDIDATE13_SECOND_STAGE_CAPTURE_PREP.md' }
    @{ Source='work/reports/20260926_CANDIDATE13_NETBPFLOAD_FAILURE_AND_C14_BUILD.md'; Destination='reports/candidate13/20260926_CANDIDATE13_NETBPFLOAD_FAILURE_AND_C14_BUILD.md' }
    @{ Source='work/reports/20260926_CANDIDATE14_FAILURE_AND_CANDIDATE15_EGL_PLAN.md'; Destination='reports/candidate15/20260926_CANDIDATE14_FAILURE_AND_CANDIDATE15_EGL_PLAN.md' }
    @{ Source='work/reports/20260926_CANDIDATE15_FIRST_BOOT_AND_CANDIDATE16_GRAPHICS_ALLOCATOR_FIX.md'; Destination='reports/candidate16/20260926_CANDIDATE15_FIRST_BOOT_AND_CANDIDATE16_GRAPHICS_ALLOCATOR_FIX.md' }
    @{ Source='work/reports/20260926_CANDIDATE16_FAILURE_AND_CANDIDATE17_BUILD_FLASH.md'; Destination='reports/candidate17/20260926_CANDIDATE16_FAILURE_AND_CANDIDATE17_BUILD_FLASH.md' }
    @{ Source='work/reports/20260926_CANDIDATE17_FIRST_BOOT/REPORT.md'; Destination='reports/candidate17/20260926_CANDIDATE17_FIRST_BOOT_REPORT.md' }
    @{ Source='work/reports/20260926_CANDIDATE17_RETEST/REPORT.md'; Destination='reports/candidate17/20260926_CANDIDATE17_RETEST_REPORT.md' }
    @{ Source='work/reports/20260926_CANDIDATE18_NATIVE_ADRENO/REPORT.md'; Destination='reports/candidate18/20260926_CANDIDATE18_NATIVE_ADRENO_REPORT.md' }
    @{ Source='work/reports/20260926_C18_NATIVE_ADRENO/C18_RETEST_REPORT.md'; Destination='reports/candidate18/C18_RETEST_REPORT.md' }
    @{ Source='work/stage_h_thyme_os4_candidate_18_native_adreno_run1/images/BUILD_MANIFEST.json'; Destination='reports/candidate18/BUILD_MANIFEST.json' }
    @{ Source='work/reports/20260927_CANDIDATE19_RGBX_EGL/REPORT.md'; Destination='reports/candidate19/REPORT.md' }
    @{ Source='work/stage_i_thyme_os4_candidate_19_rgbx_egl_run1/images/BUILD_MANIFEST.json'; Destination='reports/candidate19/BUILD_MANIFEST.json' }
    @{ Source='work/reports/20260927_CANDIDATE23_SF_PRIME_SKIP/REPORT.md'; Destination='reports/candidate23/REPORT.md' }
    @{ Source='work/reports/20260928_C25_FIRST_SCREEN_DIAG/C25_FIRST_SCREEN_DIAGNOSTIC_BUILD_FLASH_20260928.md'; Destination='reports/candidate25/C25_FIRST_SCREEN_DIAGNOSTIC_BUILD_FLASH_20260928.md' }
    @{ Source='work/stage_o_thyme_os4_candidate_25_first_screen_diag_20260928_run5/BUILD_REPORT.md'; Destination='reports/candidate25/BUILD_REPORT.md' }
    @{ Source='work/stage_o_thyme_os4_candidate_25_first_screen_diag_20260928_run5/images/BUILD_MANIFEST.json'; Destination='reports/candidate25/BUILD_MANIFEST.json' }
    @{ Source='work/reports/20260929_C26_ZYGOTE_FIRST_EXIT/C26_BUILD_FLASH_STATUS.md'; Destination='reports/candidate26/C26_BUILD_FLASH_STATUS.md' }
    @{ Source='work/reports/20260929_C26_ZYGOTE_FIRST_EXIT/runtime_comparison.txt'; Destination='reports/candidate26/runtime_comparison.txt' }
    @{ Source='work/stage_c26_zygote_diag_20260929_run2/C26_ZYGOTE_DIAGNOSTIC_BUILD_REPORT.md'; Destination='reports/candidate26/C26_ZYGOTE_DIAGNOSTIC_BUILD_REPORT.md' }
    @{ Source='work/stage_c26_zygote_diag_20260929_run2/images/BUILD_MANIFEST.json'; Destination='reports/candidate26/BUILD_MANIFEST.json' }
    @{ Source='work/reports/20260926_CANDIDATE13_NETBPFLOAD_EVIDENCE_EXCERPT.txt'; Destination='reports/boot-logs/candidate13_netbpfload_failure_excerpt.txt' }
    @{ Source='@STORAGE_SAFETY_REPORT'; Destination='reports/candidate13/20260925_CANDIDATE13_STORAGE_SAFETY_AND_FIRST_FAILURE.md' }
    @{ Source='work/reports/20260924_CANDIDATE10_WARMDTB_LOG_SALVAGE/pstore/console-ramoops-0'; Destination='reports/boot-logs/candidate10_console-ramoops.txt' }
    @{ Source='work/reports/20260924_CANDIDATE11_LOG_SALVAGE/pstore/console-ramoops-0'; Destination='reports/boot-logs/candidate11_console-ramoops.txt' }
    @{ Source='work/reports/20260924_CANDIDATE11_LOG_SALVAGE/pmsg_clean.txt'; Destination='reports/boot-logs/candidate11_pmsg-ramoops.txt' }
    @{ Source='work/reports/20260925_CANDIDATE12_LOG_SALVAGE/pstore/console-ramoops-0'; Destination='reports/boot-logs/candidate12_console-ramoops.txt' }
    @{ Source='work/reports/20260925_CANDIDATE12_LOG_SALVAGE/pmsg_clean.txt'; Destination='reports/boot-logs/candidate12_pmsg-ramoops.txt' }
    @{ Source='work/reports/20260925_CANDIDATE13_LOG_SALVAGE/run_20260925_165614/pstore/console-ramoops-0'; Destination='reports/boot-logs/candidate13_recovery_console-ramoops.txt' }
    @{ Source='work/reports/20260925_CANDIDATE13_LOG_SALVAGE/run_20260926_002005/pstore/console-ramoops-0'; Destination='reports/boot-logs/candidate13_clean_data_console-ramoops.txt' }
    @{ Source='work/reports/20260925_CANDIDATE13_STORAGE_SAFETY_AND_FIRST_FAILURE/observations/run_20260926_001542/usb_adb_fastboot_timeline.csv'; Destination='reports/boot-logs/candidate13_usb_adb_fastboot_timeline.csv' }
)

function Resolve-AllowlistedSource([string]$RelativeSource) {
    switch ($RelativeSource) {
        '@PROJECT_STATUS' { $d=Join-Path $SourceRoot $LogDirName; return (Get-ChildItem -LiteralPath $d -File -Filter '*.md' | Where-Object {$_.Name.Contains($StateMarker)} | Select-Object -First 1).FullName }
        '@EXECUTION_LOG' { $d=Join-Path $SourceRoot $LogDirName; return (Get-ChildItem -LiteralPath $d -File -Filter '*.md' | Where-Object {$_.Name.Contains($ExecMarker)} | Select-Object -First 1).FullName }
        '@PORTING_GUIDE' { return (Get-ChildItem -LiteralPath $SourceRoot -File -Filter '*.md' | Where-Object {$_.Name.Contains($GuideMarker)} | Select-Object -First 1).FullName }
        '@PREPARATION_PLAN' { return (Get-ChildItem -LiteralPath $SourceRoot -File -Filter '*.md' | Where-Object {$_.Name.Contains($PlanMarker)} | Select-Object -First 1).FullName }
        '@REVIEW_HANDOFF' { return (Get-ChildItem -LiteralPath $SourceRoot -File -Filter 'THYME_OS4_*.md' | Select-Object -First 1).FullName }
        '@STORAGE_SAFETY_REPORT' { $d=Join-Path $SourceRoot 'work/reports/20260925_CANDIDATE13_STORAGE_SAFETY_AND_FIRST_FAILURE'; return (Get-ChildItem -LiteralPath $d -File -Filter '*.md' | Select-Object -First 1).FullName }
        default { return (Join-Path $SourceRoot $RelativeSource) }
    }
}

function ConvertTo-PublicText([string]$Text) {
    $Text = [regex]::Replace($Text, '(?i)\b[A-Z]:\\(?:[^\\\r\n]+\\)*10S_OS4', '[LOCAL_PROJECT_ROOT]')
    $Text = [regex]::Replace($Text, '(?i)\b[A-Z]:/(?:[^/\r\n]+/)*10S_OS4', '[LOCAL_PROJECT_ROOT]')
    if (-not [string]::IsNullOrWhiteSpace($env:COMPUTERNAME)) {
        $Text = [regex]::Replace($Text, '(?i)\b' + [regex]::Escape($env:COMPUTERNAME) + '\b', '[LOCAL_HOST]')
    }
    $Text = [regex]::Replace($Text, '(?i)/mnt/[a-z]/RVK/10S_OS4', '/path/to/thyme-os4-local')
    $Text = [regex]::Replace($Text, '(?m)^([^\r\n]*?/path/to/thyme-os4-local[^\r\n]*?)[ \t]+\r?$', '$1')
    $Text = [regex]::Replace($Text, '(?i)/root/10s_os4_build', '/path/to/thyme-os4-build')
    $Text = [regex]::Replace($Text, '(?i)(androidboot\.cpuid=)0x[0-9a-f]+', '$1[REDACTED_CPUID]')
    $Text = [regex]::Replace($Text, '(?i)\b[A-Z]:\\Users\\[^\s"''<>|]+', '[LOCAL_USER_PATH]')
    $Text = [regex]::Replace($Text, '(?i)\b[DE]:\\[^\s"''<>|]+', '[LOCAL_PATH]')
    $Text = [regex]::Replace($Text, '(?i)\b[DE]:/[^\s"''<>|]+', '[LOCAL_PATH]')
    $Text = [regex]::Replace($Text, '(?i)\b(?=[a-f0-9]{8}\b)(?=[a-f0-9]*[a-f])(?=[a-f0-9]*[0-9])[a-f0-9]{8}\b', '[REDACTED_DEVICE_ID]')
    $Text = [regex]::Replace($Text, '(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b', '[REDACTED_EMAIL]')
    $Text = [regex]::Replace($Text, '(?i)\b[A-Z]:\\Users\\[^\\\r\n\s"'']+', '[LOCAL_USER_PATH]')
    $Text = [regex]::Replace($Text, '(?i)\b\d{15,17}\b', '[REDACTED_LONG_ID]')
    $LocalBuildDir = [string]::Concat('10s','_os4_build')
    $Text = [regex]::Replace($Text, '(?i)' + [regex]::Escape($LocalBuildDir), '[LOCAL_WSL_BUILD_DIR]')
    $Text = [regex]::Replace($Text, '\bgh[pousr]_[A-Za-z0-9_]{20,}\b|\bgithub_pat_[A-Za-z0-9_]{20,}\b', '[REDACTED_GITHUB_TOKEN]')
    $Text = [regex]::Replace($Text, '-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----', '[REDACTED_PRIVATE_KEY]', [System.Text.RegularExpressions.RegexOptions]::Singleline)
    return $Text
}

$Copied = 0
$Missing = @()
foreach ($Entry in $Allowlist) {
    $SourcePath = Resolve-AllowlistedSource $Entry.Source
    if ([string]::IsNullOrWhiteSpace($SourcePath) -or -not (Test-Path -LiteralPath $SourcePath -PathType Leaf)) { $Missing += $Entry.Source; continue }
    $SourceItem = Get-Item -LiteralPath $SourcePath -Force
    if (($SourceItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw "Refusing reparse point: $($Entry.Source)" }
    if ($SourceItem.Length -gt 100MB) { throw "Refusing file over 100 MiB: $($Entry.Source)" }
    $DestinationPath = Join-Path $DestinationRoot $Entry.Destination
    New-Item -ItemType Directory -Path (Split-Path -Parent $DestinationPath) -Force | Out-Null
    $Text = [IO.File]::ReadAllText($SourcePath, [Text.Encoding]::UTF8)
    $Text = ConvertTo-PublicText $Text
    if ($Entry.Destination -eq 'tools/build_candidate18_native_adreno.py') {
        $Text = $Text.Replace('[LOCAL_WSL_USER]/10s_os4_build', '/path/to/thyme-os4-build')
    }
    if ($Entry.Destination -in @('tools/build_candidate25_first_screen_diag.py','reports/candidate25/BUILD_MANIFEST.json')) {
        $Text = $Text.Replace('[LOCAL_WSL_USER]/10s_os4_build', '/path/to/thyme-os4-build')
    }
    if ($Entry.Destination -eq 'tools/build_standalone_diag.py') {
        $Text = $Text.Replace('[REDACTED_DEVICE_ID]', 'THYME-DIAG')
    }
    if ($Entry.Destination -match '_pmsg-ramoops\.txt$') { $Text = $Text.Replace([string][char]0, '') }
    [IO.File]::WriteAllText($DestinationPath, $Text, [Text.UTF8Encoding]::new($false))
    $Copied++
}
[pscustomobject]@{Copied=$Copied; Missing=$Missing; Destination=$DestinationRoot} | ConvertTo-Json -Depth 4
if ($Missing.Count -gt 0) { Write-Warning ('Allowlisted source files absent: ' + ($Missing -join ', ')) }
if (-not $SkipRawEvidence) {
    $RawEvidenceSync = Join-Path $PSScriptRoot 'sync_raw_startup_evidence.ps1'
    if ($EvidenceCandidates.Count -gt 0) {
        & $RawEvidenceSync -SourceRoot $SourceRoot -DestinationRoot $DestinationRoot -Candidates $EvidenceCandidates
    } else {
        & $RawEvidenceSync -SourceRoot $SourceRoot -DestinationRoot $DestinationRoot
    }
}
