@echo off
setlocal
cd /d "%~dp0"
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
"..\.venv\Scripts\python.exe" "..\sermax_platform_launcher.py"
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
  echo A Plataforma encerrou com codigo %EXIT_CODE%.
  pause
)
endlocal & exit /b %EXIT_CODE%
