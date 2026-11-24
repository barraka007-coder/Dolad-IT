@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
if exist "release\Dolaď-IT.exe" (
  start "Dolaď-IT" "%~dp0release\Dolaď-IT.exe"
  exit /b 0
)
if not exist ".venv\Scripts\pythonw.exe" (
  echo Nejprve spustte Instalace.bat.
  pause
  exit /b 1
)
start "Dolaď-IT" ".venv\Scripts\pythonw.exe" "%~dp0launch.py"
