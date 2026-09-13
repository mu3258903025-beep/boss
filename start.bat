@echo off
setlocal
chcp 65001 >nul
set PY=
if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" set PY=%LOCALAPPDATA%\Programs\Python\Python313\python.exe
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set PY=%LOCALAPPDATA%\Programs\Python\Python311\python.exe
if not defined PY if exist "C:\Program Files\Python313\python.exe" set PY=C:\Program Files\Python313\python.exe
if not defined PY if exist "C:\Python313\python.exe" set PY=C:\Python313\python.exe
if defined PY goto RUN
python --version >nul 2>&1
if not errorlevel 1 set PY=python
if defined PY goto RUN
py -3 --version >nul 2>&1
if not errorlevel 1 set PY=py -3
if defined PY goto RUN
echo.
echo [ERROR] Python not found. Install from https://www.python.org/downloads/
echo Check "Add python.exe to PATH" during install.
echo.
pause
exit /b 1

:RUN
set SCRAPER=D:\BossJob\boss_scraper\scripts\boss_cdp_raw.py
echo.
echo Python: %PY%
echo ========================================

rem ----- 1/4 collector deps (websocket-client, requests) -----
"%PY%" -c "import websocket, requests" >nul 2>&1
if not errorlevel 1 goto HAVE_DEPS
echo [1/4] Installing collector deps (websocket-client, requests)...
"%PY%" -m pip install websocket-client requests
if errorlevel 1 goto FAIL
goto AFTER_DEPS
:HAVE_DEPS
echo [1/4] Collector deps OK.
:AFTER_DEPS

rem ----- 2/4 BOSS dedicated Chrome + one-time login -----
"%PY%" "%SCRAPER%" --check >nul 2>&1
if not errorlevel 1 goto SKIP_LOGIN
echo [2/4] First run: launching BOSS dedicated Chrome, please log in there...
"%PY%" "%SCRAPER%" --setup-chrome
goto AFTER_LOGIN
:SKIP_LOGIN
echo [2/4] BOSS login detected, skip.
:AFTER_LOGIN

rem ----- 3/4 start local LLM -----
echo [3/4] Starting local model service...
"%PY%" "D:\Ollama\start_ollama.py" --no-chat

rem ----- 4/4 start web tool -----
echo [4/4] Starting web tool...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr "127.0.0.1:8090" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1
start "BOSS Job Tool" /MIN "%PY%" "D:\BossJob\boss_job.py"
timeout /t 3 >nul
start "" http://localhost:8090

echo.
echo Done. Tool running at http://localhost:8090
echo Close the "BOSS Job Tool" window to stop.
echo.
pause
exit /b 0

:FAIL
echo.
echo [FAILED] Setup failed (maybe network issue). Please retry.
echo.
pause
exit /b 1
