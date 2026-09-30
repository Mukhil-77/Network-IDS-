@echo off
REM ==========================================
REM IDS Platform - Startup Script
REM Starts both Backend (FastAPI) and Frontend (Vite)
REM ==========================================

cd /d "C:\Users\Mukhil\Downloads\files\ids-platform"

echo.
echo ==========================================
echo   IDS Platform - Starting Application
echo ==========================================
echo.

REM Check if venv exists
if not exist "venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found!
    echo Please run: python -m venv venv && venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

echo [1/3] Activating virtual environment...
call venv\Scripts\activate.bat

echo.
echo [2/3] Starting Backend (FastAPI on port 8000)...
start "IDS Backend" cmd /k "cd /d C:\Users\Mukhil\Downloads\files\ids-platform && call venv\Scripts\activate.bat && python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"

REM Wait a moment for backend to start
timeout /t 3 /nobreak >nul

echo.
echo [3/3] Starting Frontend (Vite on port 5173)...
start "IDS Frontend" cmd /k "cd /d C:\Users\Mukhil\Downloads\files\ids-platform\frontend && npm run dev"

echo.
echo ==========================================
echo   Application Started!
echo ==========================================
echo.
echo Backend API:  http://localhost:8000
echo API Docs:     http://localhost:8000/docs
echo Frontend:     http://localhost:5173
echo.
echo Press any key to close this window (servers will keep running)...
pause