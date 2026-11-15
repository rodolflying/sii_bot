@echo off
rem Compila SII Bot F29 con cx_Freeze y deja un .zip listo para compartir en dist\
setlocal
cd /d "%~dp0"

if not exist .venv\Scripts\python.exe (
    python -m venv .venv || exit /b 1
)
.venv\Scripts\python.exe -m pip install --quiet -r requirements.txt cx_Freeze==8.7.1 || exit /b 1

if exist build rmdir /s /q build
.venv\Scripts\cxfreeze.exe build || exit /b 1

rem selenium trae selenium-manager para Linux y macOS, en Windows sobran (~17 MB)
for %%d in (linux-arm64 linux-x86_64 macos) do rmdir /s /q "build\SII Bot F29\lib\selenium\webdriver\common\%%d"

if not exist dist mkdir dist
.venv\Scripts\python.exe -m zipfile -c "dist\SII Bot F29.zip" "build\SII Bot F29" || exit /b 1
echo.
echo Listo: dist\SII Bot F29.zip
