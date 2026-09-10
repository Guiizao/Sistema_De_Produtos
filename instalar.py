#!/usr/bin/env python3
"""Copia o SW Boost para dentro da pasta do Social Wars.

Nao e obrigatorio: o `play.py` funciona de fora da pasta do jogo com
`--game-dir CAMINHO`. Instalar deixa tudo junto, o que e mais pratico para
criar um atalho na area de trabalho.

    python instalar.py /caminho/para/socialwarriors

Nenhum arquivo do jogo e alterado ou apagado. Se algum nome ja existir na
pasta de destino, o script avisa e para (use --force para sobrescrever).
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from swboost import boost  # noqa: E402

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
    ("ANALISE_TECNICA.md", "ANALISE_TECNICA.md"),
    ("IDEIAS.md", "IDEIAS.md"),
)


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
        destination = boost.locate_game_dir(args.destino)
    except boost.BoostError as exc:
        print(f"[!] {exc}")
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

    print("\n[+] Pronto. Agora, dentro da pasta do jogo:")
    print("      Windows ....: clique duas vezes em jogar.bat")
    print("      GNU/Linux ..: ./jogar.sh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
