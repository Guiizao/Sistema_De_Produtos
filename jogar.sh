#!/usr/bin/env bash
# Social Wars - inicia o jogo com um comando so.
set -euo pipefail
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"

if ! command -v "$PY" >/dev/null 2>&1; then
    echo " [!] Python 3 nao encontrado. Instale com o gerenciador de pacotes da sua distro."
    exit 1
fi

if ! "$PY" -c "import flask" >/dev/null 2>&1; then
    echo
    echo " [+] Instalando as dependencias pela primeira vez..."
    echo
    "$PY" -m pip install -r requirements.txt
fi

exec "$PY" play.py "$@"
