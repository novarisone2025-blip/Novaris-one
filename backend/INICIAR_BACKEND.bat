@echo off
setlocal
cd /d "%~dp0"
set "UVICORN_EXE=%~dp0.deps\bin\uvicorn.exe"
set "PYTHONPATH=%~dp0;%~dp0.deps"

if not exist "%UVICORN_EXE%" (
    echo Uvicorn do Novaris nao foi encontrado. > erro_backend.log
    echo Caminho esperado: %UVICORN_EXE% >> erro_backend.log
    exit /b 1
)

"%UVICORN_EXE%" app.main:app --host 0.0.0.0 --port 8001 2> erro_backend.log
