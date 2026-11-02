@echo off
cd /d "%~dp0"
.venv\Scripts\python.exe -m unittest test_emineko test_complete test_playnite -v
if errorlevel 1 goto fail
.venv\Scripts\python.exe verify_commands.py
if errorlevel 1 goto fail
.venv\Scripts\python.exe diagnostico.py
if errorlevel 1 goto fail
echo Verificacion completada.
pause
exit /b 0
:fail
echo Fallo la verificacion. Revisa el error anterior.
pause
exit /b 1
