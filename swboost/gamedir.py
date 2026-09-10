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


def locate_game_dir(hint: str | None = None) -> str:
    """Descobre onde esta o codigo-fonte do Social Wars."""
    if hint:
        path = os.path.abspath(os.path.expanduser(hint))
        if not _looks_like_game(path):
            raise BoostError(
                f"'{path}' nao parece a pasta do Social Wars "
                f"(esperava encontrar {', '.join(GAME_MARKERS)})."
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
