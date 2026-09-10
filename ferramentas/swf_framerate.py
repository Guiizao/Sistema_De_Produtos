#!/usr/bin/env python3
"""Inspeciona e reescreve a taxa de quadros de arquivos SWF.

O servidor turbinado ja faz isso em memoria (`play.py --fps 60`), sem tocar
nos arquivos. Esta ferramenta existe para quem quer gravar a mudanca em disco
- por exemplo para usar o bundle .exe da release, que nao passa pelo boost.

    python ferramentas/swf_framerate.py info assets/flash/SWLoader.swf
    python ferramentas/swf_framerate.py set 60 assets/flash/SWLoader.swf
    python ferramentas/swf_framerate.py restore assets/flash/SWLoader.swf

Toda gravacao cria um backup `.orig` ao lado do arquivo, e `restore` volta a
partir dele. Leia ANALISE_TECNICA.md antes de mudar: no Social Wars a taxa de
quadros controla a VELOCIDADE do jogo, nao so a suavidade.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from swboost import swf  # noqa: E402

BACKUP_SUFFIX = ".orig"


def cmd_info(paths: list) -> int:
    problems = 0
    for path in paths:
        try:
            header = swf.read_header_file(path)
            backup = " (tem backup .orig)" if os.path.isfile(path + BACKUP_SUFFIX) else ""
            print(f"  {os.path.basename(path)}: {header.describe()}{backup}")
        except (swf.SwfError, OSError) as exc:
            print(f"  {os.path.basename(path)}: ERRO - {exc}")
            problems += 1
    return 1 if problems else 0


def cmd_set(fps: float, paths: list, keep_backup: bool = True) -> int:
    problems = 0
    for path in paths:
        backup = path + BACKUP_SUFFIX
        try:
            before = swf.read_header_file(path)
            # O backup e sempre do arquivo de fabrica: se ja existe, nao
            # sobrescreve com uma versao ja modificada.
            if keep_backup and not os.path.isfile(backup):
                shutil.copy2(path, backup)
            after = swf.set_frame_rate_file(path, fps)
            print(f"  {os.path.basename(path)}: {before.frame_rate:g} -> {after.frame_rate:g} fps")
        except (swf.SwfError, OSError) as exc:
            print(f"  {os.path.basename(path)}: ERRO - {exc}")
            problems += 1
    return 1 if problems else 0


def cmd_restore(paths: list) -> int:
    problems = 0
    for path in paths:
        backup = path + BACKUP_SUFFIX
        if not os.path.isfile(backup):
            print(f"  {os.path.basename(path)}: sem backup .orig, nada a restaurar")
            problems += 1
            continue
        try:
            shutil.copy2(backup, path)
            header = swf.read_header_file(path)
            print(f"  {os.path.basename(path)}: restaurado ({header.frame_rate:g} fps)")
        except OSError as exc:
            print(f"  {os.path.basename(path)}: ERRO - {exc}")
            problems += 1
    return 1 if problems else 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)

    info = sub.add_parser("info", help="mostrar a taxa de quadros atual")
    info.add_argument("paths", nargs="+")

    setter = sub.add_parser("set", help="gravar uma nova taxa de quadros")
    setter.add_argument("fps", type=float)
    setter.add_argument("paths", nargs="+")
    setter.add_argument("--no-backup", action="store_true", help="nao criar o arquivo .orig")

    restore = sub.add_parser("restore", help="voltar ao arquivo original (.orig)")
    restore.add_argument("paths", nargs="+")

    args = parser.parse_args(argv)

    if args.command == "info":
        return cmd_info(args.paths)
    if args.command == "set":
        if args.fps > 30:
            print(f"  [!] {args.fps:g} fps deixa o jogo ~{args.fps / 30:.1f}x mais rapido.")
            print("      A logica do Social Wars conta quadros, nao tempo real.")
            print("      Veja ANALISE_TECNICA.md.\n")
        return cmd_set(args.fps, args.paths, keep_backup=not args.no_backup)
    return cmd_restore(args.paths)


if __name__ == "__main__":
    raise SystemExit(main())
