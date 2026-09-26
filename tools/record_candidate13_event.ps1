[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string]$RunDir,
    [Parameter(Mandatory = $true)] [ValidateNotNullOrEmpty()] [string]$Message
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RunPath = (Resolve-Path -LiteralPath $RunDir).Path
if (-not (Test-Path -LiteralPath (Join-Path $RunPath 'run_metadata.json') -PathType Leaf)) {
    throw "Not a Candidate 13 observer run directory: $RunPath"
}
$EventPath = Join-Path $RunPath 'operator_actions.csv'
if (-not (Test-Path -LiteralPath $EventPath -PathType Leaf)) {
    'host_utc,event,message' | Set-Content -LiteralPath $EventPath -Encoding utf8
}
$Utc = [DateTimeOffset]::UtcNow.ToString('o')
$Escape = { param([string]$Value) '"' + $Value.Replace('"', '""') + '"' }
$Line = ((& $Escape $Utc) + ',"operator_action",' + (& $Escape $Message))
Add-Content -LiteralPath $EventPath -Value $Line -Encoding utf8
Write-Host "[RECORDED] $Utc $Message"
