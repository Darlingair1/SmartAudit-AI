@echo off
setlocal EnableExtensions

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

echo [1/2] Java unit tests...
cd /d "%ROOT%\backend-java"
mvn -q test
if errorlevel 1 (
  echo [FAIL] Java unit tests failed.
  exit /b 1
)

echo [2/2] Python unit tests...
cd /d "%ROOT%\ai-python"
if exist ".\venv\Scripts\python.exe" (
  .\venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
) else (
  python -m unittest discover -s tests -p "test_*.py"
)
if errorlevel 1 (
  echo [FAIL] Python unit tests failed.
  exit /b 1
)

echo [PASS] Baseline tests all passed.
exit /b 0
