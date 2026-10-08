@echo off
REM ==========================================
REM SOC Platform - Full Stack Launcher
REM Usage: start_soc_full.bat [sqlite|postgres]
REM Default is sqlite. "pg" is an alias for postgres.
REM ==========================================

setlocal

echo ==========================================
echo  SOC Platform - AI Network Intrusion Detection
echo ==========================================
echo.

set "PROJECT_ROOT=%~dp0"
set "VENV_DIR=%PROJECT_ROOT%venv"
set "FRONTEND_DIR=%PROJECT_ROOT%frontend"
set "MODELS_DIR=%PROJECT_ROOT%models"

REM Password for the local postgres superuser, used by psql
if not defined PGPASSWORD set "PGPASSWORD=lenovo"

set "DB_MODE=sqlite"
if /i "%~1"=="postgres" set "DB_MODE=postgres"
if /i "%~1"=="pg" set "DB_MODE=postgres"

cd /d "%PROJECT_ROOT%"

echo Database mode: %DB_MODE%
echo.

REM ==========================================
echo [1/6] Checking prerequisites...
for %%C in (python npm pip) do call :check_command %%C || goto :fail
echo Prerequisites OK
echo.

REM ==========================================
echo [2/6] Setting up database...

if /i not "%DB_MODE%"=="postgres" goto :db_sqlite

where psql >nul 2>nul
if errorlevel 1 goto :pg_no_psql

psql -U postgres -w -c "SELECT 1;" >nul 2>nul
if errorlevel 1 goto :pg_no_conn

echo PostgreSQL connection OK
psql -U postgres -w -c "CREATE DATABASE ids_soc;" 2>&1 | findstr /v "already exists" | findstr /v "CREATE DATABASE"
psql -U postgres -w -c "CREATE USER ids_user WITH ENCRYPTED PASSWORD 'ids_password';" 2>&1 | findstr /v "already exists" | findstr /v "CREATE ROLE"
psql -U postgres -w -c "GRANT ALL PRIVILEGES ON DATABASE ids_soc TO ids_user;" >nul 2>nul
psql -U postgres -w -d ids_soc -c "GRANT ALL ON SCHEMA public TO ids_user;" >nul 2>nul
psql -U postgres -w -d ids_soc -c "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO ids_user;" >nul 2>nul
psql -U postgres -w -d ids_soc -c "GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO ids_user;" >nul 2>nul
psql -U postgres -w -d ids_soc -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO ids_user;" >nul 2>nul
psql -U postgres -w -d ids_soc -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO ids_user;" >nul 2>nul
echo PostgreSQL database ready
set "DB_URL=postgresql+psycopg2://ids_user:ids_password@localhost:5432/ids_soc"
goto :db_write_env

:pg_no_psql
echo WARNING: psql not found in PATH.
echo Add the PostgreSQL bin folder to PATH, for example C:\Program Files\PostgreSQL\16\bin
echo Falling back to SQLite...
goto :db_sqlite

:pg_no_conn
echo WARNING: Cannot connect to PostgreSQL as user postgres.
echo Check that the service is running and that the password is correct.
echo Falling back to SQLite...
goto :db_sqlite

:db_sqlite
set "DB_MODE=sqlite"
echo Using SQLite, file soc_platform.db
set "DB_URL=sqlite:///./soc_platform.db"

:db_write_env
if exist "%PROJECT_ROOT%.env" copy /y "%PROJECT_ROOT%.env" "%PROJECT_ROOT%.env.bak" >nul
call :write_env
echo .env written for %DB_MODE% - previous copy saved as .env.bak
echo.

REM ==========================================
echo [3/6] Setting up Python environment...

if exist "%VENV_DIR%\Scripts\python.exe" goto :venv_ok
echo Creating virtual environment...
python -m venv "%VENV_DIR%"
if errorlevel 1 goto :fail
:venv_ok

echo Upgrading pip...
"%VENV_DIR%\Scripts\python.exe" -m pip install --upgrade pip >nul 2>&1

echo Installing Python dependencies...
"%VENV_DIR%\Scripts\pip.exe" install -r "%PROJECT_ROOT%requirements.txt"
if errorlevel 1 goto :fail
echo.

REM ==========================================
echo [4/6] Running database migrations...
"%VENV_DIR%\Scripts\python.exe" -m backend.database.migrations.create_tables
if errorlevel 1 echo WARNING: Migration had issues, this may be OK if tables already exist
echo.

REM ==========================================
echo [5/6] Installing frontend dependencies...

if exist "%FRONTEND_DIR%\node_modules" goto :npm_update
echo Installing npm packages, first run may take a minute...
pushd "%FRONTEND_DIR%"
call npm install
set "NPM_ERR=%errorlevel%"
popd
if not "%NPM_ERR%"=="0" goto :fail
goto :npm_done

:npm_update
echo Node modules exist, syncing...
pushd "%FRONTEND_DIR%"
call npm install --prefer-offline --no-audit >nul 2>&1
popd

:npm_done
echo.

REM ==========================================
echo [6/6] Checking ML models...

if exist "%MODELS_DIR%\v2\lgbm_model.pkl" goto :model_v2
if exist "%MODELS_DIR%\v1\rf_model.pkl" goto :model_v1
echo WARNING: No trained models found in %MODELS_DIR%
echo You can train one later with: python backend/scripts/train_v1_model.py
goto :models_done

:model_v2
echo Found LightGBM model v2
goto :models_done

:model_v1
echo Found RandomForest model v1

:models_done
echo.
echo ==========================================
echo Setup complete! Starting servers...
echo ==========================================
echo.

REM Backend runs from project root so backend.main resolves and .env is found
echo Starting Backend, FastAPI on port 8000...
start "SOC Backend" /d "%PROJECT_ROOT%" cmd /k "venv\Scripts\activate.bat && python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000"

timeout /t 3 /nobreak >nul

echo Starting Frontend, Vite on port 5173...
start "SOC Frontend" /d "%FRONTEND_DIR%" cmd /k "npm run dev"

echo.
echo ==========================================
echo SOC Platform is starting!
echo ==========================================
echo.
echo Backend API:  http://localhost:8000
echo API Docs:     http://localhost:8000/docs
echo Frontend:     http://localhost:5173
echo Health Check: http://localhost:8000/health
echo.
echo Login: admin / ChangeMe123!   CHANGE THIS IMMEDIATELY
echo.
echo Close the server windows or press Ctrl+C in them to stop.
echo.
pause
exit /b 0

REM ==========================================
REM Subroutines - only reached through call or goto
REM ==========================================

:fail
echo.
echo Setup failed. See the messages above.
pause
exit /b 1

:check_command
where %1 >nul 2>nul
if errorlevel 1 (
    echo ERROR: %1 not found in PATH. Please install it and add it to PATH.
    exit /b 1
)
exit /b 0

:write_env
> "%PROJECT_ROOT%.env" (
echo # Core configuration
echo MODEL_PATH=%PROJECT_ROOT%models
echo API_VERSION=1.0.0
echo HOST=0.0.0.0
echo PORT=8000
echo LOG_LEVEL=INFO
echo CORS_ORIGINS=*
echo ENABLE_RATE_LIMIT=false
echo.
echo # Database
echo DATABASE_URL=%DB_URL%
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
)
exit /b 0