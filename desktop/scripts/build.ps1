# Full production build for SOC Platform Windows desktop app.
#
# Steps:
#   1. Build the Python security engine   -> ids-platform\dist-engine\SOC-Engine\SOC-Engine.exe
#   2. Build the React frontend           -> ids-platform\frontend\dist
#   3. Package the Electron desktop app   -> desktop\release\SOC-Platform-Setup-<ver>.exe
#
# Usage:  powershell -ExecutionPolicy Bypass -File scripts\build.ps1
# Prereqs: Node.js, Python 3.14, ids-platform\venv created and pip-installed.

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $PSScriptRoot
Set-Location $here

$idsRoot = Join-Path $here "..\ids-platform"

Write-Host "========== SOC Platform build ==========" -ForegroundColor Cyan

# ---- 1. Backend engine (PyInstaller) ---------------------------------
Write-Host "[1/3] Building Python security engine..." -ForegroundColor Cyan
Push-Location $idsRoot
try {
    $venvPy = Join-Path $idsRoot "venv\Scripts\python.exe"
    if (-not (Test-Path $venvPy)) {
        Write-Error "Backend venv not found at $venvPy. Run setup.bat first."
    }
    & $venvPy -m pip show pyinstaller 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        & $venvPy -m pip install "pyinstaller>=6.16"
    }
    & $venvPy -m PyInstaller engine.spec --noconfirm `
        --distpath (Join-Path $idsRoot "dist-engine") `
        --workpath (Join-Path $idsRoot "build\engine-spec")
    if ($LASTEXITCODE -ne 0) { Write-Error "PyInstaller failed." }
}
finally { Pop-Location }

$engineExe = Join-Path $idsRoot "dist-engine\SOC-Engine\SOC-Engine.exe"
if (-not (Test-Path $engineExe)) { Write-Error "Engine build missing: $engineExe" }

# ---- 2. Frontend (Vite production build) ------------------------------
Write-Host "[2/3] Building React frontend..." -ForegroundColor Cyan
Push-Location (Join-Path $idsRoot "frontend")
try {
    if (-not (Test-Path "node_modules")) {
        & npm.cmd install
        if ($LASTEXITCODE -ne 0) { Write-Error "npm install failed." }
    }
    & npm.cmd run build
    if ($LASTEXITCODE -ne 0) { Write-Error "Frontend build failed." }
}
finally { Pop-Location }

$frontDist = Join-Path $idsRoot "frontend\dist"
if (-not (Test-Path (Join-Path $frontDist "index.html"))) {
    Write-Error "Frontend build missing index.html at $frontDist"
}

# ---- 3. Desktop installer (electron-builder) --------------------------
Write-Host "[3/3] Packaging desktop app..." -ForegroundColor Cyan
if (-not (Test-Path "node_modules\electron")) {
    & npm.cmd install
    if ($LASTEXITCODE -ne 0) { Write-Error "Desktop deps install failed." }
}
& npm.cmd run dist
if ($LASTEXITCODE -ne 0) { Write-Error "electron-builder failed." }

Write-Host ""
Write-Host "========== Build complete ==========" -ForegroundColor Green
Write-Host "Installer: desktop\release\SOC-Platform-Setup-*.exe"
Write-Host "Engine:    $engineExe"
Write-Host "Frontend:  $frontDist"