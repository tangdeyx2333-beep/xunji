@echo off
setlocal

:: ==========================================
:: 1. SET DEFAULT CONFIGURATION
:: ==========================================
set "BACKEND_PORT=21801"
set "FRONTEND_PORT=21800"

set "BACKEND_DIR=xunji-backup"
set "FRONTEND_DIR=xunji-frontend"
set "LOG_FILE=backend_server.log"

:: ==========================================
:: 2. PARSE ARGUMENTS (Loop through flags)
:: ==========================================
:parse_args
if "%~1"=="" goto :done_args
if /i "%~1"=="-b" (
    set "BACKEND_PORT=%~2"
    shift
    shift
    goto :parse_args
)
if /i "%~1"=="-f" (
    set "FRONTEND_PORT=%~2"
    shift
    shift
    goto :parse_args
)
:: If user types arguments without flags, ignore or handle error
shift
goto :parse_args
:done_args

:: Export port for Python
set "PORT=%BACKEND_PORT%"

echo [SYSTEM] Initializing Xunji Project...
echo --------------------------------------------------
echo [CONFIG] Backend Port  : %BACKEND_PORT%
echo [CONFIG] Frontend Port : %FRONTEND_PORT%
echo --------------------------------------------------

:: ==========================================
:: 3. CLEANUP BACKEND PORT
:: ==========================================
for /f "tokens=5" %%a in ('netstat -aon ^| find ":%BACKEND_PORT%" ^| find "LISTENING"') do (
    echo [CLEANUP] Port %BACKEND_PORT% is in use by PID %%a - Killing process...
    taskkill /f /pid %%a >nul 2>&1
)

:: ==========================================
:: 4. PREPARE & START BACKEND
:: ==========================================
echo [STEP 1/2] Checking Backend environment...
cd %BACKEND_DIR%

if not exist .venv (
    echo [ERROR] .venv folder not found! Please create it first.
    pause
    exit
)

call .venv\Scripts\activate

:: Install requirements quietly
echo [INFO] Installing dependencies...
pip install -r requirements.txt >nul 2>&1

echo [STEP 1/2] Starting Python Backend on Port %BACKEND_PORT%...
echo        - Logs: %BACKEND_DIR%\%LOG_FILE%

:: Start python in background
start /b "Xunji Backend" cmd /c "python -m app.main > %LOG_FILE% 2>&1"

:: Wait 3 seconds
timeout /t 3 /nobreak >nul

:: ==========================================
:: 5. START FRONTEND
:: ==========================================
echo [STEP 2/2] Starting Frontend on Port %FRONTEND_PORT%...
echo --------------------------------------------------
echo [TIP] Press Ctrl + C to stop the server.
echo --------------------------------------------------

cd ..\%FRONTEND_DIR%

:: Pass the port to Vite
call npm run dev -- --port %FRONTEND_PORT%

:: ==========================================
:: 6. EXIT CLEANUP
:: ==========================================
echo.
echo [SYSTEM] Frontend stopped. Shutting down Backend...

:: Clean up backend port again
for /f "tokens=5" %%a in ('netstat -aon ^| find ":%BACKEND_PORT%" ^| find "LISTENING"') do (
    taskkill /f /pid %%a >nul 2>&1
    echo [SYSTEM] Backend PID %%a stopped successfully.
)

echo [SYSTEM] Goodbye.
timeout /t 2 /nobreak >nul