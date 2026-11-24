@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Nejprve spustte Instalace.bat.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m pip install "pyinstaller>=6.11,<7"
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --distpath release VoiceStudio.spec
if errorlevel 1 goto failed
echo Hotovo: release\Dolaď-IT.exe
echo FFmpeg je vlozen do EXE, pokud je v tools\ffmpeg pri sestaveni.
pause
exit /b 0
:failed
echo Sestaveni selhalo. Podrobnosti jsou vyse.
pause
exit /b 1
