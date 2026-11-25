@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" exit /b 1
".venv\Scripts\python.exe" -c "import pytest,PySide6" >nul 2>&1
if errorlevel 1 (
  ".venv\Scripts\python.exe" -m pip install -r requirements-dev.txt
  if errorlevel 1 exit /b 1
)
".venv\Scripts\python.exe" tools\run_tests.py
set "RESULT=%errorlevel%"
pause
exit /b %RESULT%
