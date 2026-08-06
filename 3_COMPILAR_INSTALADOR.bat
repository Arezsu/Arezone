@echo off
title AREZONE - Compilar
cd /d "%~dp0"

echo Cerrando AREZONE si esta abierto...
taskkill /IM AREZONE.exe /F >nul 2>nul
timeout /t 1 /nobreak >nul

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
echo Archivos listos:
echo   %~dp0release\app\AREZONE.exe
echo   %~dp0release\instalador\Instalador_AREZONE.exe
echo.
pause
