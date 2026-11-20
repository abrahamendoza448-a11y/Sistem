@echo off
REM Pone en marcha ARCHIVA en modo demostracion (Windows).
REM   iniciar.bat         -> http://127.0.0.1:8000 (solo esta computadora)
REM   iniciar.bat red     -> tambien accesible desde celulares en la misma red Wi-Fi
cd /d "%~dp0"
where py >nul 2>nul && (set PY=py -3) || (set PY=python)
%PY% --version >nul 2>nul || (echo Falta instalar Python 3.10 o superior: https://www.python.org/downloads/ ^(marque "Add Python to PATH"^) & pause & exit /b 1)
if not exist .venv\Scripts\python.exe %PY% -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install -q -r requirements.txt
if not exist data mkdir data
python manage.py migrate -v0
python manage.py seed_demo
python manage.py seed_papeles
set HOST=127.0.0.1
if /i "%1"=="red" (
  set HOST=0.0.0.0
  set ARCHIVA_ALLOWED_HOSTS=*
  echo Desde el celular ^(misma Wi-Fi^) abra: http://IP-DE-ESTA-PC:8000  ^(use ipconfig para ver la IP^)
)
echo ARCHIVA listo en http://127.0.0.1:8000  (usuarios: admin, archivista, funcionario, auditor - clave: Archiva-2026!)
python manage.py runserver %HOST%:8000
