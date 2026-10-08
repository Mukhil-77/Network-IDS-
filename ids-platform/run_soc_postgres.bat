@echo off
REM ==========================================
REM SOC Platform - PostgreSQL Full Stack Launcher
REM Run as Administrator
REM ==========================================

echo ==========================================
echo  SOC Platform - PostgreSQL Full Stack
echo ==========================================
echo.

set "PROJECT_ROOT=%~dp0"
set "FRONTEND_DIR=%PROJECT_ROOT%frontend"
set PGPASSWORD=lenovo

cd /d "%PROJECT_ROOT%"

echo [1/5] Checking PostgreSQL...

where psql >nul 2>nul
if errorlevel 1 goto :no_psql

psql -U postgres -w -c "SELECT 1;" >nul 2>nul
if errorlevel 1 goto :no_connect

echo PostgreSQL connection OK
goto :setup_db

:no_psql
echo ERROR: psql not found in PATH
echo Add the PostgreSQL bin folder to PATH, for example C:\Program Files\PostgreSQL\16\bin
pause
exit /b 1

:no_connect
echo ERROR: Cannot connect to PostgreSQL as user postgres.
echo Check that the PostgreSQL service is running and that the password is correct.
echo Manual test: psql -U postgres -c "SELECT 1;"
pause
exit /b 1

:setup_db
echo.
echo [2/5] Setting up database...
echo Creating database ids_soc...
psql -U postgres -w -c "CREATE DATABASE ids_soc;" 2>&1 | findstr /v "already exists" | findstr /v "CREATE DATABASE"

echo Creating user ids_user...
psql -U postgres -w -c "CREATE USER ids_user WITH ENCRYPTED PASSWORD 'ids_password';" 2>&1 | findstr /v "already exists" | findstr /v "CREATE ROLE"

echo Granting privileges...
psql -U postgres -w -c "GRANT ALL PRIVILEGES ON DATABASE ids_soc TO ids_user;" >nul 2>nul
psql -U postgres -w -d ids_soc -c "GRANT ALL ON SCHEMA public TO ids_user;" >nul 2>nul
psql -U postgres -w -d ids_soc -c "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO ids_user;" >nul 2>nul
psql -U postgres -w -d ids_soc -c "GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO ids_user;" >nul 2>nul
psql -U postgres -w -d ids_soc -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO ids_user;" >nul 2>nul
psql -U postgres -w -d ids_soc -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO ids_user;" >nul 2>nul
echo Database ready

echo.
echo [3/5] Updating .env configuration...
(
echo # PostgreSQL Configuration
echo MODEL_PATH=%PROJECT_ROOT%models
echo API_VERSION=1.0.0
echo HOST=0.0.0.0
echo PORT=8000
echo LOG_LEVEL=INFO
echo CORS_ORIGINS=*
echo ENABLE_RATE_LIMIT=false
echo.
echo # PostgreSQL
echo DATABASE_URL=postgresql+psycopg2://ids_user:ids_password@localhost:5432/ids_soc
echo.
echo # Security - CHANGE IN PRODUCTION
echo JWT_SECRET_KEY=dev-only-insecure-secret-change-me
echo JWT_ALGORITHM=HS256
echo ACCESS_TOKEN_EXPIRE_MINUTES=15
echo REFRESH_TOKEN_EXPIRE_DAYS=7
echo.
echo # Default admin - CHANGE IMMEDIATELY
echo DEFAULT_ADMIN_USERNAME=admin
echo DEFAULT_ADMIN_EMAIL=admin@example.com
echo DEFAULT_ADMIN_PASSWORD=ChangeMe123!
echo.
echo # Optional notification channels
echo SMTP_HOST=
echo SMTP_PORT=587
echo SMTP_USERNAME=
echo SMTP_PASSWORD=
echo ALERT_EMAIL_FROM=
echo ALERT_EMAIL_TO=
echo.
echo TELEGRAM_BOT_TOKEN=
echo TELEGRAM_CHAT_ID=
echo.
echo RESPONSE_WEBHOOK_URL=
) > "%PROJECT_ROOT%.env"
echo .env updated

echo.
echo [4/5] Setting up Python environment...
if not exist "%PROJECT_ROOT%venv" (
    echo Creating virtual environment...
    python -m venv venv
)

echo Upgrading pip...
venv\Scripts\python.exe -m pip install --upgrade pip >nul 2>&1

echo Installing Python dependencies...
venv\Scripts\pip.exe install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install Python dependencies
    pause
    exit /b 1
)

echo Running database migrations...
venv\Scripts\python.exe -m backend.database.migrations.create_tables
if errorlevel 1 echo WARNING: Migration had issues, this may be OK if tables already exist

echo.
echo [5/5] Installing frontend dependencies...
if not exist "%FRONTEND_DIR%\node_modules" (
    echo Installing npm packages, first run may take a minute...
    pushd "%FRONTEND_DIR%"
    call npm install
    set NPM_ERR=%errorlevel%
    popd
    if not "%NPM_ERR%"=="0" (
        echo ERROR: npm install failed
        pause
        exit /b 1
    )
)

echo.
echo ==========================================
echo Starting servers...
echo ==========================================

start "SOC Backend" /d "%PROJECT_ROOT%" cmd /k "venv\Scripts\activate.bat && python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000"
timeout /t 3 /nobreak >nul
start "SOC Frontend" /d "%FRONTEND_DIR%" cmd /k "npm run dev"

echo.
echo Backend:  http://localhost:8000
echo API Docs: http://localhost:8000/docs
echo Frontend: http://localhost:5173
echo.
echo Login: admin / ChangeMe123!
echo.
pause