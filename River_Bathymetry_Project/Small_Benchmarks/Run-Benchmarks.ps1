param(
    [string]$Python = 'python',
    [string]$RuntimeDir = '',
    [ValidateSet('smoke','channel','sill','depth')][string]$Suite = 'smoke',
    [ValidateSet('cpu','cuda')][string]$Device = 'cpu',
    [string]$OutputDir = '',
    [int]$TimeoutSeconds = 900,
    [int]$ChannelSeconds = 3600,
    [switch]$PrepareOnly,
    [switch]$RetryFailed
)
$ErrorActionPreference = 'Stop'
$scriptFile = Join-Path $PSScriptRoot 'run_benchmarks.py'
$repoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
if (-not $OutputDir) {
    $OutputDir = Join-Path $PSScriptRoot ('results\run_' + (Get-Date -Format 'yyyyMMdd_HHmmss_fff'))
}
$OutputDir = [System.IO.Path]::GetFullPath($OutputDir)
if (-not (Test-Path -LiteralPath (Join-Path $OutputDir 'manifest.json'))) {
    & $Python -X utf8 $scriptFile prepare --out $OutputDir --channel-seconds $ChannelSeconds
    if ($LASTEXITCODE -ne 0) { throw 'Prepare failed. Read the error above.' }
}
Write-Host "[Benchmark] OutputDir: $OutputDir"
if ($PrepareOnly) { return }
if (-not $RuntimeDir) {
    $RuntimeDir = Join-Path $repoRoot 'V48_runs\20261004_runtime_fix_r1'
}
& $Python -X utf8 $scriptFile doctor --runtime $RuntimeDir
if ($LASTEXITCODE -ne 0) { throw 'Runtime not found. Specify -RuntimeDir pointing to the actual R1 runtime.' }
$runArgs = @('-X','utf8',$scriptFile,'run','--out',$OutputDir,'--runtime',$RuntimeDir,
             '--suite',$Suite,'--device',$Device,'--timeout',"$TimeoutSeconds")
if ($RetryFailed) { $runArgs += '--retry-failed' }
& $Python @runArgs
$resultCode = $LASTEXITCODE
& $Python -X utf8 $scriptFile bundle --out $OutputDir
if ($LASTEXITCODE -ne 0) { throw 'Creating report bundle failed.' }
if ($resultCode -ne 0) { throw "Suite $Suite did not pass. See $OutputDir\reports and case console.log files." }
Write-Host "[Benchmark] $Suite PASS. Continue using the SAME -OutputDir and -Device."
