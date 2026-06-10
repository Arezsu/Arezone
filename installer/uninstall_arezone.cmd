@echo off
setlocal

set "APP_DIR=%ProgramFiles%\ArezOne"

taskkill /IM AREZONE.exe /F >nul 2>nul
if exist "%APP_DIR%" rmdir /S /Q "%APP_DIR%"

powershell -NoProfile -ExecutionPolicy Bypass -Command "$desktop=[Environment]::GetFolderPath('Desktop'); $start=[Environment]::GetFolderPath('Programs'); Remove-Item -Force -ErrorAction SilentlyContinue (Join-Path $desktop 'AREZONE.lnk'); Remove-Item -Recurse -Force -ErrorAction SilentlyContinue (Join-Path $start 'AREZONE')"

echo AREZONE desinstalado.
endlocal
