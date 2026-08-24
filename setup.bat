@echo off
REM ==============================================
REM  SOC Platform - Setup and Run (desktop app)
REM
REM One-time install, then launches the SOC Platform
REM desktop app (Electron). The app starts the Python
REM security engine and the React dashboard by itself.
REM ==============================================

cd "%~dp0"

echo.
echo [1] Setting up backend (ids-platform)...
cd ids-platform

IF NOT EXIST "venv" (
    echo Creating Python virtual environment...
    python -m venv venv
)

echo Installing backend requirements...
call venv\Scripts\activate.bat
pip install -r requirements.txt

IF NOT EXIST ".env" (
    echo Creating .env file from .env.example...
    copy .env.example .env
    echo DATABASE_URL=sqlite:///./soc_platform.db >> .env
)

IF NOT EXIST "models\v1\rf_model.pkl" (
    echo Training the machine learning model...
    python scripts\train_model.py
)

cd ..

echo.
echo [2] Setting up frontend (ids-platform\frontend)...
cd ids-platform\frontend

IF NOT EXIST "node_modules" (
    echo Installing frontend dependencies...
    call npm install
)
cd ..\..

echo.
echo [3] Setting up desktop shell (desktop)...
cd desktop

IF NOT EXIST "node_modules" (
    echo Installing desktop dependencies...
    call npm install
)
cd ..

echo.
echo [4] Launching the SOC Platform desktop app...
echo     - Python security engine  : 127.0.0.1:8000
echo     - React dashboard         : inside the app window
echo     - Logs                    : desktop\.runtime\logs  (dev)
echo.
echo Note: close the app window to shut everything down.
echo.

REM Launch the Electron dev app (it spawns the engine + Vite automatically).
powershell -NoProfile -ExecutionPolicy Bypass -File "desktop\scripts\dev.ps1"