@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
if exist "release\Dolaď-IT-Alpha.exe" (
  start "Dolaď-IT Alpha" "%~dp0release\Dolaď-IT-Alpha.exe"
  exit /b 0
)
if not exist ".venv\Scripts\pythonw.exe" (
  echo Nejprve spustte Instalace.bat nebo použijte hotove EXE ze slozky release.
  pause
  exit /b 1
)
start "Dolaď-IT Alpha" ".venv\Scripts\pythonw.exe" "%~dp0launch.py"
