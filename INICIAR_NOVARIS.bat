@echo off
setlocal
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\iniciar-novaris.ps1" %*
if errorlevel 1 (
    echo.
    echo Nao foi possivel iniciar o Novaris One.
    echo Consulte backend\erro_backend.log e frontend\erro_frontend.log.
    echo.
    pause
    exit /b 1
)

timeout /t 2 /nobreak >nul
