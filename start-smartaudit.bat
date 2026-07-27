@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "LOG_DIR=%ROOT%\logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

echo [SmartAudit] single-window start mode
echo [Root] %ROOT%

set "DEPLOY_ENV_FILE=%ROOT%\env.deploy"
set "DEPLOY_ENV_EXAMPLE=%ROOT%\env.deploy.example"
if not exist "%DEPLOY_ENV_FILE%" (
  if exist "%DEPLOY_ENV_EXAMPLE%" (
    copy /Y "%DEPLOY_ENV_EXAMPLE%" "%DEPLOY_ENV_FILE%" >nul
    echo.
    echo ============================================================
    echo [INFO] env.deploy has been created from env.deploy.example.
    echo Please edit env.deploy and fill in your real values:
    echo   - MySQL: DB_USER DB_PASS
    echo   - Auth : SMARTAUDIT_JWT_SECRET SMARTAUDIT_CALLBACK_TOKEN
    echo           SMARTAUDIT_AI_INTERNAL_TOKEN
    echo           SMARTAUDIT_CALLBACK_SIGNATURE_SECRET
    echo   - LLM  : DEEPSEEK_API_KEY DEEPSEEK_BASE_URL LLM_MODEL
    echo ============================================================
    echo.
    goto :fail
  ) else (
    echo [WARN] env.deploy not found, env.deploy.example also missing.
    echo       Will rely on system environment variables instead.
  )
)
if exist "%DEPLOY_ENV_FILE%" (
  echo [Config] loading %DEPLOY_ENV_FILE%
  for /f "usebackq eol=# tokens=1* delims==" %%A in ("%DEPLOY_ENV_FILE%") do (
    if not "%%A"=="" set "%%A=%%B"
  )
)

if "%SMARTAUDIT_JWT_SECRET%"=="" (
  echo [ERROR] Missing env SMARTAUDIT_JWT_SECRET
  goto :fail
)
if "%SMARTAUDIT_CALLBACK_TOKEN%"=="" (
  echo [ERROR] Missing env SMARTAUDIT_CALLBACK_TOKEN
  goto :fail
)
if "%SMARTAUDIT_AI_INTERNAL_TOKEN%"=="" (
  echo [ERROR] Missing env SMARTAUDIT_AI_INTERNAL_TOKEN
  goto :fail
)
if "%SMARTAUDIT_CALLBACK_SIGNATURE_SECRET%"=="" (
  echo [ERROR] Missing env SMARTAUDIT_CALLBACK_SIGNATURE_SECRET
  goto :fail
)
if "%DB_USER%"=="" (
  echo [ERROR] Missing env DB_USER
  goto :fail
)
if "%DB_PASS%"=="" (
  echo [ERROR] Missing env DB_PASS
  goto :fail
)
set "INTERNAL_API_TOKEN=%SMARTAUDIT_AI_INTERNAL_TOKEN%"
set "CALLBACK_SIGNATURE_SECRET=%SMARTAUDIT_CALLBACK_SIGNATURE_SECRET%"

if not exist "%ROOT%\backend-java\mvnw.cmd" (
  echo [ERROR] backend-java\mvnw.cmd not found.
  goto :fail
)

where npm >nul 2>nul
if errorlevel 1 (
  echo [ERROR] npm not found. Please install Node.js or add it to PATH.
  goto :fail
)

where python >nul 2>nul
if errorlevel 1 (
  REM Auto-detect Python from common install locations
  for %%D in (
    "%LOCALAPPDATA%\Programs\Python\Python312"
    "%LOCALAPPDATA%\Programs\Python\Python311"
    "%LOCALAPPDATA%\Programs\Python\Python310"
    "C:\Python312"  "C:\Python311"  "C:\Python310"
    "F:\python"  "D:\python"  "E:\python"
  ) do if exist "%%~D\python.exe" set "PATH=%%~D;!PATH!"
  where python >nul 2>nul
  if errorlevel 1 (
    echo [ERROR] python not found. Please install Python 3.10+ or add it to PATH.
    goto :fail
  )
)

if not exist "%ROOT%\backend-java\pom.xml" (
  echo [ERROR] backend-java\pom.xml not found.
  goto :fail
)

if not exist "%ROOT%\frontend\package.json" (
  echo [ERROR] frontend\package.json not found.
  goto :fail
)

if not exist "%ROOT%\ai-python\main.py" (
  echo [ERROR] ai-python\main.py not found.
  goto :fail
)

if not exist "%ROOT%\ai-python\.env" (
  if exist "%ROOT%\ai-python\.env.example" (
    copy /Y "%ROOT%\ai-python\.env.example" "%ROOT%\ai-python\.env" >nul
    echo [ERROR] ai-python\.env was created from .env.example. Fill it then rerun.
  ) else (
    echo [ERROR] ai-python\.env missing and .env.example missing.
  )
  goto :fail
)

set "AI_ACTIVATE="
if exist "%ROOT%\ai-python\venv\Scripts\activate.bat" (
  set "AI_ACTIVATE=%ROOT%\ai-python\venv\Scripts\activate.bat"
) else if exist "%ROOT%\.venv\Scripts\activate.bat" (
  set "AI_ACTIVATE=%ROOT%\.venv\Scripts\activate.bat"
)

echo [1/3] starting backend on 8080...
start "" /b cmd /c "cd /d ""%ROOT%\backend-java"" && call mvnw.cmd spring-boot:run > ""%LOG_DIR%\backend.log"" 2>&1"

echo [2/3] starting ai service on 8000...
if defined AI_ACTIVATE (
  start "" /b cmd /c "cd /d ""%ROOT%\ai-python"" && call ""%AI_ACTIVATE%"" && python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload > ""%LOG_DIR%\ai-python.log"" 2>&1"
) else (
  start "" /b cmd /c "cd /d ""%ROOT%\ai-python"" && python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload > ""%LOG_DIR%\ai-python.log"" 2>&1"
)

echo [3/3] starting frontend on 5173...
start "" /b cmd /c "cd /d ""%ROOT%\frontend"" && npm run dev -- --force > ""%LOG_DIR%\frontend.log"" 2>&1"

echo [*] waiting for ports...
call :wait_port 8080 120
if errorlevel 1 (
  echo [WARN] backend 8080 not ready in time.
) else (
  echo [OK] backend 8080 ready.
)

call :wait_port 8000 90
if errorlevel 1 (
  echo [WARN] ai 8000 not ready in time.
) else (
  echo [OK] ai 8000 ready.
)

call :wait_port 5173 90
if errorlevel 1 (
  echo [WARN] frontend 5173 not ready in time.
) else (
  echo [OK] frontend 5173 ready.
)

echo.
echo Backend : http://localhost:8080
echo AI      : http://localhost:8000
echo Frontend: http://localhost:5173
echo.
echo Logs:
echo   %LOG_DIR%\backend.log
echo   %LOG_DIR%\ai-python.log
echo   %LOG_DIR%\frontend.log
echo.
echo Press ENTER to stop all services...
pause >nul

call :kill_port 8080
call :kill_port 8000
call :kill_port 5173

echo services stop signal sent.
goto :end

:wait_port
set "WP_PORT=%~1"
set /a "WP_TIMEOUT=%~2"
:wait_port_loop
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":!WP_PORT! .*LISTENING"') do (
  exit /b 0
)
if !WP_TIMEOUT! LEQ 0 exit /b 1
set /a WP_TIMEOUT-=1
timeout /t 1 >nul
goto :wait_port_loop

:kill_port
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":%1 .*LISTENING"') do (
  taskkill /PID %%P /T /F >nul 2>&1
)
exit /b 0

:fail
echo.
echo startup precheck failed. press any key to exit...
pause >nul
goto :end

:end
endlocal
exit /b 0
