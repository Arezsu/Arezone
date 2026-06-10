@echo off
title AREZONE - Compilar
cd /d "%~dp0"
echo Compilando version actual de AREZONE...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\build_release.ps1"
if errorlevel 1 (
  echo.
  echo La compilacion fallo. Revise el mensaje anterior.
  pause
  exit /b 1
)
echo.
echo Compilacion finalizada.
echo.
pause
