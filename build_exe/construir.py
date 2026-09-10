#!/usr/bin/env python3
"""Gera o executavel do lancador do Social Wars.

O executavel NAO empacota os assets do jogo (sao ~1,4 GB). Ele e so o
lancador: leva Python, Flask, waitress e o SW Boost dentro de si, e roda
contra a pasta do jogo onde estiver colocado. Resultado: ~15-25 MB.

    python build_exe/construir.py            # arquivo unico (padrao)
    python build_exe/construir.py --onedir   # pasta (melhor com AppLocker)

SEM ADMINISTRADOR
-----------------
O executavel gerado nao pede elevacao: o PyInstaller so embute o manifesto
de administrador quando `uac_admin=True`, e aqui isso fica explicitamente
desligado. O que costuma disparar o pedido de administrador nao e o .exe, e
o `pip install` gravando no Python do sistema - por isso o `jogar.bat` usa um
ambiente virtual local.

Para rodar sem elevacao, o executavel precisa ficar numa pasta onde o seu
usuario possa escrever (Area de Trabalho, Documentos, Downloads, um pendrive).
Dentro de "Arquivos de Programas" o Windows bloqueia a gravacao dos saves.

O build so pode ser feito no mesmo sistema operacional de destino: o
PyInstaller nao faz compilacao cruzada. Para gerar o .exe do Windows sem ter
um Windows a mao, use o fluxo do GitHub Actions em
`.github/workflows/build-windows.yml`.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOME = "SocialWars"

# O jogo importa estes modulos em tempo de execucao, a partir dos .py que
# ficam na pasta do jogo. O PyInstaller nao consegue enxergar essas
# dependencias sozinho, entao elas entram na mao.
IMPORTS_OCULTOS = [
    "flask",
    "jinja2",
    "werkzeug",
    "waitress",
    "jsonpatch",
    "jsonpointer",
    "requests",
    "email.mime.text",       # usado por partes da stdlib que o waitress puxa
    "logging.handlers",
]


def construir(onefile: bool = True, limpar: bool = True) -> int:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("[!] PyInstaller nao esta instalado. Rode:")
        print("      pip install pyinstaller")
        return 1

    trabalho = os.path.join(RAIZ, "build_exe", "work")
    destino = os.path.join(RAIZ, "build_exe", "dist")

    comando = [
        sys.executable, "-m", "PyInstaller",
        "--onefile" if onefile else "--onedir",
        "--console",              # o jogador precisa ver o log e os erros
        "--noupx",                # UPX costuma acionar antivirus a toa
        "--noconfirm",
        "--clean" if limpar else "--noconfirm",
        "--name", NOME,
        "--workpath", trabalho,
        "--distpath", destino,
        "--specpath", os.path.join(RAIZ, "build_exe"),
        "--paths", RAIZ,
    ]

    for modulo in IMPORTS_OCULTOS:
        comando += ["--hidden-import", modulo]

    # O pacote swboost inteiro precisa ir junto.
    comando += ["--collect-submodules", "swboost"]

    comando.append(os.path.join(RAIZ, "play.py"))

    print("[+] Empacotando...\n")
    resultado = subprocess.run(comando, cwd=RAIZ)
    if resultado.returncode != 0:
        return resultado.returncode

    sufixo = ".exe" if os.name == "nt" else ""
    caminho = os.path.join(destino, NOME + sufixo) if onefile else os.path.join(destino, NOME)
    if os.path.exists(caminho):
        tamanho = (
            os.path.getsize(caminho) if os.path.isfile(caminho)
            else sum(
                os.path.getsize(os.path.join(raiz, nome))
                for raiz, _dirs, nomes in os.walk(caminho)
                for nome in nomes
            )
        )
        print(f"\n[+] Pronto: {caminho}  ({tamanho / 1024 / 1024:.1f} MB)")
        print("\n    Coloque este executavel dentro da pasta do Social Wars")
        print("    (a que tem server.py e assets/) e clique duas vezes.")
        print("    Nao precisa de administrador nem de Python instalado.")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--onedir", action="store_true",
                        help="gerar uma pasta em vez de um arquivo unico")
    parser.add_argument("--sem-limpar", action="store_true",
                        help="reaproveitar o build anterior (mais rapido)")
    args = parser.parse_args(argv)
    return construir(onefile=not args.onedir, limpar=not args.sem_limpar)


if __name__ == "__main__":
    raise SystemExit(main())
