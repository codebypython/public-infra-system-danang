@echo off
REM =====================================================================
REM Đà Nẵng Public Infrastructure System — One-command launcher
REM Wrapper around scripts\start.ps1 for cmd.exe / Explorer double-click
REM =====================================================================
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start.ps1" %*
endlocal
