@echo off
rem ============================================================================
rem  fadir - console starter
rem
rem  Double-click to run the dashboard in a visible console window. Handles
rem  first-run setup automatically: virtualenv, dependencies, frontend bundle
rem  and database bootstrap. Closing this window stops the server.
rem
rem  For a windowless version that lives in the system tray, use
rem  fadir-tray.vbs instead.
rem ============================================================================

setlocal EnableDelayedExpansion
cd /d "%~dp0"

set "PORT=8000"
set "URL=http://127.0.0.1:%PORT%"
set "PY=.venv\Scripts\python.exe"

title fadir - portfolio dashboard

echo.
echo   fadir - multi-currency portfolio PnL tracker
echo   -------------------------------------------
echo.

rem -- already running? just open the browser --------------------------------
netstat -ano | findstr /r /c:":%PORT% .*LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo   Server is already running on port %PORT%.
    echo   Opening %URL%
    start "" "%URL%"
    echo.
    timeout /t 3 >nul
    exit /b 0
)

rem -- python present? --------------------------------------------------------
where python >nul 2>&1
if errorlevel 1 (
    echo   [X] Python was not found on PATH.
    echo       Install Python 3.11+ from python.org and tick "Add to PATH".
    goto :fail
)

rem -- virtualenv -------------------------------------------------------------
if not exist "%PY%" (
    echo   [1/4] Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 goto :fail
    echo         Installing dependencies ^(this takes a minute^)...
    "%PY%" -m pip install --upgrade pip --quiet
    "%PY%" -m pip install -r requirements-dev.txt --quiet
    if errorlevel 1 goto :fail
) else (
    echo   [1/4] Virtual environment ready.
)

rem -- frontend bundle --------------------------------------------------------
if not exist "frontend\dist\index.html" (
    where npm >nul 2>&1
    if errorlevel 1 (
        echo   [2/4] npm not found - starting in API-only mode.
        echo         Install Node.js to get the dashboard UI.
    ) else (
        echo   [2/4] Building the dashboard...
        pushd frontend
        if not exist "node_modules" call npm install --silent
        call npm run build
        popd
    )
) else (
    echo   [2/4] Dashboard bundle ready.
)

rem -- database ---------------------------------------------------------------
if not exist "fadir.db" (
    echo   [3/4] First run - creating database and fetching market data...
    echo.
    "%PY%" scripts\bootstrap.py
    if errorlevel 1 (
        echo.
        echo   [!] Bootstrap reported problems. Starting anyway - check the
        echo       dashboard for any positions flagged as missing data.
    )
    echo.
) else (
    echo   [3/4] Database ready.
)

rem -- open the browser once the port is actually accepting -------------------
start "" /b powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "for($i=0;$i -lt 40;$i++){try{$c=New-Object Net.Sockets.TcpClient;$c.Connect('127.0.0.1',%PORT%);$c.Close();Start-Process '%URL%';break}catch{Start-Sleep -Milliseconds 400}}"

echo   [4/4] Starting server on %URL%
echo.
echo   ------------------------------------------------------------------
echo    Your browser will open automatically in a moment.
echo    Press Ctrl+C or close this window to stop the server.
echo   ------------------------------------------------------------------
echo.

"%PY%" -m uvicorn app.main:app --host 127.0.0.1 --port %PORT%

echo.
echo   Server stopped.
timeout /t 3 >nul
exit /b 0

:fail
echo.
echo   [X] Setup failed. See the messages above.
echo.
pause
exit /b 1
