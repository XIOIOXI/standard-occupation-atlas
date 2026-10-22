param(
    # Create a new isolated database for a fresh end-to-end test.  Existing
    # isolated runs are retained and production data is never touched.
    [switch]$Fresh
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot ".venv-role-vectors\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) { throw "未找到项目 Python 环境：$python" }
$sandboxName = if ($Fresh) { "interactive-isolated-test-" + (Get-Date -Format "yyyyMMdd-HHmmss") } else { "interactive-isolated-test" }
$env:RECRUITMENT_SANDBOX_DIR = Join-Path $projectRoot ("outputs\" + $sandboxName)
$env:RECRUITMENT_API_PORT = "18088"
& $python (Join-Path $PSScriptRoot "prepare_isolated_recruitment_console.py") $env:RECRUITMENT_SANDBOX_DIR
# The API does not hot-reload Python source.  Replace only the previous
# loopback service on this dedicated test port so a rerun always uses the
# current code.  No production service or data path is involved.
$listener = Get-NetTCPConnection -LocalAddress "127.0.0.1" -LocalPort 18088 -State Listen -ErrorAction SilentlyContinue
if ($listener) { Stop-Process -Id $listener.OwningProcess -Force }
Start-Process -FilePath $python -ArgumentList (Join-Path $PSScriptRoot "serve_management_api.py") -WorkingDirectory $projectRoot -WindowStyle Hidden
Set-Location (Join-Path $projectRoot "frontend")
npm run dev
