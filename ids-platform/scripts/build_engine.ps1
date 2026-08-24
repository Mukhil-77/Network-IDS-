# Builds the packaged SOC security engine with PyInstaller.
#
# Prerequisites:
#   - venv exists with all requirements installed (see setup.bat)
#   - engine.spec is at the ids-platform root
#
# Output: dist-engine/SOC-Engine/SOC-Engine.exe (onedir bundle)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$venvPy = Join-Path $root "venv\Scripts\python.exe"

if (-not (Test-Path $venvPy)) {
    Write-Error "Backend virtualenv not found at $venvPy. Run setup.bat first (or create it: python -m venv venv)."
}

Write-Host "== SOC Engine build ==" -ForegroundColor Cyan
Write-Host "Using Python: $venvPy"

# PyInstaller must be present in the same venv that has the app's deps.
& $venvPy -m pip show pyinstaller 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing PyInstaller..."
    & $venvPy -m pip install "pyinstaller>=6.16"
    if ($LASTEXITCODE -ne 0) { Write-Error "Failed to install PyInstaller." }
}

Push-Location $root
try {
    Write-Host "Running PyInstaller (this can take several minutes)..."

    $distPath = Join-Path $root "dist-engine"
    $workPath = Join-Path $root "build\engine-spec"

    if (Test-Path $distPath) { Remove-Item $distPath -Recurse -Force }
    if (Test-Path $workPath) { Remove-Item $workPath -Recurse -Force }

    & $venvPy -m PyInstaller engine.spec --noconfirm --distpath $distPath --workpath $workPath
    if ($LASTEXITCODE -ne 0) { Write-Error "PyInstaller failed with exit code $LASTEXITCODE." }
}
finally {
    Pop-Location
}

$engineExe = Join-Path $root "dist-engine\SOC-Engine\SOC-Engine.exe"
if (-not (Test-Path $engineExe)) {
    Write-Error "Build finished but engine exe not found at $engineExe"
}

Write-Host "Engine built: $engineExe" -ForegroundColor Green