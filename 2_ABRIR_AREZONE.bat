@echo off
title AREZONE POS
cd /d "%~dp0"

if exist "%~dp0release\app\AREZONE.exe" (
  start "" "%~dp0release\app\AREZONE.exe"
  exit /b 0
)

where python >nul 2>nul && set PY=python
if not defined PY where py >nul 2>nul && set PY=py
if not defined PY (
  echo No hay ejecutable compilado ni Python instalado.
  echo Ejecute 3_COMPILAR_INSTALADOR.bat para generar AREZONE.exe
  pause
  exit /b 1
)

echo Abriendo AREZONE en modo desarrollo...
%PY% "%~dp0main.py"
