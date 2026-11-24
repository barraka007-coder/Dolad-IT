@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto dependencies
py -3 -m venv .venv
if errorlevel 1 goto failed
:dependencies
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
echo.
echo Instalace dokoncena. Spustte Spustit_Voice_Studio.bat.
pause
exit /b 0
:failed
echo.
echo Instalace selhala. Nainstalujte Python 3.11 nebo novejsi z python.org.
echo Prvni instalace knihoven vyzaduje internet. Podrobnosti jsou vyse.
pause
exit /b 1
