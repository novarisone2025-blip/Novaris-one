@echo off
setlocal
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\parar-novaris.ps1"
timeout /t 2 /nobreak >nul
