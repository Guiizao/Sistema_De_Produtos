#!/usr/bin/env bash
# Social Wars - inicia o jogo com um comando so.
#
# Nao precisa de root/sudo: as dependencias vao para um ambiente virtual
# dentro desta pasta (.venv), nunca no Python do sistema.
set -euo pipefail
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"

if ! command -v "$PY" >/dev/null 2>&1; then
    echo " [!] Python 3 nao encontrado. Instale pelo gerenciador de pacotes da sua distro."
    exit 1
fi

# O requirements.txt do projeto original lista so o flask. O nosso, instalado
# ao lado com outro nome, tem a lista completa.
REQS="requirements.txt"
[ -f "requirements-swboost.txt" ] && REQS="requirements-swboost.txt"

if [ -x ".venv/bin/python" ]; then
    PY=".venv/bin/python"
elif ! "$PY" -c "import flask, waitress" >/dev/null 2>&1; then
    echo
    echo " [+] Preparando o ambiente pela primeira vez (sem sudo)..."
    echo
    if "$PY" -m venv .venv 2>/dev/null; then
        PY=".venv/bin/python"
        "$PY" -m pip install --upgrade pip >/dev/null
        "$PY" -m pip install -r "$REQS"
    else
        echo " [!] Nao consegui criar o .venv. Instalando so para o seu usuario..."
        "$PY" -m pip install --user -r "$REQS"
    fi
fi

exec "$PY" play.py "$@"
