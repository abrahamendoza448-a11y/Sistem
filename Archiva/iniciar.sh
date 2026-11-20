#!/usr/bin/env bash
# Pone en marcha ARCHIVA en modo demostración (Linux / Mac).
#   ./iniciar.sh          -> abre en http://127.0.0.1:8000 (solo esta computadora)
#   ./iniciar.sh --red    -> también accesible desde celulares en la misma red Wi-Fi
set -e
cd "$(dirname "$0")"
PY=$(command -v python3 || command -v python) || { echo "Falta Python 3.10 o superior: https://www.python.org/downloads/"; exit 1; }
[ -d .venv ] || "$PY" -m venv .venv
. .venv/bin/activate
python -m pip install -q -r requirements.txt
mkdir -p data
python manage.py migrate -v0
python manage.py seed_demo
python manage.py seed_papeles
HOST=127.0.0.1
if [ "$1" = "--red" ]; then
  HOST=0.0.0.0
  export ARCHIVA_ALLOWED_HOSTS="*"
  IP=$(hostname -I 2>/dev/null | awk '{print $1}')
  echo "Desde el celular (misma Wi-Fi) abra: http://${IP:-IP-DE-ESTA-PC}:8000"
fi
echo "ARCHIVA listo en http://127.0.0.1:8000  (usuarios: admin, archivista, funcionario, auditor · clave: Archiva-2026!)"
exec python manage.py runserver "$HOST:8000"
