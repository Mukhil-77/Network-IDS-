@echo off
REM ==============================================
REM  SOC Platform - Cache Cleanup Script
REM  Removes all cache, build artifacts, and temporary files
REM ==============================================

@echo off
echo Cleaning SOC Platform cache and build artifacts...

REM --- Python cache ---
echo [1/6] Cleaning Python cache (__pycache__, .pyc files)...
if exist backend\__pycache__ rmdir /s /q backend\__pycache__ 2>nul
for /d /r backend %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d" 2>nul
del /s /q backend\*.pyc 2>nul
del /s /q backend\*.pyo 2>nul
del /s /q backend\*.pyd 2>nul

REM --- Pytest cache ---
echo [2/6] Cleaning pytest cache...
if exist backend\.pytest_cache rmdir /s /q backend\.pytest_cache 2>nul
if exist backend\.coverage rmdir /s /q backend\.coverage 2>nul
del /s /q backend\.coverage.* 2>nul

REM --- Mypy cache ---
echo [3/6] Cleaning mypy cache...
if exist backend\.mypy_cache rmdir /s /q backend\.mypy_cache 2>nul

REM --- Frontend build artifacts ---
echo [4/6] Cleaning frontend build artifacts...
if exist frontend\dist rmdir /s /q frontend\dist 2>nul
if exist frontend\node_modules\.cache rmdir /s /q frontend\node_modules\.cache 2>nul
if exist frontend\.vite rmdir /s /q frontend\.vite 2>nul
if exist frontend\.eslintcache del frontend\.eslintcache 2>nul

REM --- Desktop build artifacts ---
echo [5/6] Cleaning desktop build artifacts...
if exist desktop\dist rmdir /s /q desktop\dist 2>nul
if exist desktop\build rmdir /s /q desktop\build 2>nul
if exist desktop\release rmdir /s /q desktop\release 2>nul

REM --- Python virtual environment (optional) ---
echo [6/6] Skipping virtual environment (run 'rmdir /s /q backend\venv' manually if needed)...

echo.
echo ==============================================
echo Cache cleanup complete!
echo ==============================================
echo.
echo Note: The following were NOT removed (run manually if needed):
echo   - backend\venv (Python virtual environment)
echo   - frontend\node_modules (npm dependencies)
echo   - desktop\node_modules (npm dependencies)
echo   - Any .env or .env.* files (environment configs)
echo   - desktop\resources (app resources)
echo.
pause