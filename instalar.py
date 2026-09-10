#!/usr/bin/env python3
"""Copia o SW Boost para dentro da pasta do Social Wars.

Depois de instalar, ESTA pasta (a do boost) pode ser apagada: tudo o que o
jogo precisa passa a morar dentro da pasta dele.

    python instalar.py                          # pergunta onde esta o jogo
    python instalar.py /caminho/do/socialwarriors

Nenhum arquivo do jogo e alterado ou apagado. Se algum nome ja existir na
pasta de destino, o script avisa e para (use --force para sobrescrever).
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Importa so o modulo sem dependencias: o instalador roda ANTES de qualquer
# `pip install`, entao nao pode exigir Flask para copiar arquivos.
from swboost.gamedir import BoostError, locate_game_dir  # noqa: E402

# O que vai para a pasta do jogo, como (origem, nome no destino).
# `tests/` fica de fora de proposito. O nosso README vira SWBOOST.md e o nosso
# requirements.txt vira requirements-swboost.txt: os dois nomes ja existem no
# projeto Social Warriors e nao podem ser sobrescritos. (O requirements.txt de
# la lista so o flask, faltando requests e jsonpatch - veja ANALISE_TECNICA.md.)
PAYLOAD = (
    ("play.py", "play.py"),
    ("swboost", "swboost"),
    ("ferramentas", "ferramentas"),
    ("jogar.bat", "jogar.bat"),
    ("jogar.sh", "jogar.sh"),
    ("requirements.txt", "requirements-swboost.txt"),
    ("README.md", "SWBOOST.md"),
    ("MANUAL.md", "MANUAL.md"),
    ("ANALISE_TECNICA.md", "ANALISE_TECNICA.md"),
    ("IDEIAS.md", "IDEIAS.md"),
)


def _limpar_caminho(texto: str) -> str:
    """Normaliza um caminho colado ou arrastado para a janela do terminal.

    Arrastar uma pasta para o Prompt de Comando cola o caminho entre aspas
    quando ele tem espacos; o PowerShell as vezes acrescenta um `& `.
    """
    texto = texto.strip()
    if texto.startswith("& "):
        texto = texto[2:].strip()
    return texto.strip("\"'").rstrip("\\/") or texto.strip()


def perguntar_pasta_do_jogo() -> str | None:
    """Pergunta onde esta o jogo, com ate tres tentativas."""
    print("\n  Onde esta a pasta do Social Wars?")
    print("  (a pasta que tem o server.py e a pasta assets)")
    print("\n  Dica: arraste a pasta para esta janela e aperte Enter.")
    print("  Para desistir, aperte Enter sem digitar nada.\n")

    for _ in range(3):
        try:
            resposta = input("  Caminho: ")
        except (EOFError, KeyboardInterrupt):
            return None

        caminho = _limpar_caminho(resposta)
        if not caminho:
            return None

        try:
            return locate_game_dir(caminho)
        except BoostError as exc:
            print(f"\n  [!] {exc}\n")

    return None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("destino", nargs="?", help="pasta do jogo (a que contem server.py)")
    parser.add_argument("--force", action="store_true", help="sobrescrever arquivos existentes")
    parser.add_argument("--dry-run", action="store_true", help="so mostrar o que seria copiado")
    args = parser.parse_args(argv)

    source = os.path.dirname(os.path.abspath(__file__))

    try:
        destination = locate_game_dir(args.destino)
    except BoostError as exc:
        if args.destino:
            # Deu um caminho explicito e ele nao serve: nao adianta perguntar.
            print(f"[!] {exc}")
            return 1
        destination = perguntar_pasta_do_jogo()
        if destination is None:
            print("\n[!] Instalacao cancelada.")
            print("    Rode de novo assim: python instalar.py CAMINHO-DA-PASTA-DO-JOGO")
            return 1

    if os.path.abspath(destination) == source:
        print("[+] O SW Boost ja esta dentro da pasta do jogo. Nada a fazer.")
        return 0

    print(f"[+] Origem ..: {source}")
    print(f"[+] Destino .: {destination}\n")

    planned, conflicts = [], []
    for name, target_name in PAYLOAD:
        origin = os.path.join(source, name)
        if not os.path.exists(origin):
            continue
        target = os.path.join(destination, target_name)
        planned.append((origin, target, target_name))
        if os.path.exists(target):
            conflicts.append(target_name)

    if conflicts and not args.force:
        print("[!] Ja existem no destino:")
        for name in conflicts:
            print(f"      {name}")
        print("\n    Use --force para sobrescrever.")
        return 1

    for origin, target, name in planned:
        kind = "pasta " if os.path.isdir(origin) else "arquivo"
        print(f"    {kind}  {name}")
        if args.dry_run:
            continue
        if os.path.isdir(origin):
            shutil.copytree(origin, target, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            shutil.copy2(origin, target)

    if args.dry_run:
        print("\n[+] --dry-run: nada foi copiado.")
        return 0

    print("\n[+] Pronto!\n")
    print(f"    A partir de agora so importa esta pasta:")
    print(f"      {destination}\n")
    print("    Para jogar, entre nela e:")
    if os.name == "nt":
        print("      clique duas vezes em jogar.bat")
    else:
        print("      ./jogar.sh")
    print(f"\n    Esta pasta aqui ({os.path.basename(source)}) ja cumpriu o papel")
    print("    e pode ser apagada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
