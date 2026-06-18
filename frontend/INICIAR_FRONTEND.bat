@echo off
setlocal
cd /d "%~dp0"
set "PYTHON_EXE=C:\Users\Davi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if not exist "%PYTHON_EXE%" (
    echo Python do Novaris nao foi encontrado. > erro_frontend.log
    echo Caminho esperado: %PYTHON_EXE% >> erro_frontend.log
    exit /b 1
)

if not exist "%~dp0dist\index.html" (
    echo O frontend compilado nao foi encontrado. > erro_frontend.log
    echo Execute a compilacao do frontend antes de iniciar. >> erro_frontend.log
    exit /b 1
)

"%PYTHON_EXE%" -m http.server 5173 --bind 0.0.0.0 --directory dist 2> erro_frontend.log
