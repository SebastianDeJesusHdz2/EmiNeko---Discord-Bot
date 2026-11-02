@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  python -m venv .venv
  if errorlevel 1 goto fail
)
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto fail
if not exist ".env" copy ".env.example" ".env" >nul
.venv\Scripts\python.exe preparar_playnite.py
if errorlevel 1 goto fail
.venv\Scripts\python.exe diagnostico.py
if errorlevel 1 goto fail
echo Dependencias listas. Revisa PASO_A_PASO.md y ejecuta iniciar_bot.bat.
pause
exit /b 0
:fail
echo La instalacion no termino. Revisa el error anterior.
pause
exit /b 1
