# Starts the SOC Platform in development mode:
#   - backend engine via the ids-platform venv (desktop_entry.py)
#   - Vite dev server for the React frontend
#   - Electron window pointing at the Vite server
# All process management lives in src/main.cjs; this script just runs Electron.
#
# Usage:  powershell -ExecutionPolicy Bypass -File scripts\dev.ps1

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $PSScriptRoot
Set-Location $here

$venvPy = Join-Path $here "..\ids-platform\venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    Write-Host "Backend venv not found at $venvPy" -ForegroundColor Yellow
    Write-Host "Run setup.bat first, or create it manually:" -ForegroundColor Yellow
    Write-Host "  python -m venv ..\ids-platform\venv" -ForegroundColor Yellow
    Write-Host "  ..\ids-platform\venv\Scripts\pip install -r ..\ids-platform\requirements.txt" -ForegroundColor Yellow
    exit 1
}

if (-not (Test-Path "node_modules")) {
    Write-Host "Installing desktop app dependencies (electron)..." -ForegroundColor Cyan
    & npm.cmd install
    if ($LASTEXITCODE -ne 0) { exit 1 }
}

Write-Host "Starting SOC Platform (dev)..." -ForegroundColor Cyan
Write-Host "  Backend engine : venv python + desktop_entry.py (127.0.0.1:8000)"
Write-Host "  Frontend       : Vite dev server (localhost:5173)"
& npm.cmd run dev