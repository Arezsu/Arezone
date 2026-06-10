@echo off
title AREZONE POS
cd /d "%~dp0"
where python >nul 2>nul && set PY=python
if not defined PY where py >nul 2>nul && set PY=py
if not defined PY (
  echo Python no encontrado.
  pause
  exit /b 1
)
%PY% "%~dp0main.py"
