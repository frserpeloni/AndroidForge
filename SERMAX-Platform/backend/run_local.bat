@echo off
setlocal
cd /d "%~dp0"
set "LAUNCHER=..\sermax_platform_launcher.py"

rem Operacoes de controle nao precisam instalar dependencias da API.
if "%~1"=="--stop" goto control
if "%~1"=="--status" goto control
if "%~1"=="--install-autostart" goto control
if "%~1"=="--autostart-status" goto control
if "%~1"=="--remove-autostart" goto control

if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv
  if errorlevel 1 (
    echo Falha ao criar ambiente Python.
    pause
    exit /b 1
  )
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo Falha ao instalar dependencias.
  pause
  exit /b 1
)
set "SERMAX_CORE_DIR=%~dp0..\..\SERMAX-Windows"
".venv\Scripts\python.exe" "%LAUNCHER%" %*
goto finish

:control
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" "%LAUNCHER%" %*
) else (
  where py >nul 2>&1
  if errorlevel 1 (
    python "%LAUNCHER%" %*
  ) else (
    py -3 "%LAUNCHER%" %*
  )
)

:finish
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
  echo A operacao da Plataforma encerrou com codigo %EXIT_CODE%.
  pause
)
endlocal & exit /b %EXIT_CODE%
