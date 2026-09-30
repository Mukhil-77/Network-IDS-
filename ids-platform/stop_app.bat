@echo off
REM ==========================================
REM IDS Platform - Stop Script
REM Stops Backend and Frontend servers
REM ==========================================

echo.
echo ==========================================
echo   IDS Platform - Stopping Application
echo ==========================================
echo.

echo Stopping Backend (uvicorn)...
taskkill /F /FI "WINDOWTITLE eq IDS Backend" >nul 2>&1
taskkill /F /IM uvicorn.exe >nul 2>&1

echo Stopping Frontend (Vite)...
taskkill /F /FI "WINDOWTITLE eq IDS Frontend" >nul 2>&1
taskkill /F /IM node.exe >nul 2>&1

echo.
echo All servers stopped.
pause