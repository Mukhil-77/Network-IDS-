@echo off
REM ==========================================
REM SOC Platform - Quick Start (assumes setup is done)
REM ==========================================

set "PROJECT_ROOT=%~dp0"
set "FRONTEND_DIR=%PROJECT_ROOT%frontend"

if not exist "%PROJECT_ROOT%venv\Scripts\activate.bat" (
    echo ERROR: venv not found. Run start_soc.bat first to do the full setup.
    pause
    exit /b 1
)

echo Starting SOC Platform...
echo.

REM Backend: run from project root so backend.main resolves and .env is found
start "SOC Backend" /d "%PROJECT_ROOT%" cmd /k "venv\Scripts\activate.bat && python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000"

REM Give the backend a moment to start
timeout /t 3 /nobreak >nul

REM Frontend
start "SOC Frontend" /d "%FRONTEND_DIR%" cmd /k "npm run dev"

echo.
echo Backend:  http://localhost:8000
echo API Docs: http://localhost:8000/docs
echo Frontend: http://localhost:5173
echo.
echo Login: admin / ChangeMe123!
echo.
echo Close the server windows or press Ctrl+C in them to stop.
echo.
pause