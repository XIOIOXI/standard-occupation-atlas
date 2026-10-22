param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Source,
    [ValidateSet("cached", "model")]
    [string]$MappingMode = "cached",
    [ValidateRange(0.01, 1000)]
    [double]$BudgetUsd = 0.20,
    [string]$RetryFailed
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot ".venv-role-vectors\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "Python environment was not found at $python. Create the project environment before running an update."
}
if (-not (Test-Path -LiteralPath $Source)) {
    throw "The supplied CSV/XLSX file does not exist: $Source"
}

$env:PYTHONPATH = Join-Path $projectRoot "backend"
$arguments = @((Join-Path $PSScriptRoot "process_recruitment_update.py"), $Source, "--mapping-mode", $MappingMode, "--budget-usd", $BudgetUsd)
if ($RetryFailed) {
    $arguments += @("--retry-failed", $RetryFailed)
}
& $python @arguments
exit $LASTEXITCODE
