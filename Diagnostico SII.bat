@echo off
chcp 65001 > nul
title Diagnostico SII - solo lectura
cd /d "%~dp0"
python diagnostico.py
echo.
echo Listo. Revisa el indice.md de la carpeta diagnostico
pause
