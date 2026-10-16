@echo off
chcp 65001 >nul
if "%~1"=="" (
  echo Usage: apply_main.cmd "original.iso"
  pause
  exit /b 1
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0apply_main.ps1" "%~f1"
set "RESULT=%ERRORLEVEL%"
pause
exit /b %RESULT%
