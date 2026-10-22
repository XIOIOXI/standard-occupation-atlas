$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot ".venv-role-vectors\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) { throw "未找到项目 Python 环境：$python" }
$env:RECRUITMENT_API_PORT = "18087"

# The management API listens only on localhost.  API keys are loaded by the
# backend process from its environment/.env and never reach browser code.
Start-Process -FilePath $python -ArgumentList (Join-Path $PSScriptRoot "serve_management_api.py") -WorkingDirectory $projectRoot -WindowStyle Hidden
Set-Location (Join-Path $projectRoot "frontend")
npm run dev
