@echo off
echo ==============================================
echo  SOC Dashboard Project Setup and Run Script
echo ==============================================

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
echo [3] Starting the services...

echo Starting backend server...
start cmd /k "title Backend Server && cd ids-platform && call venv\Scripts\activate.bat && python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"

echo Starting frontend server...
start cmd /k "title Frontend Server && cd ids-platform\frontend && npm run dev"

echo.
echo Done! The services are starting in separate windows.
pause
