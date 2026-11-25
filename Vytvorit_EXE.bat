@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Nejprve spustte Instalace.bat.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
  ".venv\Scripts\python.exe" -m pip install "pyinstaller>=6.11,<7"
  if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" tools\build_alpha.py
if errorlevel 1 goto failed
echo Hotovo: release\Dolaď-IT-Alpha.exe
echo FFmpeg a FFprobe jsou vlozeny do EXE. Pracovni soubory sestaveni se automaticky odstrani.
pause
exit /b 0
:failed
echo Sestaveni selhalo. Podrobnosti jsou vyse.
pause
exit /b 1
