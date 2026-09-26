[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$SourceRoot,
    [string]$DestinationRoot = (Split-Path -Parent $PSScriptRoot)
)
$ErrorActionPreference = 'Stop'
$SourceRoot = (Resolve-Path -LiteralPath $SourceRoot).Path
$DestinationRoot = [System.IO.Path]::GetFullPath($DestinationRoot)
$EvidenceRoot = Join-Path $DestinationRoot 'evidence'
if (-not (Test-Path -LiteralPath $DestinationRoot)) { throw "Destination repository does not exist: $DestinationRoot" }

# Explicit capture-directory allowlist. Add a verified Standalone export or host-observation
# directory here after each experiment. Unlisted source paths are never traversed or copied.
$RawDirectoryAllowlist = @(
    @{ Candidate='C13'; Source='work/reports/20260925_CANDIDATE13_LOG_SALVAGE'; Destination='candidate13/standalone' }
    @{ Candidate='C13'; Source='work/reports/20260925_CANDIDATE13_STORAGE_SAFETY_AND_FIRST_FAILURE/observations/run_20260926_001542'; Destination='candidate13/host-observations/run_20260926_001542_unlabeled' }
    @{ Candidate='C13'; Source='work/reports/20260925_CANDIDATE13_STORAGE_SAFETY_AND_FIRST_FAILURE/observations/run_20260926_122156'; Destination='candidate13/host-observations/run_20260926_122156' }
    @{ Candidate='C14'; Source='work/reports/20260926_CANDIDATE14_FIRST_BOOT/standalone'; Destination='candidate14/standalone' }
    @{ Candidate='C14'; Source='work/reports/20260925_CANDIDATE13_STORAGE_SAFETY_AND_FIRST_FAILURE/observations/candidate14/run_20260926_152457'; Destination='candidate14/host-observations/run_20260926_152457' }
    @{ Candidate='C15'; Source='work/reports/20260926_CANDIDATE15_FIRST_BOOT/standalone'; Destination='candidate15/standalone' }
    @{ Candidate='C15'; Source='work/reports/20260925_CANDIDATE13_STORAGE_SAFETY_AND_FIRST_FAILURE/observations/run_20260926_173743'; Destination='candidate15/host-observations/run_20260926_173743' }
    @{ Candidate='C16'; Source='work/reports/20260926_CANDIDATE16_FIRST_BOOT/standalone'; Destination='candidate16/standalone' }
    @{ Candidate='C16'; Source='work/reports/20260926_CANDIDATE16_FIRST_BOOT/observations/run_20260926_191130'; Destination='candidate16/host-observations/run_20260926_191130' }
    @{ Candidate='C17'; Source='work/reports/20260926_CANDIDATE17_FIRST_BOOT/standalone'; Destination='candidate17/standalone/first_boot' }
    @{ Candidate='C17'; Source='work/reports/20260926_CANDIDATE17_RETEST/standalone'; Destination='candidate17/standalone/retest' }
    @{ Candidate='C17'; Source='work/reports/20260925_CANDIDATE13_STORAGE_SAFETY_AND_FIRST_FAILURE/observations/C17_revalidation/run_20260926_202822'; Destination='candidate17/host-observations/run_20260926_202822' }
    @{ Candidate='C18'; Source='work/reports/20260926_C18_NATIVE_ADRENO/standalone/run_20260926_215725'; Destination='candidate18/standalone/failed_attempt_215725' }
    @{ Candidate='C18'; Source='work/reports/20260926_C18_NATIVE_ADRENO/standalone/run_20260926_220042'; Destination='candidate18/standalone/failed_attempt_220042' }
    @{ Candidate='C18'; Source='work/reports/20260926_C18_NATIVE_ADRENO/standalone/run_20260926_221653'; Destination='candidate18/standalone/run_20260926_221653' }
    @{ Candidate='C18'; Source='work/reports/20260926_CANDIDATE18_NATIVE_ADRENO/observations/run_20260926_215459'; Destination='candidate18/host-observations/run_20260926_215459' }
)

$CredentialPatterns = @(
    @{ Type='private_key_pem'; Pattern='-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----' }
    @{ Type='github_token'; Pattern='\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b' }
    @{ Type='gitlab_token'; Pattern='\bglpat-[A-Za-z0-9_-]{20,}\b' }
    @{ Type='google_api_key'; Pattern='\bAIza[0-9A-Za-z_-]{35}\b' }
    @{ Type='openai_or_stripe_token'; Pattern='\b(?:sk-proj-|sk-live-|sk-test-|sk-ant-)\S{20,}' }
    @{ Type='slack_token'; Pattern='\bxox[baprs]-[A-Za-z0-9-]{10,}\b' }
    @{ Type='aws_access_key_id'; Pattern='\bAKIA[0-9A-Z]{16}\b' }
    @{ Type='bearer_token'; Pattern='(?i)authorization\s*:\s*bearer\s+[A-Za-z0-9._~+/=-]{20,}' }
    @{ Type='password_assignment'; Pattern='(?i)\b(?:password|passwd)\s*[:=]\s*[^ \r\n]{8,}' }
)
$ForbiddenImageNamePattern = '^(?:boot|init_boot|vendor_boot|dtbo|vbmeta|vbmeta_system|super|system|system_ext|product|vendor|odm|userdata|metadata|misc|persist|modemst\d?|efsnv|efs)(?:_[A-Za-z0-9]+)?\.(?:img|raw|bin|mbn|elf|zip|payload)$'

$ManifestRows = @()
$ExcludedRows = @()
$MissingDirectories = @()
$TotalBytes = [int64]0

foreach ($Entry in $RawDirectoryAllowlist) {
    $SourcePath = Join-Path $SourceRoot ($Entry.Source -replace '/', '\')
    if (-not (Test-Path -LiteralPath $SourcePath -PathType Container)) {
        $MissingDirectories += $Entry.Source
        continue
    }

    $SourcePath = (Resolve-Path -LiteralPath $SourcePath).Path
    $SourceItem = Get-Item -LiteralPath $SourcePath -Force
    if (($SourceItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "Refusing allowlisted reparse-point directory: $($Entry.Source)"
    }

    $AllItems = @(Get-ChildItem -LiteralPath $SourcePath -Recurse -Force)
    $ReparseItems = @($AllItems | Where-Object { ($_.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 })
    if ($ReparseItems.Count -gt 0) {
        throw "Refusing capture directory containing reparse points: $($Entry.Source)"
    }

    foreach ($File in @($AllItems | Where-Object { -not $_.PSIsContainer })) {
        $RelativeSourcePath = $File.FullName.Substring($SourcePath.Length).TrimStart('\', '/')
        $RelativeDestination = Join-Path $Entry.Destination $RelativeSourcePath
        $DestinationPath = Join-Path $EvidenceRoot $RelativeDestination
        $RelativeDisplayPath = Join-Path $Entry.Source $RelativeSourcePath

        if ($File.Name -match $ForbiddenImageNamePattern) {
            $ExcludedRows += [pscustomobject]@{Candidate=$Entry.Candidate;Source=$RelativeDisplayPath;Reason='partition_or_firmware_image'}
            continue
        }
        if ($File.Length -gt 100MB) {
            $ExcludedRows += [pscustomobject]@{Candidate=$Entry.Candidate;Source=$RelativeDisplayPath;Reason='over_100_MiB'}
            continue
        }

        $Bytes = [IO.File]::ReadAllBytes($File.FullName)
        $Ascii = [Text.Encoding]::ASCII.GetString($Bytes)
        $SecretType = $null
        foreach ($Pattern in $CredentialPatterns) {
            if ([regex]::IsMatch($Ascii, $Pattern.Pattern)) {
                $SecretType = $Pattern.Type
                break
            }
        }
        if ($SecretType) {
            $ExcludedRows += [pscustomobject]@{Candidate=$Entry.Candidate;Source=$RelativeDisplayPath;Reason="credential_pattern:$SecretType"}
            continue
        }

        New-Item -ItemType Directory -Path (Split-Path -Parent $DestinationPath) -Force | Out-Null
        [IO.File]::WriteAllBytes($DestinationPath, $Bytes)
        $SourceHash = (Get-FileHash -LiteralPath $File.FullName -Algorithm SHA256).Hash
        $DestinationHash = (Get-FileHash -LiteralPath $DestinationPath -Algorithm SHA256).Hash
        $DestinationLength = (Get-Item -LiteralPath $DestinationPath).Length
        if ($DestinationLength -ne $File.Length -or $SourceHash -ne $DestinationHash) {
            throw "Raw evidence copy mismatch: $RelativeDisplayPath"
        }

        $ManifestRows += [pscustomobject]@{
            Candidate = $Entry.Candidate
            Source = $RelativeDisplayPath.Replace('\', '/')
            PublishedPath = (Join-Path 'evidence' $RelativeDestination).Replace('\', '/')
            Bytes = $File.Length
            SHA256 = $SourceHash
        }
        $TotalBytes += $File.Length
    }
}

New-Item -ItemType Directory -Path $EvidenceRoot -Force | Out-Null
$ManifestPath = Join-Path $EvidenceRoot 'RAW_EVIDENCE_MANIFEST.csv'
$ManifestRows | Export-Csv -LiteralPath $ManifestPath -NoTypeInformation -Encoding utf8
$ExclusionsPath = Join-Path $EvidenceRoot 'RAW_EVIDENCE_EXCLUSIONS.csv'
if ($ExcludedRows.Count -gt 0) {
    $ExcludedRows | Export-Csv -LiteralPath $ExclusionsPath -NoTypeInformation -Encoding utf8
} else {
    [IO.File]::WriteAllText($ExclusionsPath, "Candidate,Source,Reason" + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
}

[pscustomobject]@{
    RawFilesCopied = $ManifestRows.Count
    RawBytesCopied = $TotalBytes
    CredentialOrPolicyExclusions = $ExcludedRows.Count
    MissingDirectories = $MissingDirectories
    Manifest = 'evidence/RAW_EVIDENCE_MANIFEST.csv'
    Exclusions = 'evidence/RAW_EVIDENCE_EXCLUSIONS.csv'
    Destination = $DestinationRoot
} | ConvertTo-Json -Depth 4
if ($MissingDirectories.Count -gt 0) {
    Write-Warning ('Allowlisted evidence directories absent: ' + ($MissingDirectories -join ', '))
}
