[CmdletBinding()]
param(
    [string]$Python = "python",
    [ValidateSet("cuda", "cpu")][string]$Device = "cuda",
    [ValidateSet("all", "smoke", "closed", "channel", "sill", "depth", "ablation")][string]$Suite = "all",
    [string]$OutputDir = "",
    [ValidateRange(1, 3600)][int]$TimeoutSeconds = 900,
    [ValidateRange(300, 3600)][int]$ChannelSeconds = 3600,
    [switch]$PrepareOnly,
    [switch]$RetryFailed
)
$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "../..")).Path
$runtime = Join-Path $projectRoot "V48_runs/20261118_runtime_fix_r3"
$runner = Join-Path $PSScriptRoot "run_benchmarks.py"
if (-not $OutputDir) {
    $OutputDir = Join-Path $PSScriptRoot ("results/R3_{0}_{1}" -f $Device, (Get-Date -Format "yyyyMMdd_HHmmss_fff"))
}
$OutputDir = [System.IO.Path]::GetFullPath($OutputDir)
Write-Host "[R3] Small synthetic cases only; no provincial input or production launchers."
Write-Host "[R3] Output: $OutputDir"
if (-not (Test-Path -LiteralPath (Join-Path $OutputDir "manifest.json"))) {
    & $Python -X utf8 $runner prepare --out $OutputDir --channel-seconds $ChannelSeconds
    if ($LASTEXITCODE -ne 0) { throw "[R3] Preparation failed; use a fresh output folder after fixing the cause." }
}
if ($PrepareOnly) {
    Write-Host "[R3] Prepared only; no solver run."
    return
}
$failed = $false
try {
    & $Python -X utf8 $runner doctor --runtime $runtime
    if ($LASTEXITCODE -ne 0) { throw "Runtime or dependency check failed" }
    $suites = if ($Suite -eq "all") { @("smoke", "closed", "channel", "sill", "depth", "ablation") } else { @($Suite) }
    foreach ($part in $suites) {
        $arguments = @("-X", "utf8", $runner, "run", "--out", $OutputDir,
                       "--runtime", $runtime, "--suite", $part, "--device", $Device,
                       "--timeout", "$TimeoutSeconds")
        if ($RetryFailed) { $arguments += "--retry-failed" }
        & $Python @arguments
        if ($LASTEXITCODE -ne 0) { throw "Suite $part failed; remaining suites were not started" }
    }
}
catch {
    $failed = $true
    Write-Host "[R3] STOP: $($_.Exception.Message)"
}
finally {
    & $Python -X utf8 $runner bundle --out $OutputDir
    if ($LASTEXITCODE -ne 0) { $failed = $true }
}
if ($failed) { throw "[R3] Checks failed. Send the report ZIP and retain this output folder." }
Write-Host "[R3] Requested suites passed. Send benchmark_report_*.zip; retain NetCDF locally."
