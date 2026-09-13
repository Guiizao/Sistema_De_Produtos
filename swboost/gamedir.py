"""Localizar a pasta do jogo e checar a porta - sem dependencia externa.

Este modulo usa somente a biblioteca padrao, de proposito. O `instalar.py` e
o `play.py --check` precisam funcionar ANTES de o Flask estar instalado:

- o instalador so copia arquivos, e roda antes de qualquer `pip install`;
- o `--check` existe justamente para dizer quais dependencias faltam, entao
  nao pode quebrar com ModuleNotFoundError ao ser executado.

Por isso nada aqui pode importar `swboost.web` (que traz o Flask junto).
"""

from __future__ import annotations

import os
import socket
import sys

GAME_MARKERS = ("server.py", "sessions.py", "bundle.py")


class BoostError(Exception):
    """Algo impediu o servidor turbinado de subir."""


def _looks_like_game(path: str) -> bool:
    return all(os.path.isfile(os.path.join(path, marker)) for marker in GAME_MARKERS)


DICA_BAIXAR = (
    "Ainda nao baixou o jogo neste computador?\n"
    "  - Windows: clique duas vezes em PREPARAR.bat (ele baixa sozinho)\n"
    "  - Linux:   python3 preparar.py\n"
    "  - ou baixe a mao: "
    "https://github.com/AcidCaos/socialwarriors/archive/refs/heads/main.zip"
)


def locate_game_dir(hint: str | None = None) -> str:
    """Descobre onde esta o codigo-fonte do Social Wars."""
    if hint:
        path = os.path.abspath(os.path.expanduser(hint))

        # Separar os casos: "a pasta nem existe" e um problema bem diferente
        # de "a pasta existe mas nao e o jogo", e a solucao tambem e outra.
        if not os.path.exists(path):
            raise BoostError(f"A pasta '{path}' nao existe neste computador.\n\n{DICA_BAIXAR}")
        if not os.path.isdir(path):
            raise BoostError(f"'{path}' e um arquivo, nao uma pasta.")

        if not _looks_like_game(path):
            faltando = [m for m in GAME_MARKERS
                        if not os.path.isfile(os.path.join(path, m))]
            raise BoostError(
                f"A pasta '{path}' existe, mas nao e a do Social Wars.\n"
                f"Falta: {', '.join(faltando)}\n"
                f"A pasta certa e a que tem o server.py e a pasta assets.\n\n"
                f"{DICA_BAIXAR}"
            )
        return path

    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates = [os.getcwd()]

    # Congelado (.exe do PyInstaller): __file__ aponta para a pasta temporaria
    # de extracao, entao quem vale e o lugar do proprio executavel.
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        candidates += [exe_dir, os.path.join(exe_dir, "socialwarriors"),
                       os.path.dirname(exe_dir)]

    candidates += [
        here,
        os.path.join(here, "socialwarriors"),
        os.path.join(os.path.dirname(here), "socialwarriors"),
        os.path.dirname(here),
    ]

    for candidate in candidates:
        if _looks_like_game(candidate):
            return os.path.abspath(candidate)

    raise BoostError(
        "Nao encontrei o codigo-fonte do Social Wars.\n"
        "Coloque estes arquivos dentro da pasta do jogo (a que tem server.py) "
        "ou use --game-dir CAMINHO."
    )


def port_is_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind((host, port))
        except OSError:
            return False
    return True
